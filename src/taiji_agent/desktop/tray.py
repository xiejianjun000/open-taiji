"""系统托盘管理"""
from PyQt6.QtWidgets import QSystemTrayIcon, QMenu
from PyQt6.QtGui import QIcon, QAction, QPixmap, QPainter, QColor
from PyQt6.QtCore import QObject, pyqtSignal, Qt


class TrayManager(QObject):
    """系统托盘管理"""

    show_window = pyqtSignal()
    quick_chat = pyqtSignal()
    show_settings = pyqtSignal()
    quit_app = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_window = parent
        self.tray: QSystemTrayIcon | None = None

    def create_tray(self):
        """创建托盘"""
        self.tray = QSystemTrayIcon(self.parent_window)

        icon = self._create_green_icon()
        self.tray.setIcon(icon)

        self._create_menu()

        self.tray.setToolTip("Taiji Agent 2.0")
        self.tray.activated.connect(self._on_tray_activated)

        self.tray.show()

    def _create_green_icon(self) -> QIcon:
        """创建绿色图标"""
        pixmap = QPixmap(32, 32)
        pixmap.fill(Qt.GlobalColor.transparent)

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        painter.setBrush(QColor("#4CAF50"))
        painter.setPen(QColor("#2E7D32"))
        painter.drawEllipse(4, 4, 24, 24)

        painter.setBrush(QColor("#2E7D32"))
        painter.drawEllipse(12, 8, 8, 8)

        painter.end()

        return QIcon(pixmap)

    def _create_menu(self):
        """创建托盘菜单"""
        menu = QMenu()

        show_action = QAction("显示主窗口", menu)
        show_action.triggered.connect(self._show_window)
        menu.addAction(show_action)

        menu.addSeparator()

        quick_chat_action = QAction("快速对话", menu)
        quick_chat_action.triggered.connect(self._quick_chat)
        menu.addAction(quick_chat_action)

        search_memory_action = QAction("记忆查询", menu)
        search_memory_action.triggered.connect(self._search_memory)
        menu.addAction(search_memory_action)

        menu.addSeparator()

        settings_action = QAction("设置", menu)
        settings_action.triggered.connect(self._show_settings)
        menu.addAction(settings_action)

        menu.addSeparator()

        quit_action = QAction("退出", menu)
        quit_action.triggered.connect(self._quit)
        menu.addAction(quit_action)

        self.tray.setContextMenu(menu)

    def show_notification(self, title: str, message: str):
        """显示通知"""
        if self.tray:
            self.tray.showMessage(title, message)

    def _on_tray_activated(self, reason):
        """托盘点击事件"""
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self._show_window()

    def _show_window(self):
        """显示窗口"""
        self.show_window.emit()
        if self.parent_window:
            self.parent_window.show()
            self.parent_window.raise_()
            self.parent_window.activateWindow()

    def _quick_chat(self):
        """快速对话"""
        self.quick_chat.emit()

    def _search_memory(self):
        """搜索记忆"""
        self._show_window()

    def _show_settings(self):
        """显示设置"""
        self.show_settings.emit()

    def _quit(self):
        """退出"""
        self.quit_app.emit()
        if self.parent_window:
            self.parent_window.close()
