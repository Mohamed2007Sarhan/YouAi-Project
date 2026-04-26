"""
company_vault.py — Vend3end Integration Layer for YouAI Memory System
======================================================================
Bridges the Vend3end three-tier encryption with the GiantMemoryManager.

At startup:
  1. Reads the company password from company.txt (K3 source)
  2. Generates an ephemeral K1 for this server session
  3. Seals K3 under K1 and stores the sealed blob in .env.memory
  4. Exposes encrypt_for_storage() / decrypt_from_storage() helpers
     that wrap any value with all three key layers before it touches the DB.

When deployed (company.txt removed from server):
  - The sealed_k3 stored in .env.memory is the only remnant of K3
  - Without K1 (held by the AI model session) it is useless to an attacker
"""

import os
import logging
import base64
from pathlib import Path
from dotenv import load_dotenv, set_key
from typing import Optional

logger = logging.getLogger("CompanyVault")

# ── Locate project root ────────────────────────────────────────────────────
_HERE         = Path(__file__).parent                        # Backend/security/
_BACKEND_DIR  = _HERE.parent                                 # Backend/
_PROJECT_ROOT = _BACKEND_DIR.parent                          # YouAi/YouAi/
_COMPANY_FILE = _PROJECT_ROOT / "company.txt"
_ENV_MEMORY   = _BACKEND_DIR / "memory" / ".env.memory"


class CompanyVault:
    """
    Singleton-style vault that holds the live Vend3end session for the
    current server process.

    Usage
    -----
    vault = CompanyVault.get_instance()
    ct    = vault.encrypt(b"raw value")
    pt    = vault.decrypt(ct)
    """

    _instance: Optional["CompanyVault"] = None

    def __init__(self):
        from Backend.security.vend3end import Vend3end
        self._session: Optional[Vend3end] = None
        self._initialised = False

    # ── Singleton accessor ─────────────────────────────────────────────────
    @classmethod
    def get_instance(cls) -> "CompanyVault":
        if cls._instance is None:
            cls._instance = cls()
        if not cls._instance._initialised:
            cls._instance._boot()
        return cls._instance

    # ── Boot sequence ──────────────────────────────────────────────────────
    def _boot(self):
        """
        Initialise the Vend3end session from company.txt (pre-deployment)
        or from the sealed_k3 in .env.memory (post-deployment stub).
        """
        from Backend.security.vend3end import Vend3end

        load_dotenv(dotenv_path=_ENV_MEMORY)
        sealed_b64 = os.getenv("VEND3END_SEALED_K3")

        if _COMPANY_FILE.exists():
            # ── Pre-deployment: company.txt is present ─────────────────────
            company_pw = _COMPANY_FILE.read_text(encoding="utf-8").strip()
            logger.info("[CompanyVault] company.txt present — creating fresh Vend3end session.")

            # For this session user_passphrase defaults to a per-session key
            # that the Start.py / twin orchestrator will pass in production.
            self._session = Vend3end.new_session(
                user_passphrase  = os.getenv("YOUAI_USER_PASSPHRASE", "youai-default-user"),
                company_password = company_pw,
            )

            # Persist the sealed K3 so the session can survive restarts (same K1)
            # NOTE: in production the K1 itself should come from an HSM;
            # here we persist the sealed blob so the memory DB remains readable.
            sealed_b64_val = base64.urlsafe_b64encode(self._session.sealed_k3).decode()
            if not _ENV_MEMORY.exists():
                _ENV_MEMORY.touch()
            set_key(str(_ENV_MEMORY), "VEND3END_SEALED_K3", sealed_b64_val)
            logger.info("[CompanyVault] Sealed K3 written to .env.memory.")

        elif sealed_b64:
            # ── Post-deployment: company.txt removed, use sealed K3 stub ───
            # In production the AI model endpoint would unseal K3 on demand.
            # Here we reconstruct a minimal session for backward compatibility.
            logger.warning(
                "[CompanyVault] company.txt not found — operating in sealed-K3 mode. "
                "Decryption of Vend3end-wrapped records requires live AI model cooperation."
            )
            # We cannot reconstruct a full session without K1; store the sealed
            # blob for future use when K1 is re-injected from the model endpoint.
            self._session = None

        else:
            logger.error(
                "[CompanyVault] Neither company.txt nor VEND3END_SEALED_K3 found. "
                "Vend3end encryption will be DISABLED for this session."
            )
            self._session = None

        self._initialised = True

    # ── Public API ─────────────────────────────────────────────────────────
    @property
    def is_active(self) -> bool:
        """True if a live Vend3end session is available."""
        return self._session is not None

    def encrypt(self, plaintext: bytes, ad: bytes = b"") -> bytes:
        """Encrypt with Vend3end. Fail closed if vault inactive."""
        if not self._session:
            raise RuntimeError("[CompanyVault] Vend3end vault inactive; refusing unencrypted write.")
        return self._session.encrypt(plaintext, ad)

    def decrypt(self, ciphertext: bytes, ad: bytes = b"") -> bytes:
        """Decrypt with Vend3end. Fail closed if vault inactive."""
        if not self._session:
            raise RuntimeError("[CompanyVault] Vend3end vault inactive; refusing unsafe decrypt fallback.")
        return self._session.decrypt(ciphertext, ad)

    def encrypt_str(self, text: str, ad: bytes = b"") -> bytes:
        return self.encrypt(text.encode("utf-8"), ad)

    def decrypt_str(self, blob: bytes, ad: bytes = b"") -> str:
        return self.decrypt(blob, ad).decode("utf-8")

    def status(self) -> dict:
        """Return safe diagnostic info."""
        info = {
            "vend3end_active":   self.is_active,
            "company_file":      str(_COMPANY_FILE),
            "company_file_ok":   _COMPANY_FILE.exists(),
            "env_memory":        str(_ENV_MEMORY),
            "sealed_k3_stored":  bool(os.getenv("VEND3END_SEALED_K3")),
        }
        if self._session:
            info.update(self._session.get_session_info())
        return info


# ── Module-level convenience ───────────────────────────────────────────────

def get_vault() -> CompanyVault:
    """Fast accessor for the singleton vault."""
    return CompanyVault.get_instance()


# ── CLI quick-check ────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys, json
    logging.basicConfig(level=logging.INFO, format="%(levelname)s — %(message)s")

    print("=" * 60)
    print("  CompanyVault Boot & Status Check")
    print("=" * 60)

    vault = get_vault()
    status = vault.status()
    print(json.dumps(status, indent=2))

    if vault.is_active:
        test_value = b"YouAI Sensitive Data - Test Record"
        ct = vault.encrypt(test_value)
        pt = vault.decrypt(ct)
        assert pt == test_value, "Round-trip FAILED"
        print(f"\n  [PASS] Encrypt/Decrypt round-trip OK ({len(ct)} bytes -> {len(pt)} bytes)")
    else:
        print("\n  [WARN] Vault not active — check company.txt or .env.memory")

    print("=" * 60)
