"""聊天视图组件"""
from PyQt6.QtWidgets import QTextEdit, QLabel
from PyQt6.QtCore import Qt


class ChatView(QTextEdit):
    """聊天视图"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self._setup_style()

    def _setup_style(self):
        """设置样式"""
        self.setStyleSheet("""
            QTextEdit {
                background-color: #16213e;
                color: #e0e0e0;
                border: 1px solid #4CAF50;
                border-radius: 8px;
                padding: 12px;
            }
        """)

    def add_user_message(self, message: str):
        """添加用户消息"""
        self.append(f"""
        <div style='text-align: right; margin-bottom: 10px;'>
            <span style='background-color: #4CAF50; color: white; 
                        padding: 8px 16px; border-radius: 16px;
                        display: inline-block;'>
                {self._escape_html(message)}
            </span>
        </div>
        """)
        self.verticalScrollBar().setValue(
            self.verticalScrollBar().maximum()
        )

    def add_assistant_message(self, message: str):
        """添加助手消息"""
        self.append(f"""
        <div style='text-align: left; margin-bottom: 10px;'>
            <span style='background-color: #2E7D32; color: white;
                        padding: 8px 16px; border-radius: 16px;
                        display: inline-block;'>
                {self._escape_html(message)}
            </span>
        </div>
        """)
        self.verticalScrollBar().setValue(
            self.verticalScrollBar().maximum()
        )

    def _escape_html(self, text: str) -> str:
        """转义 HTML"""
        return (text
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace("\n", "<br>"))

    def clear_chat(self):
        """清空聊天"""
        self.clear()
