import json
import os
from datetime import datetime
from typing import Dict, List, Optional

from tools.priority_gate import PriorityGate
from tools.social_router import SocialRouter


class ExecutiveScheduler:
    """
    Schedules and executes social automation actions.
    Supports delayed sending and high-priority confirmation gate.
    """

    def __init__(self, store_file: str):
        self.store_file = store_file
        self.router = SocialRouter()
        self.gate = PriorityGate()
        self.actions: List[Dict] = []
        self._load()

    def _load(self) -> None:
        if not os.path.exists(self.store_file):
            self.actions = []
            return
        try:
            with open(self.store_file, "r", encoding="utf-8") as f:
                self.actions = json.load(f)
        except Exception:
            self.actions = []

    def _save(self) -> None:
        os.makedirs(os.path.dirname(self.store_file), exist_ok=True)
        with open(self.store_file, "w", encoding="utf-8") as f:
            json.dump(self.actions, f, ensure_ascii=False, indent=2)

    def schedule_message(
        self,
        platform: str,
        to: str,
        message: str,
        send_at: str,
        created_by: str = "user",
    ) -> Dict:
        score, reason = self.gate.score(
            {"type": "scheduled_message", "platform": platform, "to": to, "message": message}
        )
        action = {
            "id": f"act_{int(datetime.now().timestamp() * 1000)}",
            "type": "scheduled_message",
            "platform": platform.lower(),
            "to": to,
            "message": message,
            "send_at": send_at,
            "status": "pending_approval" if score > 7 else "scheduled",
            "priority_score": score,
            "priority_reason": reason,
            "created_by": created_by,
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "last_error": "",
        }
        self.actions.append(action)
        self._save()
        return action

    def schedule_api_call(
        self,
        platform: str,
        method: str,
        params: Dict,
        send_at: str,
        created_by: str = "user",
    ) -> Dict:
        score, reason = self.gate.score(
            {
                "type": "scheduled_api_call",
                "platform": platform,
                "to": params.get("to", ""),
                "message": str(params),
            }
        )
        action = {
            "id": f"act_{int(datetime.now().timestamp() * 1000)}",
            "type": "scheduled_api_call",
            "platform": platform.lower(),
            "method": method,
            "params": params,
            "send_at": send_at,
            "status": "pending_approval" if score > 7 else "scheduled",
            "priority_score": score,
            "priority_reason": reason,
            "created_by": created_by,
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "last_error": "",
        }
        self.actions.append(action)
        self._save()
        return action

    def approve(self, action_id: str, approved: bool) -> Optional[Dict]:
        for action in self.actions:
            if action["id"] == action_id and action["status"] == "pending_approval":
                action["status"] = "scheduled" if approved else "cancelled"
                self._save()
                return action
        return None

    def request_direct_message(
        self,
        platform: str,
        to: str,
        message: str,
        created_by: str = "user",
    ) -> Dict:
        """
        Create an immediate-send action that ALWAYS requires approval first.
        This is the safe path for "act as me on social media" interactions.
        """
        score, reason = self.gate.score(
            {"type": "direct_message", "platform": platform, "to": to, "message": message}
        )
        action = {
            "id": f"act_{int(datetime.now().timestamp() * 1000)}",
            "type": "scheduled_message",
            "platform": platform.lower(),
            "to": to,
            "message": message,
            "send_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "status": "pending_approval",
            "priority_score": max(8, score),
            "priority_reason": reason or "Direct social interaction requires explicit approval",
            "created_by": created_by,
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "last_error": "",
        }
        self.actions.append(action)
        self._save()
        return action

    def list_actions(self, include_done: bool = False) -> List[Dict]:
        if include_done:
            return list(self.actions)
        return [a for a in self.actions if a["status"] not in {"sent", "cancelled"}]

    def process_due_actions(self) -> List[Dict]:
        now = datetime.now()
        processed = []
        changed = False

        for action in self.actions:
            if action.get("status") != "scheduled":
                continue
            try:
                due_at = datetime.strptime(action["send_at"], "%Y-%m-%d %H:%M")
            except Exception:
                action["status"] = "failed"
                action["last_error"] = "Invalid date format. Use YYYY-MM-DD HH:MM"
                changed = True
                continue

            if now < due_at:
                continue

            if action.get("type") == "scheduled_api_call":
                result = self.router.execute(
                    action["platform"],
                    action["method"],
                    action.get("params", {}),
                )
            else:
                result = self.router.send(action["platform"], action["to"], action["message"])
            if result.get("success"):
                action["status"] = "sent"
                action["sent_at"] = now.strftime("%Y-%m-%d %H:%M:%S")
            else:
                action["status"] = "failed"
                action["last_error"] = result.get("error", "unknown error")
            processed.append(action)
            changed = True

        if changed:
            self._save()
        return processed

