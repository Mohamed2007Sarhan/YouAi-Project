#!/usr/bin/env python3
"""
scripts/db_utils.py — YouAI Database Utility
=============================================
Manually read or write any field in the YouAI memory database.
Run from the project root directory.

Usage:
    py scripts/db_utils.py set personal_identity age 30
    py scripts/db_utils.py set personal_identity name "Mohamed Sarhan"
    py scripts/db_utils.py get personal_identity
    py scripts/db_utils.py wipe              # wipe ALL memory rows (irreversible!)
"""

import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Resolve project root (two levels up from scripts/)
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from Backend.memory.memory_management import GiantMemoryManager

db = GiantMemoryManager()


def cmd_set(table: str, field: str, value: str) -> None:
    """Update or insert a field value in the given memory table."""
    rows = db.get_records(table, min_importance=1)
    if rows:
        rec_id = rows[0]["id"]
        db.update_record(table, rec_id, {field: value})
        print(f"[set] Updated {table} row #{rec_id}  ->  {field} = {value!r}")
    else:
        db.insert_record(table, {field: value, "importance": 1})
        print(f"[set] Inserted new {table} row  ->  {field} = {value!r}")
    cmd_get(table)


def cmd_get(table: str) -> None:
    """Print all non-empty fields for every row in the given memory table."""
    rows = db.get_records(table, min_importance=1)
    if not rows:
        print(f"[get] {table}: (empty)")
        return
    for r in rows:
        data = {
            k: v for k, v in r.items()
            if k not in ("created_at", "updated_at", "is_archived") and v
        }
        print(f"[get] {table} row #{r['id']}: {data}")


def cmd_wipe() -> None:
    """Wipe ALL memory rows from the database (irreversible)."""
    confirm = input("Type YES to wipe ALL memory rows: ")
    if confirm.strip() == "YES":
        stats = db.wipe_all_memory_tables()
        deleted = sum(v for v in stats.values() if v > 0)
        print(f"[wipe] Done. {deleted} rows deleted across {len(stats)} tables.")
    else:
        print("[wipe] Cancelled.")


def main() -> None:
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        return

    cmd = args[0].lower()

    if cmd == "set" and len(args) >= 4:
        cmd_set(args[1], args[2], args[3])
    elif cmd == "get" and len(args) >= 2:
        cmd_get(args[1])
    elif cmd == "wipe":
        cmd_wipe()
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
