"""
Task Watcher Module
===================
أداة مراقبة ديناميكية يقدر الـ AI يعملها لنفسه.
تراقب: ملف / URL / process / متغير
وتبلغ فوراً لما يحصل أي تغيير.
"""

import os
import time
import hashlib
import logging
import threading
import subprocess
from datetime import datetime
from typing import Callable, Optional, Any

logger = logging.getLogger("TaskWatcher")

# ─────────────────────────────────────────────
# سجل المراقبين النشطين (يتشارك بين الكلاسات)
# ─────────────────────────────────────────────
_active_watchers: dict[str, "WatcherJob"] = {}
_watchers_lock = threading.Lock()


# ══════════════════════════════════════════════
#  WatcherJob — وحدة مراقبة واحدة
# ══════════════════════════════════════════════
class WatcherJob:
    """
    وحدة مراقبة تشتغل في background thread.
    لما تكتشف تغيير، تنادي on_change(watcher_id, old_val, new_val).
    """

    def __init__(
        self,
        watcher_id: str,
        watch_type: str,          # "file" | "url" | "process" | "value"
        target: str,              # المسار / الرابط / اسم الـ process
        on_change: Callable,      # callback(watcher_id, old, new)
        interval: float = 5.0,   # ثواني بين كل فحص
        value_fn: Optional[Callable[[], Any]] = None,  # للـ "value" type
    ):
        self.watcher_id  = watcher_id
        self.watch_type  = watch_type
        self.target      = target
        self.on_change   = on_change
        self.interval    = interval
        self.value_fn    = value_fn
        self.created_at  = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        self._stop_event = threading.Event()
        self._thread     = threading.Thread(target=self._run, daemon=True, name=f"Watcher-{watcher_id}")
        self._last_val   = None

    def start(self):
        self._last_val = self._snapshot()
        self._thread.start()
        logger.info(f"[Watcher:{self.watcher_id}] Started | type={self.watch_type} | target={self.target}")

    def stop(self):
        self._stop_event.set()
        logger.info(f"[Watcher:{self.watcher_id}] Stopped.")

    def is_alive(self) -> bool:
        return self._thread.is_alive()

    # ── الحلقة الرئيسية ──────────────────────
    def _run(self):
        while not self._stop_event.is_set():
            try:
                current = self._snapshot()
                if current != self._last_val and self._last_val is not None:
                    logger.info(f"[Watcher:{self.watcher_id}] Change detected!")
                    try:
                        self.on_change(self.watcher_id, self._last_val, current)
                    except Exception as cb_err:
                        logger.error(f"[Watcher:{self.watcher_id}] Callback error: {cb_err}")
                    self._last_val = current
                elif self._last_val is None:
                    self._last_val = current
            except Exception as e:
                logger.error(f"[Watcher:{self.watcher_id}] Snapshot error: {e}")
            self._stop_event.wait(self.interval)

    # ── Snapshot حسب النوع ────────────────────
    def _snapshot(self) -> Any:
        if self.watch_type == "file":
            return self._hash_file(self.target)
        elif self.watch_type == "url":
            return self._fetch_url(self.target)
        elif self.watch_type == "process":
            return self._check_process(self.target)
        elif self.watch_type == "value":
            if self.value_fn:
                return self.value_fn()
            return None
        return None

    def _hash_file(self, path: str) -> Optional[str]:
        try:
            if not os.path.exists(path):
                return "__NOT_FOUND__"
            with open(path, "rb") as f:
                return hashlib.md5(f.read()).hexdigest()
        except Exception:
            return None

    def _fetch_url(self, url: str) -> Optional[str]:
        try:
            import urllib.request
            with urllib.request.urlopen(url, timeout=10) as r:
                content = r.read()
                return hashlib.md5(content).hexdigest()
        except Exception as e:
            return f"__ERROR__: {e}"

    def _check_process(self, process_name: str) -> bool:
        try:
            result = subprocess.run(
                ["tasklist", "/FI", f"IMAGENAME eq {process_name}"],
                capture_output=True, text=True
            )
            return process_name.lower() in result.stdout.lower()
        except Exception:
            return False

    def info(self) -> dict:
        return {
            "id":         self.watcher_id,
            "type":       self.watch_type,
            "target":     self.target,
            "alive":      self.is_alive(),
            "interval":   self.interval,
            "created_at": self.created_at,
            "last_val":   str(self._last_val)[:80],
        }


