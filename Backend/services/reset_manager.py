#!/usr/bin/env python3
"""
reset_manager.py — YouAI Reset Manager
========================================
Handles full application and memory resets for the YouAI Digital Twin.

Usage:
    py -m Backend.services.reset_manager app       # wipe all memory files (.db, .json, .enc)
    py -m Backend.services.reset_manager memory    # wipe all DB memory rows (keep files)
    py -m Backend.services.reset_manager full      # full reset (files + rows)
"""

import os
import glob
import time
import sys


ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)


# ---------------------------------------------------------------------------
# File-level reset
# ---------------------------------------------------------------------------

def reset_memory_files() -> int:
    """
    Deletes all .db, .json, and .enc files inside Backend/memory/.
    Returns the number of deleted files.
    """
    print("=" * 56)
    print("  WARNING: This will destroy all memory files.")
    print("  Stored identity, profiles, and keys will be lost.")
    print("=" * 56)

    confirm = input("Type YES to confirm file deletion: ").strip()
    if confirm != "YES":
        print("Aborted.")
        return 0

    memory_dir = os.path.join(ROOT, "Backend", "memory")
    patterns = [
        os.path.join(memory_dir, "*.db"),
        os.path.join(memory_dir, "*.json"),
        os.path.join(memory_dir, "*.enc"),
    ]

    targets = []
    for pat in patterns:
        targets.extend(glob.glob(pat))

    deleted = 0
    for path in targets:
        try:
            os.remove(path)
            print(f"  [DELETED] {path}")
            deleted += 1
        except Exception as exc:
            print(f"  [FAILED]  {path}: {exc}")

    print("=" * 56)
    if deleted:
        print(f"  Done. {deleted} memory file(s) removed.")
        print("  Run 'python Start.py' to start fresh.")
    else:
        print("  Nothing to delete — memory is already clean.")
    time.sleep(1)
    return deleted


# ---------------------------------------------------------------------------
# Row-level reset (wipes DB rows, keeps encryption key)
# ---------------------------------------------------------------------------

def reset_memory_rows(include_vault: bool = False) -> dict:
    """
    Wipes all rows from every cognitive-vector table in the memory DB.
    The database file and encryption key are preserved.

    Args:
        include_vault: If True, also wipes the connected_user_vault table.

    Returns:
        Dict mapping table_name -> rows deleted.
    """
    print("=" * 56)
    print("  WARNING: This will erase all stored personality data.")
    print("  The database FILE is kept but all rows will be deleted.")
    print("=" * 56)

    confirm = input("Type YES to confirm memory row wipe: ").strip()
    if confirm != "YES":
        print("Aborted.")
        return {}

    try:
        from Backend.memory.memory_management import GiantMemoryManager
        db = GiantMemoryManager()
        stats = db.wipe_all_memory_tables(include_vault=include_vault)

        total = sum(v for v in stats.values() if v > 0)
        print(f"\n  [DONE] {total} row(s) deleted across {len(stats)} table(s).")
        for tbl, count in stats.items():
            if count > 0:
                print(f"    - {tbl}: {count} row(s)")
        return stats
    except Exception as exc:
        print(f"  [ERROR] Could not access database: {exc}")
        return {}


# ---------------------------------------------------------------------------
# Full reset
# ---------------------------------------------------------------------------

def full_reset():
    """Performs both file-level and row-level resets."""
    print("\n=== FULL RESET: Rows first, then files ===\n")
    reset_memory_rows(include_vault=True)
    reset_memory_files()


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main():
    args = sys.argv[1:]
    mode = args[0].lower() if args else "help"

    if mode == "app":
        reset_memory_files()
    elif mode == "memory":
        reset_memory_rows()
    elif mode == "full":
        full_reset()
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
