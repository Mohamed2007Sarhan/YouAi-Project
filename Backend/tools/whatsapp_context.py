"""
Optional WhatsApp text for LLM profiling (speaking style).

1) Drop one or more WhatsApp .txt exports into: data/whatsapp_exports/
2) YOUAI_WHATSAPP_EXPORT_PATH — optional explicit path to a WhatsApp .txt export.
2) YOUAI_WHATSAPP_WEB=1 — open WhatsApp Web (Playwright), scan QR, scrape recent message bubbles.

Requires for (2): pip install playwright && playwright install chromium
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Iterable, List, Optional, Tuple


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data" / "whatsapp_exports"


def _read_text(path: Path, max_chars: int = 140_000) -> str:
    raw = path.read_text(encoding="utf-8", errors="ignore")
    # Keep the end of file (usually contains the most recent messages)
    if len(raw) > max_chars:
        raw = "[...truncated...]\n" + raw[-max_chars:]
    return raw


_WA_LINE_RE = re.compile(
    r"^\s*(?P<date>\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4}),\s*(?P<time>\d{1,2}:\d{2})\s*-\s*(?P<sender>[^:]{1,80}):\s*(?P<msg>.*)\s*$"
)


def _guess_speaker_names() -> List[str]:
    """
    Returns possible 'your' sender labels to filter on.
    Priority:
      - YOUAI_WHATSAPP_SPEAKER (explicit)
      - personal_identity.name from memory DB
      - fallback: 'You'
    """
    out: List[str] = []
    explicit = os.getenv("YOUAI_WHATSAPP_SPEAKER", "").strip()
    if explicit:
        out.append(explicit)

    # Try to load your name from memory (optional).
    try:
        from memory.memory_management import GiantMemoryManager  # type: ignore

        db = GiantMemoryManager()
        recs = db.get_records("personal_identity", min_importance=1)
        for rec in recs:
            nm = (rec.get("name") or "").strip()
            if nm:
                out.append(nm)
                break
    except Exception:
        pass

    out.append("You")
    # Dedup while keeping order
    seen = set()
    dedup = []
    for x in out:
        if x and x not in seen:
            seen.add(x)
            dedup.append(x)
    return dedup


def _extract_my_messages(raw: str, my_speakers: List[str]) -> Tuple[List[str], int]:
    """
    Parse WhatsApp exported chat text and return (my_message_texts, parsed_lines_count).
    Only lines matching export pattern are counted as parsed lines.
    Multi-line messages are concatenated to the previous message.
    """
    msgs: List[str] = []
    parsed = 0

    # Normalize speaker set case-insensitively
    my_lower = {s.strip().lower() for s in my_speakers if s.strip()}
    current_is_me: Optional[bool] = None

    for line in raw.splitlines():
        m = _WA_LINE_RE.match(line)
        if m:
            parsed += 1
            sender = (m.group("sender") or "").strip()
            msg = (m.group("msg") or "").strip()
            # Skip WhatsApp system lines like "<Media omitted>"
            if not msg or msg.lower() in ("<media omitted>",):
                current_is_me = sender.strip().lower() in my_lower
                continue
            current_is_me = sender.strip().lower() in my_lower
            if current_is_me:
                msgs.append(msg)
        else:
            # Continuation line of previous message (multi-line export)
            if current_is_me and msgs and line.strip():
                msgs[-1] += " " + line.strip()

    return msgs, parsed


def _iter_export_files() -> Iterable[Path]:
    files: List[Path] = []
    # Auto folder scan
    if DATA_DIR.exists():
        files.extend(sorted(DATA_DIR.glob("*.txt")))
    # Optional explicit path
    p = os.getenv("YOUAI_WHATSAPP_EXPORT_PATH", "").strip()
    if p:
        path = Path(p).expanduser()
        if path.is_file():
            files.append(path)
    # Dedup
    seen = set()
    out = []
    for f in files:
        rp = str(f.resolve())
        if rp not in seen:
            seen.add(rp)
            out.append(f)
    return out


def collect_whatsapp_export_text() -> str:
    files = list(_iter_export_files())
    if not files:
        return ""

    my_speakers = _guess_speaker_names()
    blocks: List[str] = []
    total_my = 0
    total_parsed = 0

    for path in files[:8]:  # safety: avoid too many files
        try:
            raw = _read_text(path)
        except Exception as e:
            blocks.append(f"[WHATSAPP_EXPORT] Could not read file: {path} | {e}\n")
            continue

        my_msgs, parsed = _extract_my_messages(raw, my_speakers)
        total_my += len(my_msgs)
        total_parsed += parsed

        # Keep a sample of your own messages only (style-focused)
        sample = my_msgs[-220:]  # last messages are most representative
        sample_text = "\n".join(f"  {m[:800]}" for m in sample if m.strip())
        blocks.append(
            "\n".join(
                [
                    f"[WHATSAPP_EXPORT] Source: {path.name}",
                    f"[WHATSAPP_EXPORT] Parsed lines: {parsed} | Your messages found: {len(my_msgs)}",
                    f"[WHATSAPP_EXPORT] Your speaker labels considered: {', '.join(my_speakers)}",
                    "[WHATSAPP_EXPORT] Use ONLY these lines (my messages) to infer writing style, slang, tone, punctuation, and language mixing:",
                    sample_text,
                    "",
                ]
            )
        )

    header = (
        "[WHATSAPP_EXPORT] Summary: "
        f"{len(files)} file(s) scanned | total parsed lines: {total_parsed} | total your messages: {total_my}\n"
    )
    return header + "\n".join(blocks)


def collect_whatsapp_web_playwright() -> str:
    if os.getenv("YOUAI_WHATSAPP_WEB", "").strip() not in ("1", "true", "yes"):
        return ""

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return (
            "[WHATSAPP] YOUAI_WHATSAPP_WEB=1 but playwright is not installed. "
            "Run: pip install playwright && playwright install chromium\n"
        )

    lines: List[str] = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        try:
            page = browser.new_page()
            page.goto("https://web.whatsapp.com/", wait_until="domcontentloaded")
            try:
                page.wait_for_selector('[data-testid="chat-list"]', timeout=300_000)
            except Exception as e:
                return f"[WHATSAPP] Timed out waiting for login (QR scan or chat list): {e}\n"
            page.wait_for_timeout(2500)
            # Try multiple selectors; WhatsApp Web DOM changes often.
            for sel in (
                '[data-testid="msg-container"]',
                '[data-testid="conversation-panel-messages"] span',
                "div[role='row']",
            ):
                try:
                    loc = page.locator(sel)
                    n = loc.count()
                    for i in range(max(0, n - 120), n):
                        t = loc.nth(i).inner_text()
                        if t and len(t.strip()) > 1:
                            lines.append(re.sub(r"\s+", " ", t.strip())[:800])
                except Exception:
                    continue
                if len(lines) >= 20:
                    break
        finally:
            browser.close()

    if not lines:
        return (
            "[WHATSAPP] Session opened but no message text was extracted. "
            "Try exporting a chat from WhatsApp on your phone and set YOUAI_WHATSAPP_EXPORT_PATH.\n"
        )
    dedup = []
    seen = set()
    for L in lines:
        if L not in seen:
            seen.add(L)
            dedup.append(L)
    sample = "\n".join(f"  {x}" for x in dedup[:100])
    return f"[WHATSAPP_WEB] Recent message samples (style / wording):\n{sample}\n"


def collect_whatsapp_context() -> str:
    """Combined WhatsApp block for Info_get raw_context."""
    parts = []
    parts.append(collect_whatsapp_export_text())
    if os.getenv("YOUAI_WHATSAPP_WEB", "").strip() in ("1", "true", "yes"):
        parts.append(collect_whatsapp_web_playwright())
    return "\n".join(x for x in parts if x)
