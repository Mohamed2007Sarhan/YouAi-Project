import time
import logging
import threading

logger = logging.getLogger("MoodManager")

class MoodManager:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(MoodManager, cls).__new__(cls)
                cls._instance._init_state()
            return cls._instance

    def _init_state(self):
        self.current_mood = "normal"
        self.reason = ""
        self.mood_start_time = 0
        self.mood_duration = 1.5 * 3600  # 1.5 hours in seconds
        self._checker_thread = threading.Thread(target=self._check_timeout, daemon=True)
        self._checker_thread.start()

    def set_mood(self, mood: str, reason: str, duration_hours: float = 1.5):
        """Set a new mood with a reason and duration."""
        with self._lock:
            self.current_mood = mood
            self.reason = reason
            self.mood_duration = duration_hours * 3600
            self.mood_start_time = time.time()
            logger.info(f"Mood changed to '{self.current_mood}' because: {self.reason}")

    def reset_mood(self):
        """Reset mood back to normal."""
        with self._lock:
            self.current_mood = "normal"
            self.reason = ""
            self.mood_start_time = 0
            logger.info("Mood reset to normal.")

    def get_mood_context(self) -> str:
        """Returns the prompt context for the LLM based on current mood."""
        with self._lock:
            if self.current_mood != "normal" and self.reason:
                return f"[Current Mood: {self.current_mood} | Reason: {self.reason}] You must act and speak in accordance with this mood."
            return ""

    def _check_timeout(self):
        """Background thread to reset mood after duration expires."""
        while True:
            time.sleep(60)  # Check every minute
            with self._lock:
                if self.current_mood != "normal" and self.mood_start_time > 0:
                    elapsed = time.time() - self.mood_start_time
                    if elapsed >= self.mood_duration:
                        logger.info("Mood duration expired.")
                        self.reset_mood()
