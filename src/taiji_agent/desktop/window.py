"""Taiji Agent 主窗口"""
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QPushButton, QTextEdit, QLineEdit, QLabel
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QPalette

from .mascot.widget import MascotWidget
from .chat_view import ChatView
from .tray import TrayManager


class TaijiWindow(QMainWindow):
    """Taiji Agent 主窗口"""

    message_sent = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Taiji Agent 2.0")
        self.setMinimumSize(900, 650)

        self._setup_ui()
        self._setup_tray()

        self.setStyleSheet("""
            QMainWindow {
                background-color: #1a1a2e;
            }
            QLabel {
                color: #4CAF50;
                font-size: 14px;
            }
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QTextEdit {
                background-color: #16213e;
                color: #e0e0e0;
                border: 1px solid #4CAF50;
                border-radius: 8px;
                padding: 8px;
            }
            QLineEdit {
                background-color: #16213e;
                color: #e0e0e0;
                border: 1px solid #4CAF50;
                border-radius: 4px;
                padding: 8px;
            }
        """)

    def _setup_ui(self):
        """设置 UI"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QHBoxLayout()
        central_widget.setLayout(main_layout)

        left_panel = QVBoxLayout()
        left_panel.setSpacing(20)

        self.mascot = MascotWidget()
        self.mascot.setFixedSize(200, 250)
        left_panel.addWidget(self.mascot, 0, Qt.AlignmentFlag.AlignCenter)

        self.status_label = QLabel("状态: 空闲")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        left_panel.addWidget(self.status_label)

        left_panel.addStretch()

        quick_buttons = QVBoxLayout()
        quick_buttons.addWidget(QPushButton("📧 邮件"))
        quick_buttons.addWidget(QPushButton("📁 文件"))
        quick_buttons.addWidget(QPushButton("🔍 搜索"))
        left_panel.addLayout(quick_buttons)

        main_layout.addLayout(left_panel, 1)

        right_panel = QVBoxLayout()
        right_panel.setSpacing(15)

        self.chat_view = ChatView()
        right_panel.addWidget(self.chat_view, 1)

        input_layout = QHBoxLayout()
        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText("输入消息...")
        self.input_field.returnPressed.connect(self._on_send)

        send_btn = QPushButton("▶")
        send_btn.setFixedWidth(50)
        send_btn.clicked.connect(self._on_send)

        input_layout.addWidget(self.input_field, 1)
        input_layout.addWidget(send_btn)

        right_panel.addLayout(input_layout)

        memory_layout = QHBoxLayout()
        memory_layout.addWidget(QLabel("🔍 Memory Tree:"))
        memory_btn = QPushButton("查看记忆树")
        memory_btn.clicked.connect(self._show_memory)
        memory_layout.addWidget(memory_btn)
        right_panel.addLayout(memory_layout)

        main_layout.addLayout(right_panel, 3)

    def _setup_tray(self):
        """设置系统托盘"""
        self.tray = TrayManager(self)
        self.tray.create_tray()

    def _on_send(self):
        """发送消息"""
        text = self.input_field.text().strip()
        if not text:
            return

        self.chat_view.add_user_message(text)
        self.message_sent.emit(text)
        self.input_field.clear()

        self.mascot.set_state("thinking")
        self.status_label.setText("状态: 思考中...")

    def _show_memory(self):
        """显示记忆树"""
        pass

    def set_response(self, response: str):
        """设置响应"""
        self.chat_view.add_assistant_message(response)
        self.mascot.set_state("idle")
        self.status_label.setText("状态: 空闲")

    def set_speaking(self, audio_data: bytes):
        """设置吉祥物说话"""
        self.mascot.set_state("speaking")
