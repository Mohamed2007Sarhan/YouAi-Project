import json
import os
from collections import deque
from datetime import datetime
from typing import Deque, Dict, List


class ShortMemory:
    """
    Small rolling memory buffer for near-term intent.
    Keeps the last N user/assistant events and persists to disk.
    """

    def __init__(self, file_path: str, max_items: int = 40):
        self.file_path = file_path
        self.max_items = max_items
        self.buffer: Deque[Dict] = deque(maxlen=max_items)
        self._load()

    def _load(self) -> None:
        if not os.path.exists(self.file_path):
            return
        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            for item in data[-self.max_items:]:
                self.buffer.append(item)
        except Exception:
            self.buffer.clear()

    def _save(self) -> None:
        os.makedirs(os.path.dirname(self.file_path), exist_ok=True)
        with open(self.file_path, "w", encoding="utf-8") as f:
            json.dump(list(self.buffer), f, ensure_ascii=False, indent=2)

    def add(self, role: str, content: str) -> None:
        self.buffer.append(
            {
                "role": role,
                "content": content,
                "ts": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }
        )
        self._save()

    def context_block(self, limit: int = 8) -> str:
        items: List[Dict] = list(self.buffer)[-limit:]
        if not items:
            return "Short-memory is empty."
        lines = ["Recent short-memory context:"]
        for item in items:
            lines.append(f"- [{item['ts']}] {item['role']}: {item['content']}")
        return "\n".join(lines)

