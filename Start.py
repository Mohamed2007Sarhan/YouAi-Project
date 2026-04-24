import sys
import os
import logging
import threading
import json
import time
from PyQt6.QtWidgets import QApplication, QMainWindow, QFileDialog, QMessageBox
from PyQt6.QtCore import QObject, pyqtSignal, QTimer, Qt

# 1. Logging System with Auto-Cleanup
import random
import string
from datetime import datetime, timedelta

def setup_advanced_logging():
    log_dir = "logs"
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    # 1. Cleanup old logs (> 45 days / 1.5 months)
    try:
        now = time.time()
        for f in os.listdir(log_dir):
            f_path = os.path.join(log_dir, f)
            if os.path.isfile(f_path):
                if os.stat(f_path).st_mtime < now - (45 * 86400):
                    os.remove(f_path)
                    print(f"[LOG_CLEANUP] Deleted old log: {f}")
    except Exception as e:
        print(f"[LOG_CLEANUP] Error during cleanup: {e}")

    # 2. Generate Unique Log Filename
    date_str = datetime.now().strftime("%Y-%m-%d")
    rand_id = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
    log_file = os.path.join(log_dir, f"YouAi_{date_str}_{rand_id}.log")

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(name)s] %(levelname)s: %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(log_file, encoding='utf-8')
        ]
    )
    return logging.getLogger("YouAi.Start")

logger = setup_advanced_logging()

# FrontEnd Modules
from FrontEnd.gui.main_window import MainWindow
from FrontEnd.gui.setup_windows import SocialInputWindow, VoiceSetupWindow, LoadingWindow, StyleCaptureWindow
from FrontEnd.audio.speech_engine import SpeechEngine
from FrontEnd.audio.tts_engine import TTSEngine

# Backend Modules
from Backend.memory.persona_builder import check_missing_info, load_merged_identity_from_memory
from Backend.memory.memory_management import GiantMemoryManager
from Backend.services.twin_orchestrator import TwinOrchestrator
from Backend.core.autonomous_agent import AutonomousAgent
from Backend.core.mood_manager import MoodManager
from Backend.memory.question_generator import get_setup_questions
from Backend.llms.nvidia_llm import NvidiaLLM
from Backend.tools.task_planner import TaskPlanner
from Backend.tools.task_watcher import TaskWatcherManager, parse_watch_command

# ── Table hints for fill-in questions (shown to user when DB category is empty) ───
_TABLE_HINTS = {
    "cognitive_profile":       "Describe your thinking style and how you make decisions",
    "life_events_timeline":    "What is the most important event in your life that changed its course?",
    "work_productivity":       "What is your current field of work and your most important projects?",
    "financial_memory":        "What are your financial goals or approximate income level?",
    "relationships_graph":     "Who are the most important people in your life and what is your relationship with them?",
    "knowledge_learning":      "What subjects do you love learning about, and what is the most important thing you have learned?",
    "goals_intentions":        "What is your biggest goal right now and what is your plan for it?",
    "decision_history":        "What is the hardest decision you have ever made and what was the outcome?",
    "biases_weaknesses":       "What are your weaknesses or things you are excessively influenced by?",
    "problem_solving_style":   "How do you usually solve problems: do you plan ahead or act spontaneously?",
    "risk_profile":            "How willing are you to take risks in your decisions?",
    "attention_focus_model":   "When are you most focused and what distracts your attention?",
    "personality_layers":      "How would you describe your personality in 3 words?",
    "memory_importance_config":"What things do you consider important enough to be remembered?",
    "prediction_model":        "In a difficult situation, what do you typically do?",
    "evolution_tracking":      "How have you changed as a person over the last few years?",
    "meta_thinking":           "How self-critical are you and how much do you reflect on your own thinking?",
    "action_patterns":         "Are you someone who acts quickly or do you need time to think first?",
    "context_switching":       "How do you balance seriousness and humor in your life?",
    "language_tone_engine":    "How would you describe your speaking style: formal or casual? Do you use jokes?",
    "habit_system":            "What is your daily routine and your most important habits?",
    "emotional_patterns":      "What makes you happy and what stresses or upsets you?",
    "values_principles":       "What are the most important principles and values that guide your decisions?",
}

def _get_table_hint(table: str) -> str:
    return _TABLE_HINTS.get(table, f"tell me about {table.replace('_', ' ')}")


class WorkerSignals(QObject):
    finished = pyqtSignal()
    relaunch_setup = pyqtSignal(list)
    update_loading = pyqtSignal(str)
    speak_requested = pyqtSignal(str)


# ── Startup trigger keywords (any language) ────────────────────────────────
STARTUP_KEYWORDS = [
    # Arabic
    "ابدأ", "ابدا", "استارت", "بدأ", "بدا", "هيا", "يلا", "يلاه", "هيلا",
    "شغل", "شغّل", "شغله", "شغلها", "شغلني", "اشتغل",
    "كمل", "كمّل", "اكمل", "اكمّل",
    # English
    "start", "startup", "begin", "go", "launch", "run", "continue", "proceed",
    "let's go", "lets go", "ok go", "ok start",
]

def _is_startup_trigger(text: str) -> bool:
    t = text.strip().lower()
    return any(kw in t for kw in STARTUP_KEYWORDS)

