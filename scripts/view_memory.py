#!/usr/bin/env python3
"""
scripts/view_memory.py — YouAI Memory Inspector
================================================
Shows everything stored in ai_giant_memory.db and short_memory.json.
Run from the project root directory.

Usage:
    py scripts/view_memory.py              # full dump
    py scripts/view_memory.py --stats      # coverage summary only
    py scripts/view_memory.py --short      # short-term memory only
    py scripts/view_memory.py --table personal_identity   # single table
"""

import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Resolve project root (two levels up from scripts/)
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# ── ANSI colours ──────────────────────────────────────────────────────────
def _c(code): return f"\033[{code}m"
RESET   = _c(0);  BOLD = _c(1);  DIM  = _c(2)
CYAN    = _c(96); GREEN = _c(92); YELLOW = _c(93)
RED     = _c(91); MAGENTA = _c(95); WHITE = _c(97)


def bar(filled: int, total: int, width: int = 28) -> str:
    """Render an ASCII progress bar for memory coverage."""
    pct  = filled / max(total, 1)
    done = int(pct * width)
    color = GREEN if pct >= 0.8 else YELLOW if pct >= 0.4 else RED
    return (
        f"{GREEN}{'█' * done}{DIM}{'░' * (width - done)}{RESET}"
        f"  {color}{filled}/{total} ({pct*100:.0f}%){RESET}"
    )


def _fmt(record: dict) -> str:
    """Format a single DB row into a human-readable string."""
    skip = {"id", "created_at", "updated_at", "importance", "is_archived"}
    lines = []
    for k, v in record.items():
        if k in skip or not v or str(v).lower() in ("", "[]", "none", "null"):
            continue
        try:
            parsed = json.loads(v)
            if isinstance(parsed, list):
                v = ", ".join(str(x) for x in parsed)
        except Exception:
            pass
        lines.append(f"    {CYAN}{k.replace('_', ' ').title()}{RESET}: {v}")
    return "\n".join(lines) or f"    {DIM}(all fields empty){RESET}"


def _divider(char: str = "=", n: int = 64, color: str = CYAN) -> None:
    print(f"{color}{char * n}{RESET}")


# ── DB dump ───────────────────────────────────────────────────────────────

def dump_db(filter_table: str = None, stats_only: bool = False) -> None:
    """Print all memory tables or a single table from the main DB."""
    try:
        from Backend.memory.persona_builder   import CATEGORY_LABELS
        from Backend.memory.memory_management import GiantMemoryManager
        from Backend.memory.memory_schema     import SCHEMA_MAPPING
    except ImportError as e:
        print(f"{RED}Import error: {e}{RESET}")
        sys.exit(1)

    try:
        db = GiantMemoryManager()
    except Exception as e:
        print(f"{RED}Cannot open database: {e}{RESET}")
        sys.exit(1)

    tables    = [filter_table] if filter_table else list(SCHEMA_MAPPING.keys())
    filled    = 0
    total     = len(SCHEMA_MAPPING)
    empty_lst = []

    for tbl in tables:
        try:
            records = db.get_records(tbl, min_importance=1)
        except Exception as e:
            print(f"\n{RED}[{tbl}] ERROR: {e}{RESET}")
            continue

        if not records:
            empty_lst.append(tbl)
            if not stats_only:
                label = CATEGORY_LABELS.get(tbl, tbl)
                print(f"\n{DIM}{'─'*64}\n  {YELLOW}{label}{RESET}  ({DIM}{tbl}{RESET})\n  {DIM}(empty){RESET}")
            continue

        filled += 1
        if stats_only:
            continue

        label = CATEGORY_LABELS.get(tbl, tbl)
        _divider()
        print(f"{BOLD}{WHITE}  {label}  {DIM}({tbl}){RESET}")
        _divider()
        for i, rec in enumerate(records, 1):
            imp = rec.get("importance", "?")
            rid = rec.get("id", "?")
            ts  = rec.get("created_at", "")[:16]
            print(f"\n  {MAGENTA}[row #{i}]{RESET}  id={rid}  importance={imp}  {DIM}{ts}{RESET}")
            print(_fmt(rec))

    print(f"\n{BOLD}{'='*64}")
    print(f"  DATABASE COVERAGE")
    print(f"{'='*64}{RESET}")
    print(f"  {bar(filled, total)}")
    if empty_lst and not filter_table:
        print(f"\n  {YELLOW}Empty categories ({len(empty_lst)}):{RESET}")
        for t in empty_lst:
            lbl = CATEGORY_LABELS.get(t, t)
            print(f"    {DIM}- {lbl} ({t}){RESET}")
    print(f"\n{'='*64}\n")


def dump_short_memory() -> None:
    """Print all entries from the short-term memory JSON file."""
    sm_path = os.path.join(ROOT, "logs", "short_memory.json")
    if not os.path.exists(sm_path):
        print(f"{YELLOW}short_memory.json not found at {sm_path}{RESET}")
        return

    try:
        items = json.loads(open(sm_path, encoding="utf-8").read())
    except Exception as e:
        print(f"{RED}Cannot read short_memory.json: {e}{RESET}")
        return

    _divider(char="=", color=MAGENTA)
    print(f"{BOLD}{MAGENTA}  SHORT-TERM MEMORY  ({len(items)} entries){RESET}")
    _divider(char="=", color=MAGENTA)

    role_colors = {
        "user_style_sample": CYAN,
        "deep_user_answer":  GREEN,
        "deep_setup_table":  YELLOW,
        "style_similarity":  MAGENTA,
        "system":            DIM,
    }
    for i, item in enumerate(items, 1):
        role    = item.get("role", "?")
        content = item.get("content", "")
        ts      = item.get("ts", "")[:16]
        color   = role_colors.get(role, WHITE)
        preview = content.replace("\n", " | ")[:200]
        if len(content) > 200:
            preview += f"  {DIM}... (+{len(content)-200} chars){RESET}"
        print(f"\n  {color}[{i:02d}] {role}{RESET}  {DIM}{ts}{RESET}")
        print(f"  {preview}")

    print(f"\n{MAGENTA}{'='*64}{RESET}\n")


# ── Entry point ───────────────────────────────────────────────────────────

def main() -> None:
    args       = sys.argv[1:]
    stats_only = "--stats" in args
    short_only = "--short" in args
    tbl_arg    = None

    if "--table" in args:
        idx = args.index("--table")
        if idx + 1 < len(args):
            tbl_arg = args[idx + 1]

    print(f"\n{BOLD}{CYAN}{'='*64}")
    print(f"  YouAI Memory Inspector")
    print(f"{'='*64}{RESET}\n")

    if not short_only:
        dump_db(filter_table=tbl_arg, stats_only=stats_only)

    if not stats_only and not tbl_arg:
        dump_short_memory()


if __name__ == "__main__":
    main()
