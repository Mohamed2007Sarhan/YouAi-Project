import sys
import math
import random
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QHBoxLayout, 
    QPushButton, QGraphicsDropShadowEffect
)
from PyQt6.QtCore import Qt, QTimer, QPoint, QPointF, QPropertyAnimation, QEasingCurve, pyqtProperty
from PyQt6.QtGui import QPainter, QColor, QRadialGradient, QFont, QPainterPath

class DigitalVisualizerWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(400, 400)
        self.is_listening = True
        
        self.cols = 12
        self.rows = 12
        self.spacing = 6
        
        # Colors
        self.cyan_base = QColor(102, 252, 241)
        self.blue_base = QColor(69, 162, 158)
        self.purple_base = QColor(179, 136, 235)
        self.dark_purple = QColor(120, 80, 180)
        
        self.grid = [[random.random() for _ in range(self.cols)] for _ in range(self.rows)]
        
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.animate_grid)
        self.timer.start(80)
        self.time_step = 0

    def animate_grid(self):
        self.time_step += 0.2
        for r in range(self.rows):
            for c in range(self.cols):
                if self.is_listening:
                    if random.random() > 0.6:
                        self.grid[r][c] = random.uniform(0.1, 1.0)
                    else:
                        self.grid[r][c] = max(0.1, self.grid[r][c] - 0.1)
                else:
                    dist = math.sqrt((r - self.rows/2)**2 + (c - self.cols/2)**2)
                    self.grid[r][c] = (math.sin(dist - self.time_step * 3) + 1) / 2
        self.update()

    def set_listening(self, state):
        self.is_listening = state
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()
        
        grid_w = min(w, h) * 0.7
        grid_h = grid_w
        
        sq_w = (grid_w - (self.cols - 1) * self.spacing) / self.cols
        sq_h = (grid_h - (self.rows - 1) * self.spacing) / self.rows
        
        start_x = (w - grid_w) / 2
        start_y = (h - grid_h) / 2
        
        for r in range(self.rows):
            for c in range(self.cols):
                opacity = self.grid[r][c]
                
                if self.is_listening:
                    base = self.cyan_base if (r+c)%2==0 else self.blue_base
                else:
                    base = self.purple_base if (r+c)%2==0 else self.dark_purple
                    
                color = QColor(base)
                color.setAlphaF(opacity)
                
                painter.setBrush(color)
                painter.setPen(Qt.PenStyle.NoPen)
                
                x = start_x + c * (sq_w + self.spacing)
                y = start_y + r * (sq_h + self.spacing)
                
                painter.drawRoundedRect(int(x), int(y), int(sq_w), int(sq_h), 4, 4)


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.init_ui()
        self.drag_pos = QPoint()

    def init_ui(self):
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.resize(700, 700)

        # Main Layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)

        # Background Container with Rounded Corners
        self.bg_widget = QWidget(self)
        self.bg_widget.setStyleSheet("""
            QWidget {
                background-color: rgba(15, 15, 20, 150);
                border-radius: 40px;
                border: 2px solid rgba(102, 252, 241, 0.2);
            }
        """)
        
        bg_layout = QVBoxLayout(self.bg_widget)
        
        # Top Bar (Close button)
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
        title_lbl = QLabel("YOU AI")
        title_font = QFont("Segoe UI", 36, QFont.Weight.Bold)
        title_lbl.setFont(title_font)
        title_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_lbl.setStyleSheet("""
            color: #66FCF1;
            letter-spacing: 5px;
            background: transparent;
            border: none;
        """)
        bg_layout.addWidget(title_lbl)

        subtitle_lbl = QLabel("Digital Clone")
        subtitle_font = QFont("Segoe UI", 14)
        subtitle_lbl.setFont(subtitle_font)
        subtitle_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle_lbl.setStyleSheet("color: #C5C6C7; background: transparent; border: none;")
        bg_layout.addWidget(subtitle_lbl)

        # Spacer
        bg_layout.addStretch(1)

        # Digital Visualizer Widget
        self.visualizer = DigitalVisualizerWidget()
        bg_layout.addWidget(self.visualizer, alignment=Qt.AlignmentFlag.AlignCenter)

        # Spacer
        bg_layout.addStretch(1)

        # Transcript Area
        self.transcript_lbl = QLabel("I'm listening...")
        self.transcript_lbl.setFont(QFont("Segoe UI", 18))
        self.transcript_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.transcript_lbl.setWordWrap(True)
        self.transcript_lbl.setStyleSheet("""
            color: #FFFFFF;
            background-color: rgba(31, 40, 51, 150);
            border-radius: 15px;
            padding: 15px;
            border: 1px solid rgba(102, 252, 241, 0.2);
        """)
        self.transcript_lbl.setMinimumHeight(150)
        bg_layout.addWidget(self.transcript_lbl)

        # Drop Shadow for the main window
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(20)
        shadow.setColor(QColor(0, 0, 0, 180))
        shadow.setOffset(0, 0)
        self.bg_widget.setGraphicsEffect(shadow)

        layout.addWidget(self.bg_widget)

    # Allow dragging the frameless window
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self.drag_pos)
            event.accept()

    def update_transcript(self, text):
        self.transcript_lbl.setText(f"« {text} »")
        
    def set_thinking_state(self):
        self.visualizer.set_listening(False)
        self.transcript_lbl.setText("Processing...")
        self.transcript_lbl.setStyleSheet("""
            color: #B388EB;
            background-color: rgba(31, 40, 51, 150);
            border-radius: 15px;
            padding: 15px;
            border: 1px solid rgba(179, 136, 235, 0.3);
        """)

    def set_listening_state(self):
        self.visualizer.set_listening(True)
        self.transcript_lbl.setStyleSheet("""
            color: #FFFFFF;
            background-color: rgba(31, 40, 51, 150);
            border-radius: 15px;
            padding: 15px;
            border: 1px solid rgba(102, 252, 241, 0.2);
        """)

