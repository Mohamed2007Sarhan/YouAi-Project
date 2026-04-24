"""
Memory Library API (SDK)
This acts as the secure, abstracted library access point for the rest of the project.
It encapsulates the GiantMemoryManager and protects direct database or encryption keys.

Usage:
    import library as memory
    memory.add("personal_identity", {"name": "Mohamed", "age": "30"})
    records = memory.read("personal_identity")
"""

from typing import Dict, List, Any
try:
    from memory_management import GiantMemoryManager
except ImportError:
    from .memory_management import GiantMemoryManager

# Singleton instance of the engine
_engine = GiantMemoryManager()


def add(category_table: str, data: Dict[str, Any], importance: int = 1) -> int:
    """
    Inserts a new piece of memory into the memory bank securely.
    Args:
        category_table: Name of the table (e.g. 'financial_memory')
        data: Dictionary matching the table's structure. Unrecognized keys are ignored.
        importance: 1 (Low) to 3 (High). Useful for keeping memories alive.
    Returns:
        The integer ID of the newly saved record.
    """
    data["importance"] = importance
    return _engine.insert_record(category_table, data)


def read(category_table: str, min_importance: int = 1, include_archived: bool = False) -> List[Dict[str, Any]]:
    """
    Retrieves and completely decrypts memory records into dictionary format.
    Args:
        category_table: Target memory bank.
        min_importance: Filtering constraint.
        include_archived: Whether to fetch forgotten/archived memories.
    """
    return _engine.get_records(category_table, min_importance, include_archived)


def update(category_table: str, record_id: int, updated_data: Dict[str, Any]) -> bool:
    """
    Updates specific attributes within an existing memory record, completely re-encrypting it.
    """
    return _engine.update_record(category_table, record_id, updated_data)


def delete(category_table: str, record_id: int) -> bool:
    """
    Permanently erases a memory pointer from the database.
    """
    return _engine.delete_record(category_table, record_id)


def create_new_collection(category_table: str, personal_columns: List[str]) -> bool:
    """
    Allows the AI to dynamically invent new memory schemas on the fly!
    E.g., create_new_collection("health_history", ["heart_rate_avg", "dietally_restrictions"])
    """
    return _engine.create_custom_table(category_table, personal_columns)


def fetch_all_collections() -> List[str]:
    """
    Returns a list of all 25+ tables/collections registered in the brain.
    """
    return _engine.get_all_tables()


def clean_mind(older_than_days: int = 60, max_importance: int = 1) -> Dict[str, int]:
    """
    Executes the 'Forgetting System' across the entire brain.
    Returns:
        Dictionary illustrating how many trivial memories were deleted per table.
    """
    return _engine.scrub_entire_system(older_than_days, max_importance)

# ------------- TEST VERIFICATION -------------
if __name__ == "__main__":
    print("--- Library SDK Testing ---")
    
    print("[+] Creating a completely custom AI-Generated table on the fly...")
    create_new_collection("ai_dream_log", ["dream_title", "subconscious_meaning", "lucidity_level"])
    
    print("[+] Writing an encrypted dream...")
    add("ai_dream_log", {
        "dream_title": "Flying over the digital grid",
        "subconscious_meaning": "Striving for higher abstract system view",
        "lucidity_level": "99%"
    }, importance=2)
    
    print("[+] Retrieving encrypted dream...")
    dreams = read("ai_dream_log")
    for d in dreams:
        print(f" -> Found Dream (Decrypted): {d}")
        
    print("\n[+] Testing Full CRUD on Personal Identity")
    p_id = add("personal_identity", {"name": "Test User", "skills": "Basic CRUD"})
    print(f" -> Created ID: {p_id}")
    
    update("personal_identity", p_id, {"skills": "Expert Python AI Mastery"})
    print(" -> Updated successfully.")
    
    print(f" -> Content after Update: {read('personal_identity')}")
    
    delete("personal_identity", p_id)
    print(" -> Deleted successfully.")
    
    print("[+] All tables recognized automatically by the library:")
    print(" ->", fetch_all_collections())
    
    print("--- Library Secure API Confirmed Operational ---")
