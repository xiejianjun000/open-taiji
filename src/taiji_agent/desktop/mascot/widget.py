"""吉祥物组件"""
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtGui import QColor, QPainter, QRadialGradient, QPalette

from .states import MascotState, MASCOT_COLORS, MASCOT_EMOJIS
from .lottie_player import LottiePlayer


class MascotWidget(QWidget):
    """吉祥物组件 - 绿色太极主题"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.state = MascotState.IDLE
        self.animation_timer = QTimer()
        self.animation_timer.timeout.connect(self._update_animation)
        self.animation_frame = 0
        self.breath_offset = 0

        self.lottie_player = LottiePlayer()

        self._setup_ui()

    def _setup_ui(self):
        """设置 UI"""
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(layout)

        self.canvas = QLabel()
        self.canvas.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.canvas)

        self._draw_mascot()

    def set_state(self, state: str):
        """设置吉祥物状态"""
        try:
            self.state = MascotState(state)
        except ValueError:
            self.state = MascotState.IDLE

        self._draw_mascot()

        if self.state in [MascotState.THINKING, MascotState.SPEAKING]:
            self.animation_timer.start(100)
        else:
            self.animation_timer.stop()
            self.animation_frame = 0

    def _update_animation(self):
        """更新动画帧"""
        self.animation_frame += 1
        self.breath_offset = (self.breath_offset + 1) % 100
        self._draw_mascot()

    def _draw_mascot(self):
        """绘制吉祥物"""
        color = QColor(MASCOT_COLORS.get(self.state, "#4CAF50"))

        if self.state == MascotState.SPEAKING:
            pulse = abs(self.animation_frame % 20 - 10) / 10
            color = QColor(int(0 + pulse * 50), int(200 + pulse * 55), int(80 + pulse * 36))
        elif self.state == MascotState.THINKING:
            color = QColor("#4CAF50")
        elif self.state == MascotState.IDLE:
            breathe = abs(self.breath_offset % 50 - 25) / 25 * 20
            color = QColor(int(129 + breathe), int(199 + breathe), int(132 + breathe))

        self.setStyleSheet(f"""
            QWidget {{
                background-color: {color.name()};
                border-radius: 20px;
                border: 3px solid #2E7D32;
            }}
        """)

        emoji = MASCOT_EMOJIS.get(self.state, "🟢")
        self.canvas.setText(f"<span style='font-size: 80px;'>{emoji}</span>")

    def paintEvent(self, event):
        """绘制事件 - 可扩展为自定义绘制"""
        super().paintEvent(event)
