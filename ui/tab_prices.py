"""
ui/tab_prices.py
Вкладка "Прайс-листи": кілька прайс-листів (як аркуші Excel), один з них
позначений як "Основний". Імпорт з Excel/CSV, інлайн-редагування,
клонування, масова зміна цін на відсоток.
"""

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QPushButton,
    QLabel,
    QFileDialog,
    QHeaderView,
)
from PyQt6.QtCore import Qt

from modules.database import Database
from modules import excel_engine
from ui.components import ask_confirmation, show_info, show_warning, show_error, get_text_uk, get_double_uk

COL_NUM, COL_NAME, COL_PRICE = 0, 1, 2
HEADERS = ["№", "Найменування", "Ціна за кг"]


class PriceListTable(QTableWidget):
    """Таблиця позицій одного конкретного прайс-листа."""

    def __init__(self, db: Database, price_list_id: int, parent=None):
        super().__init__(parent)
        self.db = db
        self.price_list_id = price_list_id

        self.setColumnCount(3)
        self.setHorizontalHeaderLabels(HEADERS)
        self.horizontalHeader().setSectionResizeMode(COL_NAME, QHeaderView.ResizeMode.Stretch)
        self.horizontalHeader().setSectionResizeMode(COL_NUM, QHeaderView.ResizeMode.ResizeToContents)
        self.horizontalHeader().setSectionResizeMode(COL_PRICE, QHeaderView.ResizeMode.ResizeToContents)
        self.verticalHeader().setVisible(False)

        self._loading = False
        self.itemChanged.connect(self._on_item_changed)

        self.reload()

    def reload(self):
        self._loading = True
        items = self.db.list_items(self.price_list_id)
        self.setRowCount(len(items))
        for row_idx, item in enumerate(items):
            self._set_row(row_idx, item)
        self._loading = False

    def _set_row(self, row_idx, item):
        num_cell = QTableWidgetItem(str(row_idx + 1))
        num_cell.setFlags(num_cell.flags() & ~Qt.ItemFlag.ItemIsEditable)
        num_cell.setData(Qt.ItemDataRole.UserRole, item.id)
        self.setItem(row_idx, COL_NUM, num_cell)

        name_cell = QTableWidgetItem(item.name)
        self.setItem(row_idx, COL_NAME, name_cell)

        price_cell = QTableWidgetItem(f"{item.price_per_kg:g}")
        self.setItem(row_idx, COL_PRICE, price_cell)

    def _on_item_changed(self, cell: QTableWidgetItem):
        if self._loading:
            return
        row = cell.row()
        num_cell = self.item(row, COL_NUM)
        item_id = num_cell.data(Qt.ItemDataRole.UserRole)
        if item_id is None:
            return

        name = self.item(row, COL_NAME).text().strip()
        price_text = self.item(row, COL_PRICE).text().strip().replace(",", ".")
        try:
            price = float(price_text)
        except ValueError:
            show_warning(self, "Помилка", "Ціна за кг має бути числом.")
            self.reload()
            return

        self.db.update_item(item_id, name=name, price_per_kg=price)

    def add_empty_row(self):
        new_id = self.db.add_item(self.price_list_id, "Нова позиція", 0)
        self.reload()
        # Ставимо фокус на нову позицію (останній рядок)
        self.setCurrentCell(self.rowCount() - 1, COL_NAME)
        self.editItem(self.item(self.rowCount() - 1, COL_NAME))

    def delete_selected_row(self):
        row = self.currentRow()
        if row < 0:
            return
        name = self.item(row, COL_NAME).text()
        confirmed = ask_confirmation(
            self, "Видалити позицію",
            f"Ви впевнені, що хочете видалити позицію «{name}»?",
            danger=True,
        )
        if not confirmed:
            return
        item_id = self.item(row, COL_NUM).data(Qt.ItemDataRole.UserRole)
        self.db.delete_item(item_id)
        self.reload()

    def import_rows(self, rows: list[tuple[str, float]]):
        self.db.import_items_from_rows(self.price_list_id, rows)
        self.reload()

    def adjust_prices(self, percent: float):
        self.db.adjust_prices_by_percent(self.price_list_id, percent)
        self.reload()


