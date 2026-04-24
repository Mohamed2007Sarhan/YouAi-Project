"""
Extract cookies from all browsers supported by browser_cookie3, save encrypted snapshot,
and build a text summary for LLM profiling (domains / counts only — no cookie values in prompts).
"""

import json
import os
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

try:
    import browser_cookie3
except ImportError:
    browser_cookie3 = None

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MEMORY_DIR = PROJECT_ROOT / "memory"
USER_DATA = PROJECT_ROOT / "user_data"
ENCRYPTED_PATH = MEMORY_DIR / "browser_cookies_snapshot.enc"


def _fernet():
    from cryptography.fernet import Fernet
    from dotenv import load_dotenv

    env_path = MEMORY_DIR / ".env.memory"
    load_dotenv(dotenv_path=env_path)
    key = os.getenv("MEMORY_ENCRYPTION_KEY")
    if not key:
        key = Fernet.generate_key().decode("utf-8")
        env_path.touch(exist_ok=True)
        from dotenv import set_key

        set_key(str(env_path), "MEMORY_ENCRYPTION_KEY", key)
    return Fernet(key.encode("utf-8"))


def save_encrypted_snapshot(payload: Dict[str, Any]) -> bool:
    """Encrypt full cookie payload to disk (values included)."""
    try:
        MEMORY_DIR.mkdir(parents=True, exist_ok=True)
        raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        ENCRYPTED_PATH.write_bytes(_fernet().encrypt(raw))
        return True
    except Exception:
        return False


def _cookie_to_dict(c) -> Dict[str, Any]:
    return {
        "domain": getattr(c, "domain", "") or "",
        "path": getattr(c, "path", "") or "",
        "name": getattr(c, "name", "") or "",
        "value": getattr(c, "value", "") or "",
        "secure": bool(getattr(c, "secure", False)),
    }


def extract_all_browser_cookies(
    progress: Optional[Callable[[int, str], None]] = None,
) -> Tuple[Dict[str, Any], str]:
    """
    Pull cookies from every browser browser_cookie3 supports.
    Returns (full_payload_for_encryption, llm_safe_summary_text).
    """
    if browser_cookie3 is None:
        return {}, "[BROWSER_COOKIES] browser_cookie3 not installed.\n"

    def p(pct: int, msg: str):
        if progress:
            progress(pct, msg)

    p(8, "Scanning installed browsers for cookies…")

    browsers_meta: Dict[str, Any] = {}
    all_domains: List[str] = []
    total = 0

    for cookie_fn in getattr(browser_cookie3, "all_browsers", []):
        name = getattr(cookie_fn, "__name__", "browser")
        try:
            cj = cookie_fn()
            rows = []
            for c in cj:
                d = _cookie_to_dict(c)
                rows.append(d)
                dom = (d.get("domain") or "").lstrip(".")
                if dom:
                    all_domains.append(dom)
                total += 1
            browsers_meta[name] = {"count": len(rows), "cookies": rows}
        except Exception as e:
            browsers_meta[name] = {"count": 0, "error": str(e), "cookies": []}

    p(14, "Verifying merged cookie jar (load)…")
    merged_count = 0
    try:
        merged_jar = browser_cookie3.load()
        merged_count = len(list(merged_jar))
    except Exception as e:
        browsers_meta["_merged_load_error"] = str(e)

    payload = {
        "browsers": browsers_meta,
        "total_cookie_rows": total,
        "merged_cookie_count_estimate": merged_count,
        "source": "browser_cookie3.all_browsers",
    }
    p(18, "Saving encrypted cookie snapshot…")
    save_encrypted_snapshot(payload)

    domain_counts = Counter(all_domains)
    top_domains = [f"{d} ({n})" for d, n in domain_counts.most_common(120)]
    # Per-browser row counts (why "10 accounts" in vault ≠ little text: LLM only saw a short summary before)
    browser_lines = []
    for name, meta in sorted((browsers_meta or {}).items()):
        if name.startswith("_"):
            continue
        if not isinstance(meta, dict):
            continue
        cnt = meta.get("count", 0)
        err = meta.get("error")
        if err:
            browser_lines.append(f"{name}: 0 rows (error: {err[:80]})")
        else:
            browser_lines.append(f"{name}: {cnt} cookie rows")
    if not browser_lines:
        browser_lines = ["(no browser cookie stores readable — close browsers or check permissions)"]

    # Service hints from domain names (no cookie values)
    hint_keywords = (
        ("google", "Google / Gmail / YouTube ecosystem"),
        ("youtube", "YouTube"),
        ("facebook", "Facebook"),
        ("instagram", "Instagram"),
        ("twitter", "X / Twitter"),
        ("x.com", "X / Twitter"),
        ("linkedin", "LinkedIn"),
        ("github", "GitHub"),
        ("microsoft", "Microsoft / Outlook"),
        ("apple", "Apple / iCloud"),
        ("spotify", "Spotify"),
        ("amazon", "Amazon"),
        ("netflix", "Netflix"),
        ("reddit", "Reddit"),
        ("discord", "Discord"),
        ("telegram", "Telegram web"),
        ("whatsapp", "WhatsApp Web"),
        ("openai", "chatgpt / OpenAI"),
        ("anthropic", "Claude / Anthropic"),
        ("nvidia", "NVIDIA"),
    )
    hints: List[str] = []
    dom_lower = " ".join(domain_counts.keys()).lower()
    for key, label in hint_keywords:
        if key in dom_lower and label not in hints:
            hints.append(label)

    summary_lines = [
        "[BROWSER_COOKIES] Full snapshot encrypted locally (browser_cookies_snapshot.enc).",
        f"[BROWSER_COOKIES] Total cookie rows (all browsers): {total}.",
        f"[BROWSER_COOKIES] Approximate unique domains: {len(domain_counts)}.",
        f"[BROWSER_COOKIES] Top domains by row count (names only, no secrets): {', '.join(top_domains[:80])}",
    ]
    if top_domains[80:]:
        summary_lines.append(
            "[BROWSER_COOKIES] More domains (continued): " + ", ".join(top_domains[80:120])
        )
    summary_lines.append(
        "[BROWSER_COOKIES] Per-browser row counts: " + " | ".join(browser_lines)
    )
    summary_lines.append(
        "[BROWSER_COOKIES] Inferred service hints (from domain names): "
        + (", ".join(hints) if hints else "(none detected)")
    )
    summary_lines.append(
        f"[BROWSER_COOKIES] browser_cookie3.load() merged count estimate: {merged_count}"
    )
    if browsers_meta.get("_merged_load_error"):
        summary_lines.append(
            "[BROWSER_COOKIES] merged load note: " + str(browsers_meta["_merged_load_error"])
        )
    summary_lines.append(
        "[BROWSER_COOKIES] Infer language, region, hobbies, and work tools from domains only; "
        "values are not cookie contents."
    )
    return payload, "\n".join(summary_lines) + "\n"
