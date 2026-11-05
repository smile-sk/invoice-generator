"""
main.py
Точка входу застосунку "Генератор накладних".
Запускає PyQt6-застосунок, застосовує глобальний стиль (QSS) та відкриває
головне вікно з вкладками.
"""

import sys

from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QIcon

from config.settings import APP_ICON_PATH
from ui.components import STYLE_SHEET
from ui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setStyleSheet(STYLE_SHEET)

    if APP_ICON_PATH.exists():
        app.setWindowIcon(QIcon(str(APP_ICON_PATH)))

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