class AppOrchestrator(QObject):
    def __init__(self):
        super().__init__()
        self.db = GiantMemoryManager()
        self.tts = TTSEngine()
        self.speech = SpeechEngine(language="ar-EG")
        self.llm = NvidiaLLM()
        self.mood = MoodManager()
        self.system_language = "en-US"
        
        try:
            from Backend.tools.tool_manager import ToolManager
            self.tool_manager = ToolManager()
        except ImportError as e:
            logger.warning(f"Failed to import ToolManager: {e}")
            self.tool_manager = None
        
        self.signals = WorkerSignals()
        self.signals.finished.connect(self.launch_main_system)
        self.signals.relaunch_setup.connect(self.show_voice_setup)
        self.signals.update_loading.connect(lambda m: self.loading.set_message(m) if hasattr(self, "loading") else None)
        self.signals.speak_requested.connect(self._execute_speech)

        self.main_window = None
        self.agent = None
        self.watcher_manager = None   # Initialized after main window opens

    def start(self):
        logger.info("Initializing System Check...")
        missing = check_missing_info()
        empty_count = len(missing.get("empty_tables", []))
        total_count = missing.get("total_categories", 25)
        filled = total_count - empty_count
        
        # Store incomplete state for use in main chat
        self._db_empty_tables = missing.get("empty_tables", [])
        self._db_is_complete = (empty_count == 0)
        self._db_filled = filled
        self._db_total = total_count
        self._awaiting_fill_answers = False   # True while asking fill-in questions
        self._fill_questions = []             # list of {id, question}
        self._fill_idx = 0                    # current question index
        self._startup_allowed = False         # user must say 'start' keyword first

        MIN_COVERAGE = 20   # require at least 20/25 to auto-launch cleanly

        # 1. 100% Complete → launch immediately
        if empty_count == 0:
            logger.info("Memory is 100% complete. Launching system immediately.")
            self._startup_allowed = True
            self.launch_main_system()

        # 2. Completely empty (or only 1 filled) → full setup wizard
        elif filled <= 1:
            logger.info("Memory is empty. Starting initial Social Setup.")
            self._startup_allowed = True
            self.show_social_setup()

        # 3. Any missing categories → AI generates questions and asks user
        else:
            logger.info(f"Memory partially complete ({filled}/{total_count}). Generating targeted questions.")
            self._startup_allowed = True
            self._db_empty_tables = missing.get("empty_tables", [])
            self._db_filled = filled
            self._db_total  = total_count
            # Show deep questions directly (no social setup needed)
            QTimer.singleShot(0, self._open_deep_questions)

    def _show_incomplete_disclaimer(self, filled, total, empty_tables):
        """Show a premium-styled disclaimer dialog when DB is incomplete."""
        from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame
        from PyQt6.QtGui import QFont

        dlg = QDialog()
        dlg.setWindowTitle("YouAI — إعداد غير مكتمل")
        dlg.setWindowFlags(
            dlg.windowFlags() |
            __import__('PyQt6.QtCore', fromlist=['Qt']).Qt.WindowType.FramelessWindowHint
        )
        dlg.setAttribute(__import__('PyQt6.QtCore', fromlist=['Qt']).Qt.WidgetAttribute.WA_TranslucentBackground)
        dlg.resize(560, 380)

        outer = QVBoxLayout(dlg)
        outer.setContentsMargins(16, 16, 16, 16)

        card = QFrame()
        card.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0,y1:0,x2:1,y2:1,
                    stop:0 #0f0f1a, stop:1 #131826);
                border-radius: 24px;
                border: 1.5px solid rgba(255,180,0,0.55);
            }
        """)
        lay = QVBoxLayout(card)
        lay.setSpacing(14)
        lay.setContentsMargins(32, 28, 32, 28)

        # ── icon + title row ────────────────────────────────────────────
        title_row = QHBoxLayout()
        icon_l = QLabel("⚠️")
        icon_l.setFont(QFont("Segoe UI", 28))
        icon_l.setStyleSheet("background:transparent; border:none;")
        title_row.addWidget(icon_l)

        title_l = QLabel("بيانات الذاكرة غير مكتملة")
        title_l.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        title_l.setStyleSheet("color:#FFB400; background:transparent; border:none;")
        title_row.addWidget(title_l)
        title_row.addStretch()
        lay.addLayout(title_row)

        # ── progress bar (text) ────────────────────────────────────────
        pct = int(filled / total * 100)
        bar_lbl = QLabel(
            f"<span style='color:#C5C6C7;font-size:13px;'>التغطية: </span>"
            f"<span style='color:#66FCF1;font-size:15px;font-weight:bold;'>{filled}/{total} ({pct}%)</span>"
        )
        bar_lbl.setStyleSheet("background:transparent; border:none;")
        lay.addWidget(bar_lbl)

        # ── missing categories ─────────────────────────────────────────
        names = ', '.join(empty_tables[:5])
        if len(empty_tables) > 5: names += f" و{len(empty_tables)-5} أخرى"
        missing_lbl = QLabel(
            f"<span style='color:#C5C6C7;font-size:11px;'>الفئات الناقصة: {names}</span>"
        )
        missing_lbl.setWordWrap(True)
        missing_lbl.setStyleSheet("background:transparent; border:none;")
        lay.addWidget(missing_lbl)

        # ── separator ──────────────────────────────────────────────────
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("background:rgba(255,180,0,0.2); border:none; max-height:1px;")
        lay.addWidget(sep)

        # ── disclaimer text ────────────────────────────────────────────
        disc = QLabel(
            "📋 <b>Disclaimer:</b> Due to insufficient data, responses may not be 100% accurate.\n"
            "We disclaim responsibility for any errors in judgment or actions resulting from this."
        )
        disc.setWordWrap(True)
        disc.setFont(QFont("Segoe UI", 11))
        disc.setStyleSheet("color:#C5C6C7; background:transparent; border:none;")
        lay.addWidget(disc)

        lay.addStretch()

        # ── buttons ────────────────────────────────────────────────────
        btn_row = QHBoxLayout()
        btn_row.setSpacing(12)

        btn_start = QPushButton("ابدأ على أي حال  →")
        btn_start.setFixedHeight(44)
        btn_start.setStyleSheet("""
            QPushButton {
                background: rgba(255,180,0,0.12);
                color: #FFB400;
                border: 1px solid rgba(255,180,0,0.5);
                border-radius: 22px;
                font-size: 13px; font-weight: bold;
            }
            QPushButton:hover { background: rgba(255,180,0,0.22); }
        """)

        btn_setup = QPushButton("✅  اكمل الإعداد الآن")
        btn_setup.setFixedHeight(44)
        btn_setup.setStyleSheet("""
            QPushButton {
                background: #66FCF1;
                color: #0B0C10;
                border: none;
                border-radius: 22px;
                font-size: 13px; font-weight: bold;
            }
            QPushButton:hover { background: #45A29E; }
        """)

        btn_start.clicked.connect(dlg.reject)
        btn_setup.clicked.connect(dlg.accept)

        btn_row.addWidget(btn_start)
        btn_row.addWidget(btn_setup, 2)
        lay.addLayout(btn_row)

        outer.addWidget(card)

        # center on screen
        from PyQt6.QtWidgets import QApplication
        screen_geo = QApplication.primaryScreen().availableGeometry()
        dlg.move(
            screen_geo.center().x() - dlg.width() // 2,
            screen_geo.center().y() - dlg.height() // 2,
        )

        accepted = dlg.exec()

        if accepted:   # Complete Setup
            self.check_voice_setup()
        else:          # Start Anyway
            self._startup_allowed = False
            self.launch_main_system()
            QTimer.singleShot(500, self._show_disclaimer_in_chat)

    def show_social_setup(self):
        self.social_window = SocialInputWindow()
        self.social_window.data_submitted.connect(self.on_social_submitted)
        self.social_window.show()

    def on_social_submitted(self, data):
        logger.info(f"Identity data received: {data}")
        self.social_window.close()
        
        self.loading = LoadingWindow("We are currently collecting your data from social media...")
        self.loading.show()
        
        def run_automated_profiling():
            try:
                # 1. Store account links in DB
                self.db.create_custom_table("social_media_accounts", ["platform_name", "profile_url", "account_identifier", "source"])
                for plat, val in data.items():
                    if val and plat != "uploaded_file":
                        self.db.insert_record("social_media_accounts", {
                            "platform_name": plat.title(),
                            "profile_url": val,
                            "account_identifier": val,
                            "source": "IdentityLinkWindow"
                        })

                # 2. Deep Extraction using SocialFetch tools
                QTimer.singleShot(0, lambda: self.loading.set_message("جاري استخراج بيانات الحسابات...") if hasattr(self.loading, 'set_message') else None)
                raw_context = self.run_deep_social_fetch(data)
                
                # 3. Profile & store with LLM analysis
                if raw_context.strip():
                    QTimer.singleShot(0, lambda: self.loading.set_message("AI يحلل شخصيتك ويبني الذاكرة...") if hasattr(self.loading, 'set_message') else None)
                    orch = TwinOrchestrator()
                    orch.profile_and_store(raw_context)
                    logger.info(f"[Setup] Profiling complete. Context size: {len(raw_context)} chars.")
                else:
                    logger.warning("[Setup] No social context collected — skipping LLM profiling.")
                
                QTimer.singleShot(0, self._after_social_process)
            except Exception as e:
                logger.error(f"Automated profiling error: {e}")
                QTimer.singleShot(0, self._after_social_process)

        threading.Thread(target=run_automated_profiling, daemon=True).start()

    def run_deep_social_fetch(self, data):
        """
        Collects real profile data from social accounts using SocialFetch tools.
        Falls back to simple text context if tools fail.
        """
        results = []
        social_fetch_dir = os.path.join(os.path.dirname(__file__), "Backend", "SocialFetch")

        # Map platform names to their SocialFetch scripts
        platform_scripts = {
            "github":    os.path.join(social_fetch_dir, "github.py"),
            "reddit":    os.path.join(social_fetch_dir, "reddit.py"),
            "twitter":   os.path.join(social_fetch_dir, "twitter.py"),
            "facebook":  os.path.join(social_fetch_dir, "facebook.py"),
            "instagram": os.path.join(social_fetch_dir, "instagram.py"),
            "tiktok":    os.path.join(social_fetch_dir, "tiktok.py"),
            "medium":    os.path.join(social_fetch_dir, "medium.py"),
        }

        for plat, val in data.items():
            if not val or plat == "uploaded_file":
                continue

            # Extract username/identifier from URL or use as-is
            identifier = val.strip()
            for prefix in ["https://", "http://", "www."]:
                if identifier.startswith(prefix):
                    identifier = identifier[len(prefix):]
            # e.g. "github.com/MohamedSarhan" → "MohamedSarhan"
            if "/" in identifier:
                identifier = identifier.rstrip("/").split("/")[-1]
            if identifier.startswith("@"):
                identifier = identifier[1:]

            plat_key = plat.lower().strip()
            logger.info(f"[SocialFetch] Fetching {plat_key}: {identifier}")

            # ── Method 1: SocialFetch script (headless browser) ─────────
            script = platform_scripts.get(plat_key)
            if script and os.path.exists(script):
                try:
                    import subprocess as _sp
                    result = _sp.run(
                        [sys.executable, script, identifier, "--browser", "chrome"],
                        capture_output=True, text=True, timeout=45
                    )
                    output = result.stdout.strip()
                    if output and len(output) > 10:
                        results.append(f"[{plat_key.upper()}_SCRAPE] username={identifier}\n{output}")
                        logger.info(f"[SocialFetch] Got {len(output)} chars from {plat_key} script.")
                        continue  # script worked — no need for fallback
                    else:
                        logger.warning(f"[SocialFetch] Script for {plat_key} returned no data. Trying API fallback.")
                except Exception as e:
                    logger.warning(f"[SocialFetch] Script failed for {plat_key}: {e}. Trying API fallback.")

            # ── Method 2: API fallback (GitHub REST API, Twitter guest, etc.) ─
            if plat_key == "github":
                try:
                    import urllib.request as _ur, json as _json
                    api_url = f"https://api.github.com/users/{identifier}"
                    req = _ur.Request(api_url, headers={"User-Agent": "YouAI-Twin/1.0"})
                    with _ur.urlopen(req, timeout=10) as resp:
                        gh = _json.loads(resp.read().decode())
                    summary = (
                        f"[GITHUB_API] username={identifier}\n"
                        f"  name={gh.get('name','')}\n"
                        f"  bio={gh.get('bio','')}\n"
                        f"  location={gh.get('location','')}\n"
                        f"  company={gh.get('company','')}\n"
                        f"  public_repos={gh.get('public_repos','')}\n"
                        f"  followers={gh.get('followers','')}\n"
                        f"  blog={gh.get('blog','')}\n"
                        f"  email={gh.get('email','')}\n"
                    )
                    results.append(summary)
                    logger.info(f"[SocialFetch] GitHub API succeeded for {identifier}.")
                    continue
                except Exception as e:
                    logger.warning(f"[SocialFetch] GitHub API failed: {e}")

            if plat_key in ("twitter", "x"):
                try:
                    # Use the SocialFetch Twitter class directly
                    sys.path.insert(0, social_fetch_dir)
                    from twitter import Twitter
                    raw = Twitter.scrap(identifier)
                    if raw:
                        results.append(f"[TWITTER_SCRAPE] username={identifier}\n{raw}")
                        logger.info(f"[SocialFetch] Twitter scrape succeeded for {identifier}.")
                    sys.path.pop(0)
                    continue
                except Exception as e:
                    logger.warning(f"[SocialFetch] Twitter scrape failed: {e}")

            # ── Method 3: SmartFetch (browser cookies) ─────────────────
            try:
                from Backend.tools.smart_fetch import SmartSocialFetcher
                fetcher = SmartSocialFetcher()
                res = fetcher.fetch_profile(plat_key, identifier)
                if res:
                    results.append(res)
                    logger.info(f"[SocialFetch] SmartFetch succeeded for {plat_key}/{identifier}.")
                    continue
            except Exception as e:
                logger.warning(f"[SocialFetch] SmartFetch failed for {plat_key}: {e}")

            # ── Fallback: just note the account ────────────────────────
            results.append(f"[SOCIAL_ACCOUNT] platform={plat_key}, identifier={identifier}, url={val}")

        # ── Uploaded file ───────────────────────────────────────────────
        file_path = data.get("uploaded_file")
        if file_path and os.path.exists(file_path):
            try:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    file_text = f.read()
                results.append(f"--- UPLOADED FILE CONTENT ({os.path.basename(file_path)}) ---\n{file_text}")
                logger.info(f"[SocialFetch] Loaded uploaded file: {file_path}")
            except Exception as e:
                logger.error(f"File Read Error: {e}")

        combined = "\n\n".join(results)
        logger.info(f"[SocialFetch] Total context collected: {len(combined)} chars from {len(results)} sources.")
        return combined

    def _after_social_process(self):
        """Called after social fetch+profiling. Opens StyleCaptureWindow.
        Deep Setup runs AFTER the user submits their writing sample.
        IMPORTANT: Show new window BEFORE closing loading to avoid Qt exit on last-window-close.
        """
        # Open style window first, THEN close loading
        self.style_window = StyleCaptureWindow()
        self.style_window.style_captured.connect(self._on_style_captured)
        self.style_window.show()
        logger.info("[StyleCapture] Style capture window opened.")

        # Now safe to close loading (another window is already visible)
        if hasattr(self, 'loading') and self.loading:
            try: self.loading.close()
            except: pass

    def _open_style_capture(self):
        """Open StyleCaptureWindow — used from finalize_profiling path."""
        self.style_window = StyleCaptureWindow()
        self.style_window.style_captured.connect(self._on_style_captured)
        self.style_window.show()
        logger.info("[StyleCapture] Style capture window opened.")
        # Close loading after new window is visible
        if hasattr(self, 'loading') and self.loading:
            try: self.loading.close()
            except: pass

    def _on_style_captured(self, text: str):
        """Store style sample, then ask the user the deep questions directly (no AI self-simulation)."""
        def _store():
            if text.strip():
                try:
                    self.db.insert_record("language_tone_engine", {
                        "speaking_style": "written_sample",
                        "catchphrases": "",
                        "explanation_style": text.strip()[:2000],
                        "importance": "3",
                    })
                    from Backend.tools.short_memory import ShortMemory
                    sm = ShortMemory(
                        file_path=os.path.join(os.path.dirname(__file__), "logs", "short_memory.json")
                    )
                    sm.add("user_style_sample", text.strip()[:2000])
                    logger.info(f"[StyleCapture] Stored {len(text)} chars.")
                except Exception as e:
                    logger.error(f"[StyleCapture] Storage error: {e}")
            # Open deep questions window on the UI thread
            QTimer.singleShot(0, self._open_deep_questions)

        threading.Thread(target=_store, daemon=True).start()

    def _open_deep_questions(self):
        """Use the LLM to generate targeted questions for empty DB categories, then ask the USER."""
        from Backend.memory.persona_builder import check_missing_info
        from Backend.memory.memory_schema import SCHEMA_MAPPING

        missing_info = check_missing_info()
        empty_tables = [t for t in missing_info.get('empty_tables', []) if t in SCHEMA_MAPPING]

        if not empty_tables:
            logger.info("[DeepSetup] All categories filled — no questions needed.")
            QTimer.singleShot(0, self.launch_main_system)
            return

        filled = missing_info.get('total_categories', 25) - len(empty_tables)
        total  = missing_info.get('total_categories', 25)
        logger.info(f"[DeepSetup] Generating AI questions for {len(empty_tables)} empty categories ({filled}/{total} filled).")

        # Show loading while LLM generates questions
        self.loading = LoadingWindow("Preparing personalized questions for you...")
        self.loading.show()

        def _generate_questions():
            questions = []
            try:
                categories_block = "\n".join(
                    f"- {t}: {_get_table_hint(t)}" for t in empty_tables
                )
                prompt = (
                    "You are a Digital Twin setup assistant. "
                    "Generate ONE natural, conversational Arabic question for EACH category below. "
                    "Questions must be friendly, direct, and in Egyptian Arabic dialect. "
                    "Return JSON ONLY: [{\"id\": \"category_name\", \"question\": \"...\"}]\n\n"
                    f"Categories to generate questions for:\n{categories_block}"
                )
                raw = self.llm.chat(
                    [{"role": "user", "content": prompt}],
                    temperature=0.6,
                    use_reviser=False,
                )
                import re as _re
                import json as _json
                m = _re.search(r'\[.*\]', raw, _re.DOTALL)
                if m:
                    items = _json.loads(m.group(0))
                    for item in items:
                        if item.get("id") and item.get("question"):
                            questions.append({"id": item["id"], "question": item["question"]})
                logger.info(f"[DeepSetup] LLM generated {len(questions)} questions.")
            except Exception as e:
                logger.error(f"[DeepSetup] LLM question generation failed: {e}")

            # Fallback to hint-based questions if LLM failed or returned nothing
            if not questions:
                questions = [
                    {"id": t, "question": _get_table_hint(t)}
                    for t in empty_tables
                ]
                logger.info(f"[DeepSetup] Using {len(questions)} fallback questions.")

            # Store on self so the bound method can access them
            self._generated_questions = questions
            QTimer.singleShot(0, self._show_deep_questions_window)

        threading.Thread(target=_generate_questions, daemon=True).start()

    def _show_deep_questions_window(self):
        """Show the VoiceSetupWindow with AI-generated questions (called on main thread)."""
        questions = getattr(self, '_generated_questions', [])
        if not questions:
            logger.error("[DeepSetup] No questions to show — launching main system.")
            self.launch_main_system()
            return

        if hasattr(self, 'loading') and self.loading:
            try: self.loading.close()
            except: pass

        self.deep_q_window = VoiceSetupWindow(self.tts, self.speech, questions)
        self.deep_q_window.setup_completed.connect(self._on_deep_questions_done)
        self.deep_q_window.show()

        if hasattr(self, 'style_window') and self.style_window:
            try: self.style_window.close()
            except: pass

        QTimer.singleShot(600, self.deep_q_window.start_flow)
        logger.info(f"[DeepSetup] Question window opened with {len(questions)} questions.")

    def _on_deep_questions_done(self):
        """Store user answers in ShortMemory AND in the DB via LLM profiling,
        then re-check coverage."""
        answers = getattr(self.deep_q_window, 'answers', [])
        self.deep_q_window.show()

        # 1. Store in ShortMemory immediately
        try:
            from Backend.tools.short_memory import ShortMemory
            sm = ShortMemory(
                file_path=os.path.join(os.path.dirname(__file__), "logs", "short_memory.json")
            )
            for qa_text in answers:
                sm.add("deep_user_answer", qa_text)
            if answers:
                table_lines = ["=" * 52, "  User Answers — Deep Q&A", "=" * 52]
                for i, a in enumerate(answers, 1):
                    table_lines.append(f"[{i:02d}] {a}")
                sm.add("deep_setup_table", "\n".join(table_lines))
            logger.info(f"[DeepSetup] Stored {len(answers)} answers in ShortMemory.")
        except Exception as e:
            logger.error(f"[DeepSetup] ShortMemory store error: {e}")

        if not answers:
            self.deep_q_window.close()
            QTimer.singleShot(0, self.check_voice_setup)
            return

        # 2. Show loading, store in DB via LLM profiling
        self.loading = LoadingWindow("Analyzing your answers and storing in memory...")
        self.loading.show()
        self.deep_q_window.close()

        def _store_in_db():
            try:
                orch = TwinOrchestrator()
                raw = "[USER_DEEP_ANSWERS]\n" + "\n".join(answers)
                orch.profile_and_store(raw)
                logger.info(f"[DeepSetup] {len(answers)} answers stored in DB via LLM profiling.")
            except Exception as e:
                logger.error(f"[DeepSetup] DB store error: {e}")

            # ── Re-check coverage ──────────────────────────────────────────
            from Backend.memory.persona_builder import check_missing_info
            fresh      = check_missing_info()
            still_empty = fresh.get('empty_tables', [])
            filled     = fresh.get('total_categories', 25) - len(still_empty)
            total      = fresh.get('total_categories', 25)
            logger.info(f"[DeepSetup] Coverage after storage: {filled}/{total}")

            # ── Decide next step; bound methods dispatched on main thread ──
            retry = getattr(self, '_deep_q_retries', 0)
            self._deep_q_still_empty = still_empty
            self._deep_q_filled      = filled
            self._deep_q_total       = total

            if not still_empty:
                logger.info("[DeepSetup] 100% complete — launching.")
                self._deep_q_retries = 0
                QTimer.singleShot(0, self._deep_setup_done)

            elif retry < 3:
                logger.info(f"[DeepSetup] Missing {len(still_empty)} tables. Retry {retry+1}/3.")
                self._deep_q_retries = retry + 1
                QTimer.singleShot(0, self._deep_setup_retry)

            else:
                logger.warning(f"[DeepSetup] Max retries. Launching with {filled}/{total}.")
                self._db_empty_tables = still_empty
                self._db_filled       = filled
                self._db_total        = total
                QTimer.singleShot(0, self._deep_setup_disclaimer)

        threading.Thread(target=_store_in_db, daemon=True).start()

    # ── Bound methods for QTimer dispatch (always main-thread safe) ────────────

    def _deep_setup_done(self):
        """100% coverage reached — close loading and launch."""
        if hasattr(self, 'loading') and self.loading:
            try: self.loading.close()
            except: pass
        self.launch_main_system()

    def _deep_setup_retry(self):
        """More categories needed — close loading and ask again."""
        if hasattr(self, 'loading') and self.loading:
            try: self.loading.close()
            except: pass
        self._open_deep_questions()

    def _deep_setup_disclaimer(self):
        """Max retries reached — launch with disclaimer."""
        if hasattr(self, 'loading') and self.loading:
            try: self.loading.close()
            except: pass
        self.launch_main_system()
        QTimer.singleShot(800, self._show_disclaimer_in_chat)


    def _run_style_similarity(self, user_qa_list: list):
        """
        Ask the LLM to simulate answers using only DB data, then compute
        word-overlap similarity vs the user's actual answers.
        Stores a 'style_similarity' entry in ShortMemory.
        """
        import re as _re, json as _json
        from Backend.tools.short_memory import ShortMemory

        # Parse Q and A from "Q: ... | A: ..."
        questions, user_answers = [], []
        for qa in user_qa_list:
            if " | A:" in qa:
                q, a = qa.split(" | A:", 1)
                questions.append(q.replace("Q: ", "").strip())
                user_answers.append(a.strip())

        if not questions:
            return

        # Build compact DB snapshot
        db_lines = []
        for tbl in self.db.get_all_tables():
            recs = self.db.get_records(tbl, min_importance=1)
            if recs:
                r = recs[0]
                for k, v in r.items():
                    if k not in ("id","created_at","updated_at","importance","is_archived"):
                        if v and str(v).strip().lower() not in ("","none","null","[]"):
                            db_lines.append(f"  [{tbl}] {k}: {str(v)[:200]}")
        db_block = "\n".join(db_lines[:50]) or "(no data)"

        q_block = "\n".join(f"{i+1}. {q}" for i, q in enumerate(questions))
        prompt = (
            "Based ONLY on this person's stored data, answer each question as if you ARE them.\n"
            "Be brief and natural. Return JSON ONLY: [{\"a\": \"...\"}]\n\n"
            f"STORED DATA:\n{db_block}\n\n"
            f"QUESTIONS:\n{q_block}"
        )

        try:
            raw = self.llm.chat(
                [{"role": "user", "content": prompt}],
                temperature=0.3, use_reviser=False
            )
        except Exception as e:
            logger.error(f"[StyleSim] LLM call failed: {e}")
            return

        # Parse
        m = _re.search(r'\[.*?\]', raw, _re.DOTALL)
        if not m:
            logger.warning("[StyleSim] Could not parse simulated answers.")
            return
        try:
            sim_list = _json.loads(m.group(0))
        except Exception:
            logger.warning("[StyleSim] JSON parse error.")
            return

        # Word-overlap similarity per question
        scores, weak = [], []
        for i, (ua, sim) in enumerate(zip(user_answers, sim_list)):
            sa    = sim.get("a", "")
            ua_w  = set(ua.lower().split())
            sa_w  = set(sa.lower().split())
            union = ua_w | sa_w
            score = len(ua_w & sa_w) / max(len(union), 1)
            scores.append(score)
            if score < 0.25 and i < len(questions):
                weak.append(f"  - {questions[i][:80]}")

        avg_pct = round(sum(scores) / max(len(scores), 1) * 100, 1)
        logger.info(f"[StyleSim] Score: {avg_pct}%  |  Weak areas: {len(weak)}")

        # Store in ShortMemory
        sm = ShortMemory(
            file_path=os.path.join(os.path.dirname(__file__), "logs", "short_memory.json")
        )
        lines = [f"=== Deep Style Similarity: {avg_pct}% ==="]
        if weak:
            lines += ["Weak alignment areas (model answer diverged from user):"] + weak
        else:
            lines.append("High alignment — all categories matched well.")
        sm.add("style_similarity", "\n".join(lines))


    def check_voice_setup(self):
        questions = get_setup_questions()
        if questions:
            self.show_voice_setup(questions)
        else:
            self.launch_main_system()

    def show_voice_setup(self, questions):
        self.voice_window = VoiceSetupWindow(self.tts, self.speech, questions)
        self.voice_window.setup_completed.connect(self.on_voice_setup_completed)
        self.voice_window.show()
        self.voice_window.start_flow()

    def on_voice_setup_completed(self):
        answers = self.voice_window.answers
        self.voice_window.close()
        if answers:
            self.loading = LoadingWindow("Finalizing Digital Persona...")
            self.loading.show()
            threading.Thread(target=self._finalize_profiling, args=(answers,), daemon=True).start()
        else:
            self.launch_main_system()

    def _finalize_profiling(self, answers):
        try:
            orch = TwinOrchestrator()
            orch.profile_and_store("[USER_VOICE_CALIBRATION]\n" + "\n".join(answers))

            # Run Deep Setup self-simulation
            from Backend.core.deep_setup import run_deep_setup
            ds_result = run_deep_setup(
                progress_callback=lambda pct, msg: QTimer.singleShot(
                    0, lambda m=msg: self.loading.set_message(m)
                )
            )
            confidence = ds_result.get("confidence_pct", 0)
            logger.info(f"[DeepSetup] Confidence={confidence}%")

            welcome_msg = orch.deep_setup()
            self.signals.speak_requested.emit(welcome_msg)

            # Final Coverage Check
            missing = get_setup_questions()
            if missing:
                self.signals.relaunch_setup.emit(missing)
            else:
                # Open Style Capture as the very last step
                QTimer.singleShot(0, self._open_style_capture)
        except Exception as e:
            logger.error(f"Finalization Error: {e}")
            QTimer.singleShot(0, self._open_style_capture)
        finally:
            if hasattr(self, 'loading'): QTimer.singleShot(0, self.loading.close)

    def launch_main_system(self):
        logger.info("Launching Main Visualization Interface...")
        
        # 1. Detect language from memory
        persona = load_merged_identity_from_memory()
        lang = persona.get("language", "English").lower()
        if "arabic" in lang or "عربي" in lang:
            self.system_language = "ar-EG"
            self.speech.set_language("ar-EG")
            logger.info("Language detected: Arabic (ar-EG)")
        else:
            self.system_language = "en-US"
            self.speech.set_language("en-US")
            logger.info("Language detected: English (en-US)")

        self.main_window = MainWindow()
        self.main_window.show()
        
        # Start Speech Engine
        self.speech.speech_recognized.connect(self.handle_user_input)
        self.speech.start()

        # Initialize Autonomous Agent (but don't start monitoring yet)
        try:
            self.agent = AutonomousAgent()
            self.agent.system_language = self.system_language
            logger.info("Autonomous Agent initialized (Standby mode).")
        except Exception as e:
            logger.error(f"Failed to initialize Autonomous Agent: {e}")

        # Initialize Watcher Manager
        def _notify_user(msg: str):
            """Callback: notifies the user of a watcher event via transcript and TTS."""
            try:
                QTimer.singleShot(0, lambda m=msg: self.main_window.update_transcript(m))
                self.signals.speak_requested.emit(msg)
            except Exception as e:
                logger.error(f"[WatcherNotify] {e}")

        self.watcher_manager = TaskWatcherManager(notify_callback=_notify_user)
        logger.info("TaskWatcherManager initialized.")

    def _show_disclaimer_in_chat(self):
        """Show the disclaimer notice + startup prompt in the main chat window."""
        empty = getattr(self, '_db_empty_tables', [])
        filled = getattr(self, '_db_filled', 0)
        total  = getattr(self, '_db_total', 25)
        msg = (
            f"Warning: My knowledge base is {filled}/{total} categories complete.\n"
            f"Missing categories: {', '.join(empty[:6])}{'...' if len(empty) > 6 else ''}\n\n"
            "Disclaimer: I am not responsible for errors caused by incomplete data.\n\n"
            "Say 'start' to let me ask questions to complete my profile, or just talk to me directly."
        )
        try:
            QTimer.singleShot(0, lambda: self.main_window.update_transcript(msg))
            self.signals.speak_requested.emit(
                "Warning: my data is incomplete. Say 'start' to complete the setup."
            )
        except Exception as e:
            logger.error(f"[Disclaimer] {e}")

    def _start_fill_questions(self):
        """Start asking fill-in questions for empty DB categories."""
        from Backend.memory.memory_schema import SCHEMA_MAPPING
        # Re-check what's actually missing right now
        from Backend.memory.persona_builder import check_missing_info
        fresh = check_missing_info()
        empty_tables = fresh.get('empty_tables', [])
        target = [t for t in empty_tables if t in SCHEMA_MAPPING]

        if not target:
            done_msg = "Database is 100% complete! I am ready to assist you."
            QTimer.singleShot(0, lambda: self.main_window.update_transcript(done_msg))
            self.signals.speak_requested.emit(done_msg)
            return

        questions = []
        for table in target:
            questions.append({
                "id": table,
                "question": f"{_get_table_hint(table)}"
            })
        self._fill_questions = questions
        self._fill_idx = 0
        self._fill_collected = []   # accumulate Q&A pairs for LLM
        self._awaiting_fill_answers = True
        self._startup_allowed = True
        logger.info(f"[FillQuestions] Starting {len(questions)} questions.")
        self._ask_next_fill_question()

    def _ask_next_fill_question(self):
        """Ask the next fill-in question or finalise when done."""
        if self._fill_idx >= len(self._fill_questions):
            self._awaiting_fill_answers = False
            self._finalize_fill_answers()
            return
        q = self._fill_questions[self._fill_idx]
        question_text = (
            f"Question {self._fill_idx + 1}/{len(self._fill_questions)}: {q['question']}"
        )
        QTimer.singleShot(0, lambda m=question_text: self.main_window.update_transcript(m))
        self.signals.speak_requested.emit(question_text)

    def _handle_fill_answer(self, answer: str):
        """Collect user answer and ask next question."""
        if not self._fill_questions or self._fill_idx >= len(self._fill_questions):
            return
        q = self._fill_questions[self._fill_idx]
        self._fill_collected.append(f"Q: {q['question']}\nA: {answer}")
        logger.info(f"[FillQuestions] Collected answer for '{q['id']}'.")
        self._fill_idx += 1
        self._ask_next_fill_question()

    def _finalize_fill_answers(self):
        """Send collected Q&A to LLM for deep profiling, then re-check coverage."""
        if not getattr(self, '_fill_collected', []):
            return

        # Show loading in chat
        loading_msg = "Analyzing your answers and storing them in memory..."
        QTimer.singleShot(0, lambda: self.main_window.update_transcript(loading_msg))
        self.signals.speak_requested.emit("Analyzing your answers...")

        def _store_and_recheck():
            try:
                raw = "[USER_VOICE_ANSWERS]\n" + "\n\n".join(self._fill_collected)
                orch = TwinOrchestrator()
                orch.profile_and_store(raw)
                logger.info("[FillQuestions] LLM profiling complete.")
            except Exception as e:
                logger.error(f"[FillQuestions] LLM store error: {e}")

            # Re-check coverage
            from Backend.memory.persona_builder import check_missing_info
            fresh = check_missing_info()
            still_empty = fresh.get('empty_tables', [])
            filled = fresh.get('total_categories', 25) - len(still_empty)
            total  = fresh.get('total_categories', 25)

            if still_empty:
                self._db_empty_tables = still_empty
                self._db_filled = filled
                recheck_msg = (
                    f"Saved. Coverage is now: {filled}/{total}.\n"
                    f"There are still {len(still_empty)} missing categories — I will ask you about them."
                )
                QTimer.singleShot(0, lambda: self.main_window.update_transcript(recheck_msg))
                self.signals.speak_requested.emit("There are still missing categories, I will continue asking.")
                QTimer.singleShot(1200, self._start_fill_questions)
            else:
                done_msg = f"Excellent! The database is now {filled}/{total} complete. I am fully ready!"
                QTimer.singleShot(0, lambda: self.main_window.update_transcript(done_msg))
                self.signals.speak_requested.emit(done_msg)

        threading.Thread(target=_store_and_recheck, daemon=True).start()

    def handle_user_input(self, text, depth=0):
        if not text or len(text) < 2: return
        if depth > 1:
            logger.warning("Max autonomous retry depth reached. Stopping.")
            return
        logger.info(f"User input: {text} (Depth: {depth})")

        # ── Fill-in questionnaire mode ────────────────────────────────
        if getattr(self, '_awaiting_fill_answers', False):
            self._handle_fill_answer(text)
            return

        # ── Startup keyword gate ──────────────────────────────────────
        if not getattr(self, '_startup_allowed', True):
            if _is_startup_trigger(text):
                self._startup_allowed = True
                self._start_fill_questions()
            else:
                # Still in disclaimer state — remind user how to proceed
                reminder = (
                    "Say 'start' to let me ask questions to complete my profile, or just speak naturally and I will try to help."
                )
                QTimer.singleShot(0, lambda: self.main_window.update_transcript(reminder))
                self.signals.speak_requested.emit(reminder)
            return
        
        def process():
            try:
                # Load persona + build rich DB block (all fields, clean format)
                persona    = load_merged_identity_from_memory()
                all_tables = self.db.get_all_tables()

                db_lines = []
                for table in all_tables:
                    records = self.db.get_records(table, min_importance=1)
                    if not records:
                        continue
                    for r in records[:2]:
                        for k, v in r.items():
                            if k in ("id","created_at","updated_at","importance","is_archived"):
                                continue
                            if v and str(v).strip().lower() not in ("", "none", "null", "[]"):
                                db_lines.append(f"  [{table}] {k}: {str(v)[:300]}")
                full_db_block = "\n".join(db_lines) if db_lines else "  (empty)"

                # 1. Capture Visual Context & Screen Info
                from PyQt6.QtWidgets import QApplication
                screen = QApplication.primaryScreen().size()
                screen_res = f"{screen.width()}x{screen.height()}"
                
                screenshot_path = "logs/last_screen.png"
                os.makedirs("logs", exist_ok=True)
                from mss import mss
                with mss() as sct:
                    sct.shot(output=screenshot_path)
                
                is_admin = "youai" in text.lower()
                admin_instr = ""
                if is_admin:
                    admin_instr = (
                        "MASTER COMMAND DETECTED: Use JSON for DB CRUD:\n"
                        '{"thought": "...", "db_action": "insert|update|delete", "table": "...", "record_id": ..., "data": {...}}\n'
                    )

                # Tool-Use Instructions (PC Control Only)
                tool_instr = (
                    "=== PC CONTROL RULES ===\n"
                    "CRITICAL: You are a voice assistant. Your PRIMARY job is to SPEAK naturally with the user.\n"
                    "JSON actions are ONLY for when the user asks you to DO something on the computer (open app, click, etc.).\n"
                    "NEVER use JSON to reply to a question or greeting — just write your text reply normally.\n\n"
                    "❌ WRONG (DO NOT DO THIS for conversation):\n"
                    '   User: \'ما اسمك\' → {"os_action": "type", "target": "محمد"} ← WRONG! This types on keyboard!\n'
                    "✅ CORRECT for conversation:\n"
                    "   User: 'ما اسمك' → Just reply: اسمي محمد سرحان\n\n"
                    "✅ CORRECT for PC actions:\n"
                    '   User: \'افتح الكاميرا\' → {"os_action": "open_app", "target": "start microsoft.windows.camera:"}\n\n'
                    f"SCREEN RESOLUTION: {screen_res}\n"
                    "SAFETY: NEVER use any action on the 'YOU AI' window itself.\n\n"
                    "--- PC ACTIONS (ONLY when user asks you to DO something) ---\n"
                    'Open app:    {"os_action": "open_app", "target": "start notepad", "process_name": "notepad.exe"}\n'
                    'Run command: {"os_action": "run_command", "target": "ipconfig"}\n'
                    'Get output:  {"os_action": "run_capture", "target": "tasklist"}\n'
                    'Click:       {"os_action": "click", "target": [960, 540]}\n'
                    'Hotkey:      {"os_action": "hotkey", "target": ["alt", "f4"]}\n'
                    'Press key:   {"os_action": "key", "target": "enter"}\n\n'
                    "--- COMMON APPS ---\n"
                    'Camera:     {"os_action": "open_app", "target": "start microsoft.windows.camera:"}\n'
                    'Notepad:    {"os_action": "open_app", "target": "start notepad", "process_name": "notepad.exe"}\n'
                    'Calculator: {"os_action": "open_app", "target": "start calc"}\n'
                    'Chrome:     {"os_action": "open_app", "target": "start chrome", "process_name": "chrome.exe"}\n'
                    'Explorer:   {"os_action": "open_app", "target": "start explorer"}\n'
                    'Settings:   {"os_action": "open_app", "target": "start ms-settings:"}\n\n'
                    "--- WATCHER TOOL ---\n"
                    '{"watch_action": "create", "watch_type": "file|url|process", "target": "...", "interval": 10}\n'
                )

                # ── ShortMemory context ──────────────────────────────
                short_mem_ctx = ""
                try:
                    from Backend.tools.short_memory import ShortMemory
                    sm = ShortMemory(
                        file_path=os.path.join(os.path.dirname(__file__), "logs", "short_memory.json")
                    )
                    short_mem_ctx = sm.context_block(limit=12)
                except Exception:
                    pass

                user_lang  = persona.get("language", "Arabic")
                user_name  = persona.get("name", "the user")

                persona_context = (
                    "=== YOUR IDENTITY ===\n"
                    f"You ARE {user_name}. You are not an AI, not an assistant, not 'YouAi'.\n"
                    f"You ARE the digital twin of a real person named {user_name}.\n"
                    f"ALWAYS respond in {user_lang}. If the user speaks a different language, match them.\n\n"
                    "=== FULL PERSONAL DATABASE ===\n"
                    f"{full_db_block}\n\n"
                    "=== SHORT-TERM MEMORY (current session) ===\n"
                    f"{short_mem_ctx}\n\n"
                    "=== STRICT RULES ===\n"
                    "1. Use ONLY data from DATABASE or MEMORY. NEVER invent facts.\n"
                    "2. Missing data? Say 'I don't recall that exactly' — never guess.\n"
                    "3. Normal conversation (greetings, questions): reply in plain text. NO JSON.\n"
                    "4. JSON ONLY when user asks to DO something on the computer.\n"
                    "5. Never use 'type' action to reply — typing = physical keyboard input.\n"
                    "6. After any PC action, report the result in one natural sentence.\n"
                    "7. If action result says [ERROR], be honest and suggest an alternative.\n"
                    f"{admin_instr}\n"
                    "=== PC CONTROL (only for computer tasks) ===\n"
                    f"{tool_instr}\n"
                )

                # 3. Generate response using NvidiaLLM
                messages = [
                    {"role": "system", "content": persona_context},
                    {"role": "user",   "content": text}
                ]
                
                chat_kwargs = {"is_talking_to_user": True}
                if getattr(self, 'tool_manager', None):
                    chat_kwargs["tools"] = self.tool_manager.get_schemas()
                    chat_kwargs["tool_executor"] = self.tool_manager

                response = self.llm.chat(messages, **chat_kwargs)

                # -------------------------------------------------------
                # TASK PLANNER: لو المهمة طويلة اعمل خطة ونفذها
                # -------------------------------------------------------
                planner = TaskPlanner()
                plan_path = None
                plan_steps = []
                is_planned_task = planner.is_long_task(text, response)

                if is_planned_task:
                    plan_steps = planner.generate_plan_from_response(text, response)
                    if len(plan_steps) >= planner.MIN_STEPS_FOR_PLAN:
                        plan_path = planner.save_plan(text, plan_steps)
                        logger.info(f"[TaskPlanner] Long task detected. Plan saved -> {plan_path}")
                        # Notify user that a plan is being executed
                        start_msg = "This looks like a multi-step task. I'll create a plan and notify you when done."
                        if "ar" in self.system_language.lower():
                            start_msg = "هذه مهمة متعددة الخطوات. سأنشئ خطة وأُبلغك عند الانتهاء."
                        QTimer.singleShot(0, lambda m=start_msg: self.main_window.update_transcript(m))
                        self.signals.speak_requested.emit(start_msg)
                    else:
                        is_planned_task = False  # Not enough steps for a full plan
                
                # EXECUTE ACTIONS
                final_speech = response
                has_acted = False
                action_result = None
                if "{" in response:
                    try:
                        import re
                        from Backend.automation.device_control import DeviceControl
                        device = DeviceControl()
                        json_match = re.search(r'\{.*\}', response, re.DOTALL)
                        if json_match:
                            cmd = json.loads(json_match.group())
                            
                            # Clean speech more robustly
                            final_speech = response
                            # Remove all JSON blocks found in the text
                            json_blocks = re.findall(r'\{.*?\}', response, re.DOTALL)
                            for block in json_blocks:
                                final_speech = final_speech.replace(block, "")
                            
                            # Remove Reviser metadata and noise
                            junk_headers = [
                                "Revised Text:", "Revised Text", "Changes Made:", 
                                "DRAFT TO REVISE:", "OUTPUT ONLY THE REVISED TEXT.", "REVISED TEXT:",
                                "Revised Text (with fixes for grammatical, linguistic, or logical errors, without altering core meaning or adding new information):"
                            ]
                            for header in junk_headers:
                                final_speech = final_speech.replace(header, "")
                            
                            final_speech = final_speech.strip()
                            if not final_speech:
                                final_speech = "Action completed."

                            # Execution
                            action_result = None
                            if "os_action" in cmd:
                                act = cmd.get("os_action")
                                tgt = cmd.get("target")
                                proc_name = cmd.get("process_name")  # optional process name for verification
                                logger.info(f"Executing Tool: {act} -> {tgt}")
                                
                                # Minimize UI temporarily to give focus to the target window
                                if act in ["click", "move", "hotkey", "type", "key", "open_app", "run_command"]:
                                    QTimer.singleShot(0, self.main_window.showMinimized)
                                    time.sleep(1.0)  # Wait for animation
                                
                                if act == "open_app":
                                    action_result = device.open_app(str(tgt), process_name=proc_name)
                                elif act == "run_command":
                                    action_result = device.run_command(str(tgt))
                                elif act == "run_capture":
                                    action_result = device.run_command_and_capture(str(tgt))
                                elif act == "click" or act == "move":
                                    if isinstance(tgt, list) and len(tgt) == 2:
                                        action_result = device.move_mouse(tgt[0], tgt[1])
                                        if act == "click":
                                            time.sleep(0.3)
                                            action_result = device.click()
                                    else:
                                        action_result = f"[ERROR] click/move needs [x, y] list, got: {tgt}"
                                elif act == "hotkey":
                                    if isinstance(tgt, list):
                                        action_result = device.hotkey(*tgt)
                                    elif isinstance(tgt, str) and "+" in tgt:
                                        keys = [k.strip() for k in tgt.split("+")]
                                        action_result = device.hotkey(*keys)
                                    else:
                                        action_result = device.press_key(str(tgt))
                                elif act == "key":
                                    action_result = device.press_key(str(tgt))
                                elif act == "type":
                                    action_result = device.type_text(str(tgt))
                                else:
                                    action_result = f"[ERROR] Unknown os_action: '{act}'"
                                
                                logger.info(f"[ActionResult] {action_result}")
                                has_acted = True
                                
                                # Restore UI after action
                                time.sleep(0.5)
                                QTimer.singleShot(0, self.main_window.showNormal)
                                
                                # Feed result back so AI knows what really happened
                                if action_result:
                                    messages.append({"role": "assistant", "content": response})
                                    messages.append({"role": "user", "content": f"[SYSTEM RESULT of your action]: {action_result}\nBased on this result, tell the user what happened in {user_lang} in one natural sentence."})
                                    confirm_resp = self.llm.chat(messages, is_talking_to_user=True, use_reviser=False)
                                    # Strip any JSON from the confirmation
                                    confirm_clean = re.sub(r'\{.*?\}', '', confirm_resp, flags=re.DOTALL).strip()
                                    if confirm_clean:
                                        final_speech = confirm_clean

                            # 1. DB Actions
                            if is_admin and "db_action" in cmd:
                                action = cmd.get("db_action")
                                table = cmd.get("table")
                                if action == "insert": self.db.insert_record(table, cmd.get("data", {}))
                                elif action == "update": self.db.update_record(table, cmd.get("record_id"), cmd.get("data", {}))
                                elif action == "delete": self.db.delete_record(table, cmd.get("record_id"))

                            # 2. Watcher Actions
                            if "watch_action" in cmd and self.watcher_manager:
                                watch_result = parse_watch_command(cmd, self.watcher_manager)
                                logger.info(f"[Watcher] {watch_result}")
                                final_speech = watch_result  # Send confirmation to user
                                has_acted = True

                    except Exception as e:
                        logger.error(f"Tool Execution Error: {e}")

                # 4. Update UI
                if not is_planned_task:
                    # مهمة عادية: اعرض الرد فوراً
                    QTimer.singleShot(0, lambda: self.main_window.update_transcript(final_speech))
                    self.signals.speak_requested.emit(final_speech)
                else:
                    # مهمة مخططة: نفذ الخطوات وبلّغ عند الإكمال
                    for step in plan_steps:
                        planner.update_step(plan_path, step["id"], "in_progress")
                        logger.info(f"[TaskPlanner] Executing step {step['id']}: {step['title']}")
                        try:
                            # Send each step to the AI and execute it
                            step_messages = list(messages) + [
                                {"role": "assistant", "content": response},
                                {"role": "user", "content": f"Execute only the following step from the plan and confirm completion: {step['title']}"}
                            ]
                            step_resp = self.llm.chat(step_messages, is_talking_to_user=True, use_reviser=False)
                            step["status"] = "done"
                            planner.update_step(plan_path, step["id"], "done")
                            logger.info(f"[TaskPlanner] Step {step['id']} done.")
                        except Exception as step_err:
                            logger.error(f"[TaskPlanner] Step {step['id']} failed: {step_err}")
                            step["status"] = "failed"
                            planner.update_step(plan_path, step["id"], "failed")

                    # أنهِ الخطة وبلّغ المستخدم
                    all_done = all(s["status"] == "done" for s in plan_steps)
                    planner.finalize_plan(plan_path, success=all_done)
                    completion_msg = planner.get_completion_message(text, plan_steps, lang=self.system_language)
                    QTimer.singleShot(0, lambda m=completion_msg: self.main_window.update_transcript(m))
                    self.signals.speak_requested.emit(completion_msg)
                    logger.info(f"[TaskPlanner] Task complete. Plan: {plan_path}")

                # 5. VERIFICATION: action_result already fed back above.
                # If action_result had an error, log it for diagnostics.
                if has_acted and action_result:
                    if "[ERROR]" in str(action_result):
                        logger.warning(f"Action had an error: {action_result}")
                    else:
                        logger.info(f"Action confirmed successful: {action_result}")
            except Exception as e: logger.error(f"Input Processing Error: {e}")
                
        threading.Thread(target=process, daemon=True).start()

    def _execute_speech(self, text):
        try:
            logger.info(f"Speaking: {text}")
            self.tts.say(text)
            self.tts.runAndWait()
        except Exception as e: logger.error(f"TTS Error: {e}")

def main():
    app = QApplication(sys.argv)
    # Prevent Qt from quitting when last setup window closes
    # (StyleCaptureWindow must open after LoadingWindow closes)
    app.setQuitOnLastWindowClosed(False)
    orchestrator = AppOrchestrator()
    QTimer.singleShot(0, orchestrator.start)
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
