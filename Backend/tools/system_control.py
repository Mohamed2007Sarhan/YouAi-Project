import subprocess
import os
import sys

def execute_os_command(command: str) -> str:
    """Execute arbitrary OS command in shell (CMD/Powershell compatible)"""
    try:
        result = subprocess.run(
            command, shell=True, capture_output=True, text=True, timeout=30
        )
        output = result.stdout.strip()
        err = result.stderr.strip()
        if err and not output:
            return f"[ERROR] {err}"
        if err:
            return f"[OUTPUT] {output}\n[ERROR] {err}"
        return f"[OUTPUT] {output}" if output else "[SUCCESS] Command executed with no output."
    except Exception as e:
        return f"[FATAL ERROR] {str(e)}"

def read_code_file(path: str) -> str:
    """Read a file for self-healing purposes."""
    try:
        if not os.path.exists(path):
            return f"[ERROR] File not found: {path}"
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        return f"[ERROR] {str(e)}"

def write_code_file(path: str, content: str) -> str:
    """Write/Overwrite a file completely for self-healing purposes. Creates a backup first."""
    try:
        if os.path.exists(path):
            import shutil
            shutil.copyfile(path, path + ".backup")
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return f"[SUCCESS] File {path} successfully updated. (Backup created: {path}.backup)"
    except Exception as e:
        return f"[ERROR] {str(e)}"

def get_system_tools_prompt_injection() -> str:
    return (
        "--- FULL PC CONTROL & SELF-HEALING CAPABILITIES ---\n"
        "You have full administrative control over this Windows PC and your own source code.\n"
        "To execute a command, you MUST use one of these syntaxes on a new line in your response:\n"
        "1. To run any OS command (open apps, navigate, shutdown, etc): `/os_cmd <command>`\n"
        "   Example: `/os_cmd start winword` or `/os_cmd echo Hello`\n"
        "2. To READ a file (e.g. to inspect your own code if an error happened): `/read_file <filepath>`\n"
        "   Example: `/read_file main.py`\n"
        "3. To OVERWRITE a file entirely (Self-Healing): `/write_file <filepath>\n```python\n<full_content>\n````\n"
        "   (Ensure you output the full new content inside the backticks block exactly after the command).\n\n"
        "--- AI MEMORY SELF-HEALING & CORRECTION ---\n"
        "If the user tells you that a fact about them is wrong or you need to update/delete/insert a personal memory, YOU MUST use these commands:\n"
        "1. `/memory_search <keyword>` (Search user's memory database tables for rows containing keyword, to find their IDs)\n"
        "2. `/memory_update <table_name> | <row_id> | <json_data>` (Update specific row ID in a table with a generic valid JSON dict)\n"
        "3. `/memory_insert <table_name> | <json_data>` (Add a new row into the specified table using JSON dict)\n"
        "4. `/memory_delete <table_name> | <row_id>` (Delete a specific row ID from a table)\n"
        "Available core tables: identity, communication_memory, values_principles, goals_intentions, emotional_patterns, habit_system, knowledge_learning.\n\n"
        "Safety Protocol: The user will be prompted to approve OS commands, but you should still use them when they ask for system automation or when you need to self-repair.\n"
        "If you encounter an issue or bug, YOU ARE EXPECTED to use /read_file to see the file, then /write_file to fix it.\n"
    )
