"""
Public social profile extractor (Facebook / Instagram).

Scope:
- Reads *public* profile pages only (no login automation, no private content).
- Extracts lightweight identity hints: display name, bio/description, og:title.
"""

from __future__ import annotations

import re
from urllib.parse import urlparse
from typing import Dict, List

import requests


UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
)

COMMON_HEADERS = {
    "User-Agent": UA,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9,ar;q=0.8",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
}


def _extract_meta(html: str, prop: str) -> str:
    m = re.search(
        rf'<meta[^>]+(?:property|name)=["\']{re.escape(prop)}["\'][^>]+content=["\']([^"\']+)["\']',
        html,
        flags=re.IGNORECASE,
    )
    return (m.group(1).strip() if m else "")


def _clean(s: str) -> str:
    s = re.sub(r"\s+", " ", s or "").strip()
    return s[:500]


def _normalize_candidates(url: str, platform: str) -> List[str]:
    base = url.strip()
    if not base:
        return []
    if not base.startswith(("http://", "https://")):
        base = "https://" + base
    # Keep deterministic order with dedup
    cands = [base]
    if platform == "facebook":
        try:
            p = urlparse(base)
            path = (p.path or "").strip("/")
            if path:
                cands.extend(
                    [
                        f"https://www.facebook.com/{path}/",
                        f"https://m.facebook.com/{path}/",
                        f"https://mbasic.facebook.com/{path}/",
                    ]
                )
        except Exception:
            pass
    elif platform == "instagram":
        try:
            p = urlparse(base)
            path = (p.path or "").strip("/")
            if path:
                cands.extend(
                    [
                        f"https://www.instagram.com/{path}/",
                        f"https://instagram.com/{path}/",
                    ]
                )
        except Exception:
            pass

    out = []
    seen = set()
    for c in cands:
        k = c.lower().rstrip("/")
        if k not in seen:
            seen.add(k)
            out.append(c)
    return out


def _guess_name_from_url(url: str) -> str:
    try:
        p = urlparse(url if url.startswith(("http://", "https://")) else "https://" + url)
        path = (p.path or "").strip("/")
        if not path:
            return ""
        # facebook profile.php?id=... case
        if path.lower().startswith("profile.php"):
            return ""
        handle = path.split("/", 1)[0]
        handle = handle.lstrip("@")
        # If malformed with email, keep local-part as a soft hint
        if "@" in handle:
            handle = handle.split("@", 1)[0]
        handle = re.sub(r"[^A-Za-z0-9._-]+", " ", handle).strip()
        return _clean(handle)
    except Exception:
        return ""


def extract_public_profile(url: str, platform_hint: str = "") -> Dict[str, str]:
    """
    Returns dict with:
      success, platform, profile_url, display_name, bio, summary_text, error
    """
    out = {
        "success": False,
        "platform": (platform_hint or "").strip().lower(),
        "profile_url": url,
        "display_name": "",
        "bio": "",
        "summary_text": "",
        "error": "",
    }
    if not url:
        out["error"] = "Empty URL"
        return out

    try:
        low = url.lower()
        if not out["platform"]:
            if "instagram.com" in low:
                out["platform"] = "instagram"
            elif "facebook.com" in low or "fb.com" in low:
                out["platform"] = "facebook"
            else:
                out["platform"] = "social"

        last_err = ""
        html = ""
        used_url = url
        for u in _normalize_candidates(url, out["platform"]):
            try:
                r = requests.get(u, headers=COMMON_HEADERS, timeout=20, allow_redirects=True)
                if r.status_code < 400 and (r.text or "").strip():
                    html = r.text
                    used_url = r.url or u
                    break
                last_err = f"HTTP {r.status_code}"
            except Exception as e:
                last_err = str(e)

        if not html:
            # Graceful fallback: do not fail hard when social hosts block scraping.
            guess = _guess_name_from_url(url)
            if guess:
                out["display_name"] = guess
                out["bio"] = ""
                out["summary_text"] = _clean(
                    f"[{out['platform'].upper()}_PROFILE] URL: {url} | Name: {guess} | Bio: "
                    "(public page blocked; identifier inferred from URL)"
                )
                out["success"] = True
                out["error"] = last_err or "Blocked/empty response (fallback used)"
                return out
            out["error"] = last_err or "Blocked/empty response"
            return out

        og_title = _extract_meta(html, "og:title")
        og_desc = _extract_meta(html, "og:description")
        tw_title = _extract_meta(html, "twitter:title")
        tw_desc = _extract_meta(html, "twitter:description")

        display = _clean(og_title or tw_title)
        bio = _clean(og_desc or tw_desc)
        if not display and out["platform"] == "facebook":
            # Some fb pages expose title but weak og fields.
            title_tag = re.search(r"<title[^>]*>(.*?)</title>", html, flags=re.IGNORECASE | re.DOTALL)
            if title_tag:
                display = _clean(title_tag.group(1))

        out["display_name"] = display
        out["bio"] = bio
        out["summary_text"] = _clean(
            f"[{out['platform'].upper()}_PROFILE] URL: {used_url} | Name: {display} | Bio: {bio}"
        )
        out["success"] = True
        return out
    except Exception as e:
        out["error"] = str(e)
        return out

