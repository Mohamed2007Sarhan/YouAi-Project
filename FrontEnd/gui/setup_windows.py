import os
import time
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QHBoxLayout, 
    QPushButton, QGraphicsDropShadowEffect, QLineEdit, QFormLayout, QFileDialog
)
from PyQt6.QtCore import Qt, QPoint, pyqtSignal, QTimer
from PyQt6.QtGui import QColor, QFont

class SocialInputWindow(QWidget):
    """Window to collect basic social links before starting the profiling process."""
    data_submitted = pyqtSignal(dict)

    def __init__(self):
        super().__init__()
        self.drag_pos = QPoint()
        self.init_ui()

    def init_ui(self):
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.resize(500, 600)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)

        self.bg_widget = QWidget(self)
        self.bg_widget.setStyleSheet("""
            QWidget {
                background-color: rgba(15, 15, 20, 200);
                border-radius: 30px;
                border: 2px solid rgba(102, 252, 241, 0.4);
            }
        """)
        
        bg_layout = QVBoxLayout(self.bg_widget)
        
        # Top Bar
        top_bar = QHBoxLayout()
        top_bar.addStretch()
        self.close_btn = QPushButton("✕")
        self.close_btn.setFixedSize(30, 30)
        self.close_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #C5C6C7;
                font-size: 16px;
                font-weight: bold;
                border: none;
            }
            QPushButton:hover {
                color: #FF5A5F;
            }
        """)
        self.close_btn.clicked.connect(self.close)
        top_bar.addWidget(self.close_btn)
        bg_layout.addLayout(top_bar)

        # Title
        title_lbl = QLabel("Step 1: Identity Link")
        title_lbl.setFont(QFont("Segoe UI", 24, QFont.Weight.Bold))
        title_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_lbl.setStyleSheet("color: #66FCF1; background: transparent; border: none;")
        bg_layout.addWidget(title_lbl)

        subtitle = QLabel("Connect your social presence to build your Twin")
        subtitle.setFont(QFont("Segoe UI", 12))
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setStyleSheet("color: #C5C6C7; background: transparent; border: none; margin-bottom: 20px;")
        bg_layout.addWidget(subtitle)

        # Form
        form_layout = QFormLayout()
        form_layout.setContentsMargins(40, 0, 40, 0)
        form_layout.setVerticalSpacing(15)

        self.inputs = {}
        fields = [
            ("email", "Primary Email Address"),
            ("language", "Preferred Language (Arabic/English/Both)"),
            ("facebook", "Facebook Username/URL"),
            ("instagram", "Instagram Username/URL"),
            ("twitter", "X (Twitter) Handle"),
            ("github", "GitHub Username"),
        ]

        for key, label in fields:
            line_edit = QLineEdit()
            line_edit.setPlaceholderText(label)
            line_edit.setStyleSheet("""
                QLineEdit {
                    background-color: rgba(31, 40, 51, 180);
                    color: #FFFFFF;
                    border-radius: 12px;
                    padding: 12px;
                    border: 1px solid rgba(102, 252, 241, 0.2);
                    font-size: 14px;
                }
                QLineEdit:focus {
                    border: 1px solid #66FCF1;
                }
            """)
            self.inputs[key] = line_edit
            form_layout.addRow(line_edit)

        bg_layout.addLayout(form_layout)
        
        # Dual Button Section
        btn_action_layout = QHBoxLayout()
        btn_action_layout.setContentsMargins(40, 10, 40, 10)
        btn_action_layout.setSpacing(15)
        
        # 1. CV/Chat Upload Button
        self.upload_cv_btn = QPushButton("📄 Upload CV / Chats")
        self.upload_cv_btn.setFixedHeight(45)
        self.upload_cv_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(102, 252, 241, 0.1);
                color: #66FCF1;
                border-radius: 12px;
                font-weight: bold;
                border: 1px dashed #66FCF1;
            }
            QPushButton:hover { background-color: rgba(102, 252, 241, 0.2); }
        """)
        self.upload_cv_btn.clicked.connect(self.on_upload_clicked)
        btn_action_layout.addWidget(self.upload_cv_btn)
        
        # 2. Voice Sample Button (Decorative)
        self.upload_voice_btn = QPushButton("🎙️ Voice Samples")
        self.upload_voice_btn.setFixedHeight(45)
        self.upload_voice_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(197, 198, 199, 0.1);
                color: #C5C6C7;
                border-radius: 12px;
                font-weight: bold;
                border: 1px dashed rgba(197, 198, 199, 0.5);
            }
        """)
        btn_action_layout.addWidget(self.upload_voice_btn)
        
        bg_layout.addLayout(btn_action_layout)
        
        self.file_label = QLabel("No files selected")
        self.file_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.file_label.setStyleSheet("color: #C5C6C7; font-size: 10px; margin-bottom: 5px;")
        bg_layout.addWidget(self.file_label)
        
        bg_layout.addStretch()

        # Submit Button
        self.submit_btn = QPushButton("PROCEED TO DATA FETCH")
        self.submit_btn.setFixedHeight(55)
        self.submit_btn.setStyleSheet("""
            QPushButton {
                background-color: #66FCF1;
                color: #0B0C10;
                border-radius: 27px;
                font-weight: bold;
                font-size: 16px;
                letter-spacing: 1px;
                border: none;
            }
            QPushButton:hover {
                background-color: #45A29E;
            }
        """)
        self.submit_btn.clicked.connect(self.on_submit)
        
        btn_layout = QHBoxLayout()
        btn_layout.setContentsMargins(40, 0, 40, 30)
        btn_layout.addWidget(self.submit_btn)
        bg_layout.addLayout(btn_layout)

        # Drop Shadow
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(25)
        shadow.setColor(QColor(0, 0, 0, 200))
        shadow.setOffset(0, 0)
        self.bg_widget.setGraphicsEffect(shadow)
        layout.addWidget(self.bg_widget)

    def on_upload_clicked(self):
        file_name, _ = QFileDialog.getOpenFileName(self, "Select CV or Document", "", "Text Files (*.txt);;PDF Files (*.pdf);;All Files (*)")
        if file_name:
            self.file_path = file_name
            self.file_label.setText(os.path.basename(file_name))
            self.upload_cv_btn.setStyleSheet("background-color: rgba(102, 252, 241, 0.2); color: #66FCF1; border-radius: 12px; font-weight: bold; border: 2px solid #66FCF1;")

    def on_submit(self):
        data = {k: v.text().strip() for k, v in self.inputs.items()}
        if hasattr(self, "file_path") and self.file_path:
            data["uploaded_file"] = self.file_path
        self.data_submitted.emit(data)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self.drag_pos)
            event.accept()


class VoiceSetupWindow(QWidget):
    """Identity calibration window — voice mic + text input fallback."""
    setup_completed = pyqtSignal()

    def __init__(self, tts_engine, speech_engine, questions, language="ar-EG"):
        super().__init__()
        self.tts_engine  = tts_engine
        self.questions   = questions
        self.language    = language
        self.current_question_index = 0
        self.answers  = []
        self.drag_pos = QPoint()

        # Always create a fresh SpeechEngine so we avoid QThread restart issues
        from FrontEnd.audio.speech_engine import SpeechEngine
        self._own_speech = SpeechEngine(language=language)
        self._own_speech.speech_recognized.connect(self.on_speech_recognized)
        self._own_speech.listening_started.connect(self.on_listening_started)
        self._own_speech.listening_stopped.connect(self.on_listening_stopped)

        self._mic_active = False
        self.init_ui()

    # ── UI ────────────────────────────────────────────────────────────────

    def init_ui(self):
        from PyQt6.QtWidgets import QLineEdit
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.resize(640, 580)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(20, 20, 20, 20)

        self.bg = QWidget(self)
        self.bg.setStyleSheet("""
            QWidget {
                background-color: rgba(13, 14, 22, 215);
                border-radius: 32px;
                border: 2px solid rgba(179, 136, 235, 0.45);
            }
        """)
        lay = QVBoxLayout(self.bg)
        lay.setSpacing(10)
        lay.setContentsMargins(32, 14, 32, 26)

        # Close button
        top = QHBoxLayout()
        top.addStretch()
        btn_x = QPushButton("x")
        btn_x.setFixedSize(28, 28)
        btn_x.setStyleSheet(
            "QPushButton{background:transparent;color:#C5C6C7;font-size:15px;font-weight:bold;border:none;}"
            "QPushButton:hover{color:#FF5A5F;}"
        )
        btn_x.clicked.connect(self._on_close_clicked)
        top.addWidget(btn_x)
        lay.addLayout(top)

        # Title
        title = QLabel("Identity Calibration  \U0001f399\ufe0f")
        title.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("color:#B388EB;background:transparent;border:none;")
        lay.addWidget(title)

        # Counter
        self.counter_lbl = QLabel("")
        self.counter_lbl.setFont(QFont("Segoe UI", 10))
        self.counter_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.counter_lbl.setStyleSheet("color:#C5C6C7;background:transparent;border:none;")
        lay.addWidget(self.counter_lbl)

        # Question box
        self.status_lbl = QLabel("Initializing...")
        self.status_lbl.setFont(QFont("Segoe UI", 14))
        self.status_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_lbl.setWordWrap(True)
        self.status_lbl.setMinimumHeight(72)
        self.status_lbl.setStyleSheet("""
            color:#FFFFFF; background:rgba(25,30,45,185);
            border-radius:14px; padding:14px;
            border:1px solid rgba(179,136,235,0.28);
        """)
        lay.addWidget(self.status_lbl)

        # Mic indicator
        self.indicator = QLabel("\U0001f3a4")
        self.indicator.setFont(QFont("Segoe UI", 46))
        self.indicator.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.indicator.setStyleSheet("color:#66FCF1;background:transparent;border:none;")
        lay.addWidget(self.indicator)

        # Hint
        hint = QLabel("Speak into the mic  or  type your answer below:")
        hint.setFont(QFont("Segoe UI", 10))
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hint.setStyleSheet("color:rgba(197,198,199,0.68);background:transparent;border:none;")
        lay.addWidget(hint)

        # Input row
        row = QHBoxLayout()
        row.setSpacing(10)

        self.text_input = QLineEdit()
        self.text_input.setPlaceholderText("Type your answer here (any language)...")
        self.text_input.setFixedHeight(46)
        self.text_input.setLayoutDirection(Qt.LayoutDirection.RightToLeft)   # supports Arabic/RTL
        self.text_input.setStyleSheet("""
            QLineEdit {
                background:rgba(22,28,48,210); color:#FFFFFF;
                border-radius:23px; padding:0 18px;
                border:1px solid rgba(102,252,241,0.32); font-size:14px;
            }
            QLineEdit:focus { border:2px solid #66FCF1; }
        """)
        self.text_input.returnPressed.connect(self._on_text_submit)
        self.text_input.textChanged.connect(self._on_text_changed)
        row.addWidget(self.text_input)

        self.send_btn = QPushButton("Send  \u2192")
        self.send_btn.setFixedSize(96, 46)
        self.send_btn.setStyleSheet("""
            QPushButton {
                background:#66FCF1; color:#0B0C10;
                border-radius:23px; font-size:13px; font-weight:bold; border:none;
            }
            QPushButton:hover { background:#45A29E; }
            QPushButton:disabled { background:#2a3a3a; color:#666; }
        """)
        self.send_btn.clicked.connect(self._on_text_submit)
        row.addWidget(self.send_btn)

        lay.addLayout(row)
        lay.addStretch()

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(28)
        shadow.setColor(QColor(0, 0, 0, 210))
        shadow.setOffset(0, 0)
        self.bg.setGraphicsEffect(shadow)
        outer.addWidget(self.bg)

    # ── Flow ─────────────────────────────────────────────────────────────

    def start_flow(self):
        welcome = "Welcome! I'll ask you a few questions to calibrate your digital twin. Speak or type your answer."
        self.status_lbl.setText(welcome)
        self._speak(welcome)
        QTimer.singleShot(1800, self.ask_next_question)

    def ask_next_question(self):
        if self.current_question_index < len(self.questions):
            idx  = self.current_question_index
            tot  = len(self.questions)
            self.counter_lbl.setText(f"Question {idx + 1} of {tot}")
            q    = self.questions[idx].get("question", "")
            self.status_lbl.setText(q)
            self.text_input.clear()
            self.text_input.setFocus()
            self.indicator.setStyleSheet("color:#B388EB;background:transparent;border:none;")
            self._speak(q)
            self._start_mic()
        else:
            self._stop_mic()
            self.status_lbl.setText("All done! Your answers have been recorded.  \u2705")
            self.indicator.setStyleSheet("color:#45A29E;background:transparent;border:none;")
            QTimer.singleShot(1800, self.finish_setup)

    # ── Answer handling ───────────────────────────────────────────────────

    def _on_text_submit(self):
        text = self.text_input.text().strip()
        if text:
            self._record_answer(text)

    def _on_text_changed(self, text: str):
        # Stop mic if user starts typing to prevent keyboard noise from triggering speech
        if text.strip() and self._mic_active:
            self._stop_mic()
        elif not text.strip() and not self._mic_active:
            self._start_mic()

    def _record_answer(self, text: str):
        if self.current_question_index >= len(self.questions):
            self.finish_setup()
            return
        q_text = self.questions[self.current_question_index].get("question", "")
        self.answers.append(f"Q: {q_text} | A: {text}")
        self.status_lbl.setText(f'Recorded: "{text[:65]}"')
        self.text_input.clear()
        self.send_btn.setEnabled(False)
        self._stop_mic()
        self.current_question_index += 1
        QTimer.singleShot(1100, lambda: self.send_btn.setEnabled(True))
        QTimer.singleShot(1100, self.ask_next_question)

    def on_speech_recognized(self, text: str):
        if text and len(text) > 1 and self._mic_active:
            self._record_answer(text)

    def on_listening_started(self):
        self._mic_active = True
        self.indicator.setStyleSheet("color:#66FCF1;background:transparent;border:none;")

    def on_listening_stopped(self):
        self.indicator.setStyleSheet("color:#C5C6C7;background:transparent;border:none;")

    # ── Mic helpers ───────────────────────────────────────────────────────

    def _start_mic(self):
        try:
            if not self._own_speech.isRunning():
                self._own_speech.is_running = True
                self._own_speech.start()
        except Exception as e:
            pass   # mic may be unavailable — text input still works

    def _stop_mic(self):
        self._mic_active = False
        try:
            self._own_speech.stop()
        except Exception:
            pass

    # ── TTS ───────────────────────────────────────────────────────────────

    def _speak(self, text: str):
        if not self.tts_engine:
            return
        try:
            self.tts_engine.speak(text)
        except Exception:
            try:
                self.tts_engine.say(text)
                self.tts_engine.runAndWait()
            except Exception:
                pass

    # ── Finish ────────────────────────────────────────────────────────────

    def finish_setup(self):
        self._stop_mic()
        self.setup_completed.emit()

    def _on_close_clicked(self):
        self._stop_mic()
        self.close()

    # ── Drag ─────────────────────────────────────────────────────────────

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self.drag_pos)
            event.accept()



import math

class LoadingWindow(QWidget):
    """Premium Loading/Processing window with animations."""
    def __init__(self, message="Processing Identity Data..."):
        super().__init__()
        self.message = message
        self.init_ui()
        self.angle = 0
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_animation)
        self.timer.start(30)

    def init_ui(self):
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.resize(500, 300)

        layout = QVBoxLayout(self)
        self.bg_widget = QWidget(self)
        self.bg_widget.setStyleSheet("""
            QWidget {
                background-color: rgba(15, 15, 20, 220);
                border-radius: 30px;
                border: 2px solid rgba(102, 252, 241, 0.5);
            }
        """)
        bg_layout = QVBoxLayout(self.bg_widget)
        bg_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Top Bar
        top_bar = QHBoxLayout()
        top_bar.addStretch()
        self.close_btn = QPushButton("✕")
        self.close_btn.setFixedSize(30, 30)
        self.close_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #C5C6C7;
                font-size: 16px;
                font-weight: bold;
                border: none;
            }
            QPushButton:hover {
                color: #FF5A5F;
            }
        """)
        self.close_btn.clicked.connect(self.close)
        top_bar.addWidget(self.close_btn)
        bg_layout.addLayout(top_bar)

        self.spinner = QLabel("⚡")
        self.spinner.setFont(QFont("Segoe UI", 48))
        self.spinner.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.spinner.setStyleSheet("color: #66FCF1; background: transparent; border: none;")
        bg_layout.addWidget(self.spinner)

        self.msg_lbl = QLabel(self.message)
        self.msg_lbl.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        self.msg_lbl.setStyleSheet("color: #FFFFFF; background: transparent; border: none; margin-top: 20px;")
        self.msg_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        bg_layout.addWidget(self.msg_lbl)

        layout.addWidget(self.bg_widget)

    def update_animation(self):
        self.angle = (self.angle + 10) % 360
        opacity = (math.sin(math.radians(self.angle)) + 1) / 2 * 0.5 + 0.5
        self.spinner.setStyleSheet(f"color: rgba(102, 252, 241, {opacity}); background: transparent; border: none;")

    def set_message(self, text):
        self.msg_lbl.setText(text)


# ══════════════════════════════════════════════════════════════════════
#  StyleCaptureWindow — Writing Style Capture
# ══════════════════════════════════════════════════════════════════════
class StyleCaptureWindow(QWidget):
    """
    Final setup step: user writes freely so the AI can learn
    their exact writing style, tone, slang, and sentence rhythm.
    Emits style_captured(text) when the user submits.
    """
    style_captured = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.drag_pos = QPoint()
        self.init_ui()

    def init_ui(self):
        from PyQt6.QtWidgets import QTextEdit, QScrollBar
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.resize(650, 560)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(20, 20, 20, 20)

        self.bg = QWidget(self)
        self.bg.setStyleSheet("""
            QWidget {
                background-color: rgba(10, 12, 18, 215);
                border-radius: 32px;
                border: 2px solid rgba(102, 252, 241, 0.45);
            }
        """)
        lay = QVBoxLayout(self.bg)
        lay.setSpacing(10)
        lay.setContentsMargins(30, 15, 30, 25)

        # ── top bar ────────────────────────────────────────────────────
        top = QHBoxLayout()
        top.addStretch()
        close_btn = QPushButton("✕")
        close_btn.setFixedSize(30, 30)
        close_btn.setStyleSheet("""
            QPushButton { background:transparent; color:#C5C6C7; font-size:16px;
                          font-weight:bold; border:none; }
            QPushButton:hover { color:#FF5A5F; }
        """)
        close_btn.clicked.connect(self.close)
        top.addWidget(close_btn)
        lay.addLayout(top)

        # ── icon + title ───────────────────────────────────────────────
        icon_lbl = QLabel("✍️")
        icon_lbl.setFont(QFont("Segoe UI", 38))
        icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_lbl.setStyleSheet("background:transparent; border:none;")
        lay.addWidget(icon_lbl)

        title = QLabel("Your Style  =  My Soul  ✍️")
        title.setFont(QFont("Segoe UI", 20, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("color:#66FCF1; background:transparent; border:none;")
        lay.addWidget(title)

        sub = QLabel(
            "Write freely in your natural style — any topic: an idea, a rant, a text to a friend.\n"
            "The more you write, the better I can mimic you accurately."
        )
        sub.setFont(QFont("Segoe UI", 11))
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub.setWordWrap(True)
        sub.setStyleSheet("color:#C5C6C7; background:transparent; border:none; margin-bottom:8px;")
        lay.addWidget(sub)

        # ── text area ──────────────────────────────────────────────────
        self.text_edit = QTextEdit()
        self.text_edit.setPlaceholderText(
            "Example: I think AI will change everything in the next 5 years, but most people aren't ready...\n"
            "Or: Hey I had a wild idea this week I've been working on..."
        )
        self.text_edit.setMinimumHeight(160)
        self.text_edit.setStyleSheet("""
            QTextEdit {
                background-color: rgba(25, 30, 45, 200);
                color: #FFFFFF;
                border-radius: 14px;
                padding: 14px;
                border: 1px solid rgba(102, 252, 241, 0.25);
                font-size: 14px;
                font-family: 'Segoe UI';
                line-height: 1.6;
            }
            QTextEdit:focus {
                border: 1.5px solid #66FCF1;
            }
        """)
        lay.addWidget(self.text_edit)

        # ── char counter ───────────────────────────────────────────────
        self.char_lbl = QLabel("0 chars  —  write at least 50")
        self.char_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.char_lbl.setStyleSheet("color:#C5C6C7; font-size:11px; background:transparent; border:none;")
        lay.addWidget(self.char_lbl)
        self.text_edit.textChanged.connect(self._update_char_count)

        # ── skip notice ────────────────────────────────────────────────
        skip_lbl = QLabel("You can skip this step — but style mimicry accuracy will be reduced.")
        skip_lbl.setFont(QFont("Segoe UI", 9))
        skip_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        skip_lbl.setWordWrap(True)
        skip_lbl.setStyleSheet("color: rgba(197,198,199,0.6); background:transparent; border:none;")
        lay.addWidget(skip_lbl)

        # ── buttons ────────────────────────────────────────────────────
        btn_row = QHBoxLayout()
        btn_row.setSpacing(15)

        self.skip_btn = QPushButton("Skip  →")
        self.skip_btn.setFixedHeight(46)
        self.skip_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(197,198,199,0.08);
                color: #C5C6C7;
                border-radius: 23px;
                font-size: 14px;
                font-weight: bold;
                border: 1px solid rgba(197,198,199,0.3);
            }
            QPushButton:hover { background-color: rgba(197,198,199,0.18); }
        """)
        self.skip_btn.clicked.connect(self._on_skip)
        btn_row.addWidget(self.skip_btn)

        self.submit_btn = QPushButton("✅  Save Style  &  Finish Setup")
        self.submit_btn.setFixedHeight(46)
        self.submit_btn.setStyleSheet("""
            QPushButton {
                background-color: #66FCF1;
                color: #0B0C10;
                border-radius: 23px;
                font-size: 14px;
                font-weight: bold;
                border: none;
            }
            QPushButton:hover { background-color: #45A29E; }
            QPushButton:disabled {
                background-color: rgba(102,252,241,0.25);
                color: rgba(11,12,16,0.5);
            }
        """)
        self.submit_btn.setEnabled(False)
        self.submit_btn.clicked.connect(self._on_submit)
        btn_row.addWidget(self.submit_btn, 2)
        lay.addLayout(btn_row)

        # shadow
        from PyQt6.QtWidgets import QGraphicsDropShadowEffect
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(30)
        shadow.setColor(QColor(0, 0, 0, 210))
        shadow.setOffset(0, 0)
        self.bg.setGraphicsEffect(shadow)
        outer.addWidget(self.bg)

    def _update_char_count(self):
        text = self.text_edit.toPlainText()
        n = len(text)
        if n >= 50:
            self.char_lbl.setText(f"{n} chars  ✔")
            self.char_lbl.setStyleSheet("color:#66FCF1; font-size:11px; background:transparent; border:none;")
            self.submit_btn.setEnabled(True)
        else:
            remaining = 50 - n
            self.char_lbl.setText(f"{n} chars  —  {remaining} more to go")
            self.char_lbl.setStyleSheet("color:#C5C6C7; font-size:11px; background:transparent; border:none;")
            self.submit_btn.setEnabled(False)

    def _on_submit(self):
        text = self.text_edit.toPlainText().strip()
        if text:
            self.style_captured.emit(text)
        self.close()

    def _on_skip(self):
        self.style_captured.emit("")
        self.close()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self.drag_pos)
            event.accept()

