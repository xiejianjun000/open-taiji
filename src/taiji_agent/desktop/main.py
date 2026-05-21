"""Taiji Agent 桌面应用入口"""
import sys
from PyQt6.QtWidgets import QApplication

from .window import TaijiWindow


def main():
    """主函数"""
    app = QApplication(sys.argv)
    app.setApplicationName("Taiji Agent")
    app.setApplicationVersion("2.0.0")

    window = TaijiWindow()
    window.show()

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
