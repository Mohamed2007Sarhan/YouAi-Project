import os
import sys
import inspect
import importlib
from typing import Any, Dict, List, Optional


PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PUBLIC_APIS = os.path.join(PROJECT_ROOT, "Public Apis")
if PUBLIC_APIS not in sys.path:
    sys.path.insert(0, PUBLIC_APIS)

try:
    from whatsapp_business import WhatsAppClient
except Exception:
    WhatsAppClient = None

try:
    from telegram_bot import TelegramBotClient
except Exception:
    TelegramBotClient = None

try:
    from meta_messaging import MetaMessagingClient
except Exception:
    MetaMessagingClient = None


class SocialRouter:
    """Unified router for all modules under `Public Apis`."""

    def __init__(self):
        self.whatsapp = WhatsAppClient() if WhatsAppClient else None
        self.telegram = TelegramBotClient() if TelegramBotClient else None
        self.meta = MetaMessagingClient() if MetaMessagingClient else None
        self.dynamic_clients: Dict[str, Any] = {}
        self._load_dynamic_clients()

    def _load_dynamic_clients(self) -> None:
        """Dynamically load all `<name>.py` modules from Public Apis."""
        if not os.path.isdir(PUBLIC_APIS):
            return

        for filename in os.listdir(PUBLIC_APIS):
            if not filename.endswith(".py"):
                continue
            if filename.startswith("_"):
                continue
            module_name = filename[:-3]
            if module_name in {"whatsapp_business", "telegram_bot", "meta_messaging"}:
                continue

            try:
                module = importlib.import_module(module_name)
            except Exception:
                continue

            client = self._build_client(module)
            if client:
                self.dynamic_clients[module_name.lower()] = client

    def _build_client(self, module) -> Optional[Any]:
        """Instantiate the first *Client class that supports no-arg constructor."""
        candidates = []
        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            if inspect.isclass(attr) and attr_name.lower().endswith("client"):
                candidates.append(attr)
        for cls in candidates:
            try:
                sig = inspect.signature(cls)
                required = [
                    p for p in sig.parameters.values()
                    if p.default is inspect._empty and p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)
                ]
                if len(required) > 0:
                    continue
                return cls()
            except Exception:
                continue
        return None

    def supported_platforms(self) -> List[str]:
        base = ["whatsapp", "telegram", "meta"]
        return sorted(base + list(self.dynamic_clients.keys()))

    def execute(self, platform: str, method: str, params: Dict[str, Any]) -> Dict[str, Any]:
        platform = (platform or "").strip().lower()
        client = self._resolve_client(platform)
        if client is None:
            return {"success": False, "error": f"Unsupported platform: {platform}"}

        if not hasattr(client, method):
            return {"success": False, "error": f"Method '{method}' not found on platform '{platform}'"}

        fn = getattr(client, method)
        if not callable(fn):
            return {"success": False, "error": f"Attribute '{method}' is not callable"}

        try:
            return fn(**params)
        except TypeError as e:
            return {"success": False, "error": f"Parameter mismatch: {e}"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _resolve_client(self, platform: str):
        if platform == "whatsapp":
            return self.whatsapp
        if platform == "telegram":
            return self.telegram
        if platform in {"meta", "messenger", "instagram"}:
            return self.meta
        return self.dynamic_clients.get(platform)

    def send(self, platform: str, to: str, message: str) -> Dict:
        platform = (platform or "").strip().lower()
        if platform == "whatsapp":
            if not self.whatsapp:
                return {"success": False, "error": "WhatsApp client unavailable"}
            return self.whatsapp.send_text_message(to, message)

        if platform == "telegram":
            if not self.telegram:
                return {"success": False, "error": "Telegram client unavailable"}
            return self.telegram.send_message(to, message)

        if platform in {"meta", "messenger", "instagram"}:
            if not self.meta:
                return {"success": False, "error": "Meta client unavailable"}
            return self.meta.send_text(to, message)

        client = self.dynamic_clients.get(platform)
        if not client:
            return {"success": False, "error": f"Unsupported platform: {platform}"}

        # Best-effort fallback for arbitrary API clients with common method names.
        for method_name in ("send_message", "send_text", "send_text_message"):
            if hasattr(client, method_name):
                try:
                    return getattr(client, method_name)(to, message)
                except Exception:
                    continue
        return {
            "success": False,
            "error": f"Platform '{platform}' loaded but no compatible send method was found",
        }

