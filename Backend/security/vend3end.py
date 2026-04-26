"""
vend3end.py — Three-Tier Dynamic Key Encryption Framework
==========================================================
Reference implementation of the Vend3end scheme (Mohamed Sarhan Hamed, 2025).

Three independent principals each hold one layer:
  K1  —  AI model key       (ephemeral per-session, never persisted raw)
  K2  —  User key           (derived from user passphrase via PBKDF2)
  K3  —  Company key        (loaded from company.txt, stored sealed under K1)

No subset of two principals can decrypt ciphertext without the third.

Encryption order (inside-out):
  C1 = AES-256-GCM(K3, plaintext , AD)
  C2 = AES-256-GCM(K2, C1        , AD)
  C3 = AES-256-GCM(K1, C2        , AD)   ← this is what gets stored

Decryption order (outside-in):
  C2 = Dec(K1, C3, AD)
  C1 = Dec(K2, C2, AD)
  M  = Dec(K3, C1, AD)
"""

import os
import logging
from pathlib import Path
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes

logger = logging.getLogger("Vend3end")

# ── Constants ──────────────────────────────────────────────────────────────
NONCE_LEN = 12   # 96-bit GCM nonce (NIST recommended)
KEY_LEN   = 32   # 256-bit AES key


# ── Primitive helpers ──────────────────────────────────────────────────────

def generate_key() -> bytes:
    """Generate a cryptographically secure random 256-bit key."""
    return os.urandom(KEY_LEN)


def derive_user_key(password: str, salt: bytes, iterations: int = 600_000) -> bytes:
    """
    Derive K2 from a user passphrase using PBKDF2-HMAC-SHA256.
    NIST SP 800-132 recommends ≥ 600 000 iterations for AES-256.
    """
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=KEY_LEN,
        salt=salt,
        iterations=iterations,
    )
    return kdf.derive(password.encode("utf-8"))


def _enc(key: bytes, plaintext: bytes, ad: bytes = b"") -> bytes:
    """Single-layer AES-256-GCM encryption. Returns nonce || ciphertext+tag."""
    nonce = os.urandom(NONCE_LEN)
    ct    = AESGCM(key).encrypt(nonce, plaintext, ad)
    return nonce + ct


def _dec(key: bytes, blob: bytes, ad: bytes = b"") -> bytes:
    """Single-layer AES-256-GCM decryption. Raises on tag mismatch."""
    nonce = blob[:NONCE_LEN]
    ct    = blob[NONCE_LEN:]
    return AESGCM(key).decrypt(nonce, ct, ad)


# ── Key custody helpers ────────────────────────────────────────────────────

def seal_k3(k1: bytes, k3: bytes) -> bytes:
    """Encrypt K3 under K1 for company-side storage (no AD — key transport only)."""
    return _enc(k1, k3)


def unseal_k3(k1: bytes, sealed_k3: bytes) -> bytes:
    """Decrypt the sealed K3 blob using K1."""
    return _dec(k1, sealed_k3)


# ── Core Vend3end encrypt / decrypt ───────────────────────────────────────

def encrypt(plaintext: bytes, k1: bytes, k2: bytes, k3: bytes,
            ad: bytes = b"") -> bytes:
    """
    Three-layer nested encryption.
    Returns C3 (the stored ciphertext).
    """
    c1 = _enc(k3, plaintext, ad)   # innermost  — company layer
    c2 = _enc(k2, c1,        ad)   # middle     — user layer
    c3 = _enc(k1, c2,        ad)   # outer      — AI-model layer
    return c3


def decrypt(c3: bytes, k1: bytes, k2: bytes, k3: bytes,
            ad: bytes = b"") -> bytes:
    """
    Three-layer nested decryption.
    Requires all three keys in strict order.
    """
    c2 = _dec(k1, c3, ad)   # AI model strips outer layer
    c1 = _dec(k2, c2, ad)   # user strips middle layer
    m  = _dec(k3, c1, ad)   # company key strips innermost layer
    return m


# ── Session manager ────────────────────────────────────────────────────────