class PriceListsTab(QWidget):
    """Головна вкладка: перемикач прайс-листів + панель дій над ними."""

    def __init__(self, db: Database, parent=None):
        super().__init__(parent)
        self.db = db

        layout = QVBoxLayout(self)

        title = QLabel("Прайс-листи")
        title.setObjectName("pageTitle")
        layout.addWidget(title)

        toolbar = QHBoxLayout()
        self.btn_new_list = QPushButton("+ Новий прайс-лист")
        self.btn_clone = QPushButton("Клонувати")
        self.btn_set_active = QPushButton("Зробити основним")
        self.btn_rename = QPushButton("Перейменувати")
        self.btn_delete_list = QPushButton("Видалити прайс-лист")
        for b in (self.btn_clone, self.btn_set_active, self.btn_rename, self.btn_delete_list):
            b.setObjectName("secondaryButton")
        toolbar.addWidget(self.btn_new_list)
        toolbar.addWidget(self.btn_clone)
        toolbar.addWidget(self.btn_set_active)
        toolbar.addWidget(self.btn_rename)
        toolbar.addWidget(self.btn_delete_list)
        toolbar.addStretch()
        layout.addLayout(toolbar)

        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)

        row_toolbar = QHBoxLayout()
        self.btn_add_row = QPushButton("+ Позиція")
        self.btn_delete_row = QPushButton("Видалити позицію")
        self.btn_import = QPushButton("Імпорт з Excel/CSV")
        self.btn_adjust_percent = QPushButton("Змінити ціни на %")
        for b in (self.btn_delete_row, self.btn_import, self.btn_adjust_percent):
            b.setObjectName("secondaryButton")
        row_toolbar.addWidget(self.btn_add_row)
        row_toolbar.addWidget(self.btn_delete_row)
        row_toolbar.addWidget(self.btn_import)
        row_toolbar.addWidget(self.btn_adjust_percent)
        row_toolbar.addStretch()
        layout.addLayout(row_toolbar)

        self.btn_new_list.clicked.connect(self._on_new_list)
        self.btn_clone.clicked.connect(self._on_clone_list)
        self.btn_set_active.clicked.connect(self._on_set_active)
        self.btn_rename.clicked.connect(self._on_rename_list)
        self.btn_delete_list.clicked.connect(self._on_delete_list)

        self.btn_add_row.clicked.connect(self._on_add_row)
        self.btn_delete_row.clicked.connect(self._on_delete_row)
        self.btn_import.clicked.connect(self._on_import)
        self.btn_adjust_percent.clicked.connect(self._on_adjust_percent)

        self.reload_tabs()

    # ------------------------------------------------------------------
    # Побудова вкладок
    # ------------------------------------------------------------------

    def reload_tabs(self):
        self.tabs.clear()
        price_lists = self.db.list_price_lists()

        if not price_lists:
            self.db.create_price_list("Прайс-лист 1", make_active=True)
            price_lists = self.db.list_price_lists()

        for pl in price_lists:
            table = PriceListTable(self.db, pl.id)
            label = f"★ {pl.name}" if pl.is_active else pl.name
            self.tabs.addTab(table, label)

    def _current_table(self) -> PriceListTable | None:
        return self.tabs.currentWidget()

    def _current_price_list_id(self) -> int | None:
        table = self._current_table()
        return table.price_list_id if table else None

    # ------------------------------------------------------------------
    # Дії над прайс-листами
    # ------------------------------------------------------------------

    def _on_new_list(self):
        name, ok = get_text_uk(self, "Новий прайс-лист", "Назва прайс-листа:")
        if ok and name.strip():
            self.db.create_price_list(name.strip())
            self.reload_tabs()

    def _on_clone_list(self):
        pl_id = self._current_price_list_id()
        if pl_id is None:
            return
        current_name = self.tabs.tabText(self.tabs.currentIndex()).lstrip("★ ")
        name, ok = get_text_uk(
            self, "Клонувати прайс-лист", "Назва нового прайс-листа:",
            text=f"{current_name} (копія)",
        )
        if ok and name.strip():
            self.db.clone_price_list(pl_id, name.strip())
            self.reload_tabs()

    def _on_set_active(self):
        pl_id = self._current_price_list_id()
        if pl_id is None:
            return
        self.db.set_active_price_list(pl_id)
        self.reload_tabs()

    def _on_rename_list(self):
        pl_id = self._current_price_list_id()
        if pl_id is None:
            return
        current_name = self.tabs.tabText(self.tabs.currentIndex()).lstrip("★ ")
        name, ok = get_text_uk(
            self, "Перейменувати прайс-лист", "Нова назва:", text=current_name
        )
        if ok and name.strip():
            self.db.rename_price_list(pl_id, name.strip())
            self.reload_tabs()

    def _on_delete_list(self):
        pl_id = self._current_price_list_id()
        if pl_id is None:
            return
        if self.tabs.count() <= 1:
            show_warning(self, "Неможливо видалити", "Повинен залишатися хоча б один прайс-лист.")
            return
        confirmed = ask_confirmation(
            self, "Видалити прайс-лист",
            "Ви впевнені? Усі позиції цього прайс-листа буде видалено.",
            danger=True,
        )
        if confirmed:
            self.db.delete_price_list(pl_id)
            if not self.db.get_active_price_list() and self.db.list_price_lists():
                self.db.set_active_price_list(self.db.list_price_lists()[0].id)
            self.reload_tabs()

    # ------------------------------------------------------------------
    # Дії над позиціями поточного прайс-листа
    # ------------------------------------------------------------------

    def _on_add_row(self):
        table = self._current_table()
        if table:
            table.add_empty_row()

    def _on_delete_row(self):
        table = self._current_table()
        if table:
            table.delete_selected_row()

    def _on_import(self):
        table = self._current_table()
        if not table:
            return
        path, _ = QFileDialog.getOpenFileName(
            self, "Обрати файл прайс-листа", "", "Excel/CSV (*.xlsx *.xls *.csv)"
        )
        if not path:
            return
        try:
            if path.lower().endswith(".csv"):
                rows = excel_engine.import_price_rows_from_csv(path)
            else:
                rows = excel_engine.import_price_rows_from_excel(path)
        except Exception as exc:
            show_error(self, "Помилка імпорту", f"Не вдалося прочитати файл:\n{exc}")
            return

        if not rows:
            show_info(self, "Імпорт", "У файлі не знайдено жодної позиції.")
            return

        table.import_rows(rows)
        show_info(self, "Імпорт завершено", f"Додано позицій: {len(rows)}")

    def _on_adjust_percent(self):
        table = self._current_table()
        if not table:
            return
        percent, ok = get_double_uk(
            self, "Змінити ціни на %",
            "Відсоток зміни (наприклад, 10 -> +10%, -5 -> -5%):",
            value=0, min_value=-99, max_value=1000, decimals=2,
        )
        if ok and percent != 0:
            table.adjust_prices(percent)
