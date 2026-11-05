"""
ui/main_window.py
Головне вікно застосунку: контролер вкладок "Прайс-листи" та "Створення накладної".
Логіка Excel/БД сюди НЕ виноситься - тільки компонування UI.
"""

from PyQt6.QtWidgets import QMainWindow, QTabWidget, QWidget, QVBoxLayout, QHBoxLayout, QLabel
from PyQt6.QtGui import QPixmap
from PyQt6.QtCore import Qt

from config.settings import settings, LOGO_PATH
from modules.database import Database
from ui.tab_prices import PriceListsTab
from ui.tab_invoice import InvoiceTab


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Генератор накладних")
        self.setMinimumSize(1000, 650)

        self.db = Database()

        central = QWidget()
        central_layout = QVBoxLayout(central)
        central_layout.setContentsMargins(12, 8, 16, 12)

        self.tabs = QTabWidget()
        self.tabs.setObjectName("mainTabs")
        self.tabs.tabBar().setObjectName("mainTabBar")
        central_layout.addWidget(self.tabs)

        self.setCentralWidget(central)

        self.tabs.addTab(PriceListsTab(self.db), "Прайс-листи")
        self.tabs.addTab(InvoiceTab(self.db), "Створення накладної")

        self._add_logo_to_tab_bar()

    def _add_logo_to_tab_bar(self):
        """
        Логотип у правому куті рядка перемикання вкладок (лише для оформлення).
        Розмір зафіксовано під оригінал зображення (240x65). Відступ праворуч
        додається через layout контейнера, а не через contentsMargins самого
        QLabel з pixmap - інакше Qt може "зрізати" частину зображення.
        """
        if not LOGO_PATH.exists():
            return
        pixmap = QPixmap(str(LOGO_PATH))

        logo_label = QLabel()
        logo_label.setPixmap(pixmap)
        logo_label.setFixedSize(pixmap.size())
        logo_label.setContentsMargins(0, 0, 0, 0)
        logo_label.setStyleSheet("background: transparent;")

        container = QWidget()
        container.setStyleSheet("background: transparent;")
        container_layout = QHBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 12, 0)
        container_layout.addWidget(logo_label)

        self.tabs.setCornerWidget(container, Qt.Corner.TopRightCorner)

    def closeEvent(self, event):
        settings.save()
        super().closeEvent(event)