# ══════════════════════════════════════════════
#  TaskWatcherManager — يدير كل المراقبين
# ══════════════════════════════════════════════
class TaskWatcherManager:
    """
    الـ AI يتعامل مع الكلاس ده لإنشاء / إلغاء / استعراض المراقبين.
    """

    def __init__(self, notify_callback: Callable[[str], None]):
        """
        notify_callback: دالة تستقبل رسالة نصية وتعرضها/تنطقها للمستخدم.
        """
        self.notify = notify_callback

    # ── إنشاء مراقب جديد ─────────────────────
    def create_watcher(
        self,
        watch_type: str,
        target: str,
        interval: float = 5.0,
        custom_id: Optional[str] = None,
        value_fn: Optional[Callable] = None,
    ) -> str:
        """
        يعمل مراقب جديد ويبدأه فوراً.
        يرجع watcher_id.
        """
        watcher_id = custom_id or f"{watch_type}_{int(time.time())}"

        job = WatcherJob(
            watcher_id=watcher_id,
            watch_type=watch_type,
            target=target,
            on_change=self._on_change,
            interval=interval,
            value_fn=value_fn,
        )

        with _watchers_lock:
            if watcher_id in _active_watchers:
                _active_watchers[watcher_id].stop()
            _active_watchers[watcher_id] = job

        job.start()
        logger.info(f"[WatcherManager] Created watcher: {watcher_id}")
        return watcher_id

    # ── إلغاء مراقب ──────────────────────────
    def stop_watcher(self, watcher_id: str) -> bool:
        with _watchers_lock:
            job = _active_watchers.pop(watcher_id, None)
        if job:
            job.stop()
            logger.info(f"[WatcherManager] Stopped: {watcher_id}")
            return True
        return False

    def stop_all(self):
        with _watchers_lock:
            ids = list(_active_watchers.keys())
        for wid in ids:
            self.stop_watcher(wid)

    # ── قائمة المراقبين ───────────────────────
    def list_watchers(self) -> list[dict]:
        with _watchers_lock:
            return [job.info() for job in _active_watchers.values()]

    # ── الـ Callback لما يحصل تغيير ──────────
    def _on_change(self, watcher_id: str, old_val: Any, new_val: Any):
        job_info = _active_watchers.get(watcher_id)
        watch_type = job_info.watch_type if job_info else "?"
        target     = job_info.target     if job_info else watcher_id

        # رسالة بالعربي والإنجليزي تبعاً للنوع
        messages = {
            "file":    f"🔔 تغيير في الملف: {target}",
            "url":     f"🌐 تغيير في الصفحة: {target}",
            "process": f"⚙️ تغيير في حالة البرنامج: {target}  |  الآن: {'شغال ✅' if new_val else 'وقف ❌'}",
            "value":   f"📊 تغيير في القيمة [{watcher_id}]: {old_val} ← {new_val}",
        }
        msg = messages.get(watch_type, f"🔔 تغيير في [{watcher_id}]")

        logger.info(f"[WatcherManager] Notifying: {msg}")
        try:
            self.notify(msg)
        except Exception as e:
            logger.error(f"[WatcherManager] Notify error: {e}")


# ══════════════════════════════════════════════
#  Helper: ترجم JSON من الـ AI لأمر مراقبة
# ══════════════════════════════════════════════
def parse_watch_command(cmd: dict, manager: TaskWatcherManager) -> str:
    """
    يستقبل dict من JSON الـ AI ويشغل الأمر المناسب.

    JSON المتوقع من الـ AI:
    {
        "watch_action": "create" | "stop" | "list",
        "watch_type":   "file" | "url" | "process" | "value",
        "target":       "...",
        "interval":     10,
        "watcher_id":   "my_watcher"   (اختياري)
    }
    يرجع رسالة تأكيد.
    """
    action = cmd.get("watch_action", "create")

    if action == "create":
        wid = manager.create_watcher(
            watch_type = cmd.get("watch_type", "file"),
            target     = cmd.get("target", ""),
            interval   = float(cmd.get("interval", 5.0)),
            custom_id  = cmd.get("watcher_id"),
        )
        return f"✅ مراقب جديد شغال | ID: {wid} | هيبلغك لما يحصل أي تغيير."

    elif action == "stop":
        wid = cmd.get("watcher_id", "")
        success = manager.stop_watcher(wid)
        return f"🛑 المراقب [{wid}] {'وقف.' if success else 'مش موجود.'}"

    elif action == "list":
        watchers = manager.list_watchers()
        if not watchers:
            return "📋 مفيش مراقبين شغالين دلوقتي."
        lines = [f"- [{w['id']}] {w['type']} → {w['target']} (كل {w['interval']}ث)" for w in watchers]
        return "📋 المراقبون الشغالين:\n" + "\n".join(lines)

    return "❓ أمر مراقبة غير معروف."
