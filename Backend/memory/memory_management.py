import os
import sqlite3
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from pathlib import Path
from dataclasses import fields

from cryptography.fernet import Fernet
from dotenv import load_dotenv, set_key

try:
    from memory_schema import SCHEMA_MAPPING
except ImportError:
    # Safe fallback if run independently
    from .memory_schema import SCHEMA_MAPPING

# Core standard columns that remain unencrypted for fast DB querying
STANDARD_UNENCRYPTED_COLUMNS = ["id", "created_at", "updated_at", "importance", "is_archived"]

class GiantMemoryManager:
    """
    Core Database Engine for the AI Memory.
    Provides bulletproof Column-Level Encryption, Full CRUD, and Dynamic Table Mapping.
    """
    
    def __init__(self, db_path: str = "ai_giant_memory.db", env_path: str = ".env.memory"):
        self.db_dir = Path(os.path.dirname(os.path.abspath(__file__)))
        self.db_file_path = self.db_dir / db_path
        self.env_file_path = self.db_dir / env_path
        
        self.fernet = self._setup_encryption()
        self._setup_default_tables()
        self._fix_importance_floor()

    def _setup_encryption(self) -> Fernet:
        """Bootstraps the Fernet symmetric encryption engine securely via .env."""
        load_dotenv(dotenv_path=self.env_file_path)
        key = os.getenv("MEMORY_ENCRYPTION_KEY")
        
        if not key:
            print("[SECURITY] Generating new master encryption key for subsystem...")
            key = Fernet.generate_key().decode('utf-8')
            if not self.env_file_path.exists():
                self.env_file_path.touch()
            set_key(str(self.env_file_path), "MEMORY_ENCRYPTION_KEY", key)
            
        return Fernet(key.encode('utf-8'))

    def _get_connection(self) -> sqlite3.Connection:
        """Returns SQLite connection with dict-like row access."""
        conn = sqlite3.connect(self.db_file_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _get_table_columns(self, table_name: str) -> List[str]:
        """Introspects SQLite to get actual columns of a table."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f"PRAGMA table_info({table_name})")
            columns = [info["name"] for info in cursor.fetchall()]
            if not columns:
                raise ValueError(f"Table '{table_name}' does not exist.")
            return columns

    def _setup_default_tables(self) -> None:
        """Ensures the core 25 cognitive vectors exist upon startup."""
        for table_name, schema_cls in SCHEMA_MAPPING.items():
            cols = [f.name for f in fields(schema_cls) if f.name not in ("importance", "is_archived")]
            self.create_custom_table(table_name, cols)

    # -----------------------------------------------------------------------
    # DB Table Manipulation
    # -----------------------------------------------------------------------
    def create_custom_table(self, table_name: str, custom_columns: List[str]) -> bool:
        """
        Dynamically generates a new memory collection table on the fly.
        """
        table_name = table_name.lower().replace(" ", "_")
        col_defs = [
            "id INTEGER PRIMARY KEY AUTOINCREMENT",
            "created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
            "updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
            "importance INTEGER DEFAULT 1",
            "is_archived INTEGER DEFAULT 0"
        ]
        
        for col_name in custom_columns:
            # All custom data vectors are purely treated as BLOBs to hold Fernet bytes
            if col_name not in STANDARD_UNENCRYPTED_COLUMNS:
                col_defs.append(f"{col_name} BLOB")
                
        create_stmt = f"CREATE TABLE IF NOT EXISTS {table_name} (\n    {', '.join(col_defs)}\n)"
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(create_stmt)
            conn.commit()
            return True

    def _fix_importance_floor(self) -> None:
        """
        Repair rows where importance was stored as 0 (e.g. from LLM JSON).
        Persona and UI queries use min_importance=1 and would otherwise see empty tables.
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            for table_name in SCHEMA_MAPPING.keys():
                try:
                    cursor.execute(
                        f"UPDATE {table_name} SET importance = 1 WHERE importance < 1"
                    )
                except sqlite3.OperationalError:
                    pass
            conn.commit()

    def get_all_tables(self) -> List[str]:
        """Returns a list of all tables currently registered in the Memory DB."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            return [row["name"] for row in cursor.fetchall() if row["name"] != "sqlite_sequence"]

    # -----------------------------------------------------------------------
    # Column-Level Cryptography
    # -----------------------------------------------------------------------
    def _encrypt_val(self, val: Any) -> bytes:
        if val is None:
            val = ""
        str_val = str(val) if not isinstance(val, (dict, list)) else json.dumps(val)
        return self.fernet.encrypt(str_val.encode('utf-8'))

    def _decrypt_val(self, encrypted_bytes: bytes) -> str:
        if not encrypted_bytes:
            return ""
        try:
            return self.fernet.decrypt(encrypted_bytes).decode('utf-8')
        except Exception:
            return "<DECRYPTION_ERROR_OR_CORRUPT>"

    # -----------------------------------------------------------------------
    # Giant CRUD Engine (Create, Read, Update, Delete)
    # -----------------------------------------------------------------------
    def insert_record(self, table_name: str, record_data: Dict[str, Any]) -> int:
        valid_cols = self._get_table_columns(table_name)
        
        insert_cols = []
        insert_vals = []
        
        for col_name, val in record_data.items():
            if col_name not in valid_cols or col_name in ("id", "created_at", "updated_at"):
                continue
                
            insert_cols.append(col_name)
            if col_name in STANDARD_UNENCRYPTED_COLUMNS:
                if col_name == "importance":
                    try:
                        iv = int(val) if val is not None and str(val).strip() != "" else 1
                    except (TypeError, ValueError):
                        iv = 1
                    # LLM JSON often sends 0; get_records(min_importance=1) would hide those rows
                    insert_vals.append(max(1, min(3, iv)))
                elif col_name == "is_archived":
                    insert_vals.append(int(val) if val else 0)
                else:
                    insert_vals.append(int(val) if val else 0)
            else:
                insert_vals.append(self._encrypt_val(val))
                
        placeholders = ", ".join(["?"] * len(insert_vals))
        col_names_str = ", ".join(insert_cols)
        
        sql = f"INSERT INTO {table_name} ({col_names_str}) VALUES ({placeholders})"
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, tuple(insert_vals))
            conn.commit()
            return cursor.lastrowid

    def get_records(self, table_name: str, min_importance: int = 1, include_archived: bool = False) -> List[Dict[str, Any]]:
        valid_cols = self._get_table_columns(table_name)
        
        query = f"SELECT * FROM {table_name} WHERE importance >= ?"
        params = [min_importance]
        
        if not include_archived:
            query += " AND is_archived = 0"
        query += " ORDER BY created_at DESC"
        
        results = []
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, tuple(params))
            rows = cursor.fetchall()
            
            for row in rows:
                decrypted_obj = {}
                for f_name in valid_cols:
                    if f_name in STANDARD_UNENCRYPTED_COLUMNS:
                        decrypted_obj[f_name] = row[f_name]
                    else:
                        decrypted_obj[f_name] = self._decrypt_val(row[f_name])
                results.append(decrypted_obj)
        return results

    def update_record(self, table_name: str, record_id: int, updated_data: Dict[str, Any]) -> bool:
        valid_cols = self._get_table_columns(table_name)
        set_clauses = []
        update_vals = []
        
        timestamp = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
        set_clauses.append("updated_at = ?")
        update_vals.append(timestamp)
        
        for col_name, val in updated_data.items():
            if col_name not in valid_cols or col_name in ("id", "created_at", "updated_at"):
                continue
                
            set_clauses.append(f"{col_name} = ?")
            if col_name in STANDARD_UNENCRYPTED_COLUMNS:
                if col_name == "importance":
                    try:
                        iv = int(val) if val is not None and str(val).strip() != "" else 1
                    except (TypeError, ValueError):
                        iv = 1
                    update_vals.append(max(1, min(3, iv)))
                elif col_name == "is_archived":
                    update_vals.append(int(val) if val else 0)
                else:
                    update_vals.append(int(val) if val else 0)
            else:
                update_vals.append(self._encrypt_val(val))
                
        if len(set_clauses) == 1:
            return False # Nothing to update
            
        update_vals.append(record_id)
        sql = f"UPDATE {table_name} SET {', '.join(set_clauses)} WHERE id = ?"
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, tuple(update_vals))
            conn.commit()
            return cursor.rowcount > 0

    def delete_record(self, table_name: str, record_id: int) -> bool:
        """Permanently deletes a specific memory."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f"DELETE FROM {table_name} WHERE id = ?", (record_id,))
            conn.commit()
            return cursor.rowcount > 0

    def wipe_all_memory_tables(self, include_vault: bool = False) -> dict:
        """
        Deletes all rows from every SCHEMA_MAPPING table (full reset of digital-twin profile data).
        Linked accounts in connected_user_vault are kept unless include_vault=True.
        Returns table_name -> rows deleted (or -1 on error).
        """
        stats: Dict[str, int] = {}
        with self._get_connection() as conn:
            cursor = conn.cursor()
            for table_name in SCHEMA_MAPPING.keys():
                try:
                    cursor.execute(f"DELETE FROM {table_name}")
                    stats[table_name] = cursor.rowcount
                except sqlite3.OperationalError:
                    stats[table_name] = -1
            if include_vault:
                try:
                    cursor.execute("DELETE FROM connected_user_vault")
                    stats["connected_user_vault"] = cursor.rowcount
                except sqlite3.OperationalError:
                    pass
            conn.commit()
        return stats

    # -----------------------------------------------------------------------
    # System Optimization
    # -----------------------------------------------------------------------
    def scrub_entire_system(self, older_than_days: int = 60, max_importance: int = 1) -> dict:
        """Global Memory Forgetting Process (Garbage Collection of trivial old memories)"""
        cutoff_date = (datetime.utcnow() - timedelta(days=older_than_days)).strftime('%Y-%m-%d %H:%M:%S')
        stats = {}
        all_tables = self.get_all_tables()
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            for table_name in all_tables:
                # We expect standard unencrypted columns exist like importance, created_at
                try:
                    cursor.execute(f"DELETE FROM {table_name} WHERE importance <= ? AND created_at < ?", 
                                   (max_importance, cutoff_date))
                    if cursor.rowcount > 0:
                        stats[table_name] = cursor.rowcount
                except sqlite3.OperationalError:
                    pass # Custom table might not follow rules
            conn.commit()
        return stats