class Vend3end:
    """
    Stateful Vend3end session.

    Usage
    -----
    session = Vend3end.from_company_file(
        company_txt_path = "company.txt",
        user_passphrase  = "user-secret",
    )
    ct = session.encrypt(b"Sensitive record", ad=b"uid=42|ts=...")
    pt = session.decrypt(ct,                  ad=b"uid=42|ts=...")
    """

    def __init__(self, k1: bytes, k2: bytes, k3: bytes, sealed_k3: bytes):
        self._k1        = k1
        self._k2        = k2
        self._k3        = k3
        self.sealed_k3  = sealed_k3   # what is persisted (K3 enc under K1)

    # ── Factory constructors ───────────────────────────────────────────────

    @classmethod
    def new_session(cls, user_passphrase: str, company_password: str) -> "Vend3end":
        """
        Create a brand-new session with fresh K1 and fresh user salt.
        K2 is derived from user_passphrase + fresh salt (salt stored embedded
        in the sealed_k3 blob for demonstration; production should use HSM).
        K3 is derived from company_password using PBKDF2 with a fixed public salt
        so the same company password always yields the same K3 across deployments.
        """
        # K1 — ephemeral AI-model key
        k1   = generate_key()

        # K2 — user key derived from passphrase
        user_salt = os.urandom(16)
        k2   = derive_user_key(user_passphrase, user_salt)

        # K3 — company key derived deterministically from company password
        # Using a fixed well-known salt is acceptable here because K3 is
        # never stored in plaintext and is still protected by K1 (seal).
        COMPANY_SALT = b"vend3end-company-kdf-salt-v1-2025"
        k3   = derive_user_key(company_password, COMPANY_SALT, iterations=600_000)

        sealed = seal_k3(k1, k3)
        logger.info("[Vend3end] New session initialised. K1 ephemeral, K3 sealed.")
        return cls(k1, k2, k3, sealed)

    @classmethod
    def from_company_file(cls,
                          company_txt_path: str,
                          user_passphrase: str = "default-user") -> "Vend3end":
        """
        Convenience factory: reads the company password from company.txt and
        builds a fresh session. Use this as the standard entry-point while
        company_txt_path is still the runtime source of truth.
        """
        path = Path(company_txt_path)
        if not path.exists():
            raise FileNotFoundError(
                f"[Vend3end] company.txt not found at: {path.resolve()}"
            )
        company_password = path.read_text(encoding="utf-8").strip()
        logger.info(f"[Vend3end] Loaded company credential from: {path.name}")
        return cls.new_session(user_passphrase, company_password)

    # ── Public API ─────────────────────────────────────────────────────────

    def encrypt(self, plaintext: bytes, ad: bytes = b"") -> bytes:
        """Encrypt plaintext under all three keys. Returns C3."""
        return encrypt(plaintext, self._k1, self._k2, self._k3, ad)

    def decrypt(self, ciphertext: bytes, ad: bytes = b"") -> bytes:
        """Decrypt C3 ciphertext. Returns original plaintext."""
        return decrypt(ciphertext, self._k1, self._k2, self._k3, ad)

    def encrypt_str(self, text: str, ad: bytes = b"") -> bytes:
        """Convenience: encrypt a UTF-8 string."""
        return self.encrypt(text.encode("utf-8"), ad)

    def decrypt_str(self, ciphertext: bytes, ad: bytes = b"") -> str:
        """Convenience: decrypt to a UTF-8 string."""
        return self.decrypt(ciphertext, ad).decode("utf-8")

    def get_session_info(self) -> dict:
        """Return non-sensitive session metadata for logging."""
        return {
            "scheme":    "Vend3end-AES-256-GCM-3Layer",
            "k1_present": self._k1 is not None,
            "k2_present": self._k2 is not None,
            "k3_present": self._k3 is not None,
            "sealed_k3_len": len(self.sealed_k3),
        }


# ── Self-test (run directly: python vend3end.py) ──────────────────────────

if __name__ == "__main__":
    import base64, time

    print("=" * 60)
    print("  Vend3end Self-Test — Three-Tier AES-256-GCM Encryption")
    print("=" * 60)

    COMPANY_FILE = Path(__file__).parent.parent.parent / "company.txt"
    if not COMPANY_FILE.exists():
        # Fallback for standalone test
        company_pw = "youaipass"
        print(f"[i] company.txt not found — using inline fallback password.")
    else:
        company_pw = COMPANY_FILE.read_text().strip()
        print(f"[i] Company credential loaded from: {COMPANY_FILE.name}")

    session = Vend3end.new_session(
        user_passphrase  = "test-user-secret",
        company_password = company_pw,
    )

    ad        = b"uid=1|session=test|ts=2025"
    plaintext = b"Sensitive YouAI user record - TOP SECRET"

    t0 = time.perf_counter()
    ct = session.encrypt(plaintext, ad=ad)
    t1 = time.perf_counter()
    pt = session.decrypt(ct, ad=ad)
    t2 = time.perf_counter()

    assert pt == plaintext, "DECRYPTION MISMATCH - TEST FAILED"

    print(f"\n  Plaintext  : {plaintext.decode()}")
    print(f"  Ciphertext : {base64.b64encode(ct[:32]).decode()}... ({len(ct)} bytes)")
    print(f"  Recovered  : {pt.decode()}")
    print(f"\n  Encrypt time : {(t1-t0)*1000:.3f} ms")
    print(f"  Decrypt time : {(t2-t1)*1000:.3f} ms")
    print(f"  Overhead     : {len(ct) - len(plaintext)} bytes (3×nonce + 3×tag = 84 bytes)")
    print(f"\n  Session info : {session.get_session_info()}")
    print("\n  [PASS] All assertions passed. Vend3end is working correctly.")
    print("=" * 60)
