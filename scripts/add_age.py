#!/usr/bin/env python3
"""
scripts/add_age.py — YouAI Quick Age Updater
=============================================
Directly update the `age` field in the personal_identity memory table.
Run from the project root directory.

Usage:
    py scripts/add_age.py 30
    py scripts/add_age.py 25
"""
import sys
import os

sys.stdout.reconfigure(encoding="utf-8")

if len(sys.argv) < 2:
    print("Usage: py scripts/add_age.py <age>")
    print("Example: py scripts/add_age.py 30")
    sys.exit(1)

age_val = sys.argv[1].strip()

# Resolve project root (two levels up from scripts/)
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from Backend.memory.memory_management import GiantMemoryManager

db = GiantMemoryManager()

# Check for an existing personal_identity row and update or insert
rows = db.get_records("personal_identity", min_importance=1)
if rows:
    rec_id = rows[0]["id"]
    db.update_record("personal_identity", rec_id, {"age": age_val})
    print(f"[add_age] Updated personal_identity row #{rec_id} -> age = '{age_val}'")
else:
    db.insert_record("personal_identity", {"age": age_val, "importance": 1})
    print(f"[add_age] Inserted new personal_identity row -> age = '{age_val}'")

# Verify
rows = db.get_records("personal_identity", min_importance=1)
for r in rows:
    print(
        f"  Row #{r['id']}: "
        f"name={r.get('name', '')!r}  "
        f"age={r.get('age', '')!r}  "
        f"profession={r.get('profession', '')!r}"
    )
