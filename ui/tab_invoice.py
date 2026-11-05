"""
ui/tab_invoice.py
Вкладка "Створення накладної": динамічна таблиця з автодоповненням назв
із активного прайс-листа, автопідрахунком сум, підсумковим рядком та
збереженням у стилізований .xlsx з автоматичним відкриттям у Excel
(правки та друк користувач виконує вже в Excel).
"""

import os
import sys
from datetime import date

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QTableWidget,
    QTableWidgetItem,
    QPushButton,
    QLabel,
    QFileDialog,
    QHeaderView,
    QStyledItemDelegate,
    QLineEdit,
    QCompleter,
    QDoubleSpinBox,
    QSpinBox,
    QComboBox,
    QAbstractSpinBox,
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QKeyEvent

from modules.database import Database
from modules.excel_engine import InvoiceRow, generate_invoice_xlsx
from modules.labels_engine import (
    LabelItem,
    generate_labels_docx,
    LabelsError,
    TEA_TYPES_UI,
    UI_TO_FULL_TYPE,
)
from ui.components import ask_confirmation, show_info, show_warning, show_error

COL_NUM, COL_NAME, COL_QTY, COL_PRICE, COL_SUM, COL_TYPE, COL_LABELS = 0, 1, 2, 3, 4, 5, 6
HEADERS = ["№", "Найменування", "Кількість, кг", "Ціна за кг", "Сума", "Тип чаю", "Наклейки"]


class QuantitySpinDelegate(QStyledItemDelegate):
    """
    Делегат для колонки "Кількість, кг": редактор зі стрілками +/- (крок 0.1).
    Значення завжди відображається через кому (як звично для укр. користувача),
    навіть якщо введено крапку.
    """

    def createEditor(self, parent, option, index):
        editor = QDoubleSpinBox(parent)
        editor.setDecimals(2)
        editor.setMinimum(0)
        editor.setMaximum(100000)
        editor.setSingleStep(0.1)
        editor.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.UpDownArrows)
        return editor

    def setEditorData(self, editor, index):
        text = str(index.data(Qt.ItemDataRole.EditRole) or "").strip().replace(",", ".")
        try:
            value = float(text) if text else 0.0
        except ValueError:
            value = 0.0
        editor.setValue(value)

    def setModelData(self, editor, model, index):
        text = f"{editor.value():g}".replace(".", ",")
        model.setData(index, text, Qt.ItemDataRole.EditRole)


class TeaTypeDelegate(QStyledItemDelegate):
    """Делегат для колонки "Тип чаю": випадаючий список (короткі назви для UI)."""

    def createEditor(self, parent, option, index):
        editor = QComboBox(parent)
        editor.addItems(TEA_TYPES_UI)
        # Одразу показуємо випадаючий список при вході в редагування,
        # щоб перший Enter по комірці розгортав перелік типів.
        QTimer.singleShot(0, editor.showPopup)
        # Коли користувач обрав пункт зі списку (Enter/клік) - одразу
        # підтверджуємо і закриваємо редактор, без повторного відкриття.
        editor.activated.connect(lambda _idx: self._commit(editor))
        return editor

    def _commit(self, editor):
        self.commitData.emit(editor)
        self.closeEditor.emit(editor)

    def setEditorData(self, editor, index):
        current = str(index.data(Qt.ItemDataRole.EditRole) or "")
        idx = editor.findText(current)
        editor.setCurrentIndex(idx if idx >= 0 else 0)

    def setModelData(self, editor, model, index):
        model.setData(index, editor.currentText(), Qt.ItemDataRole.EditRole)


class LabelCountDelegate(QStyledItemDelegate):
    """Делегат для колонки "Наклейки": ціле число зі стрілками, крок 1, від 0."""

    def createEditor(self, parent, option, index):
        editor = QSpinBox(parent)
        editor.setMinimum(0)
        editor.setMaximum(1000)
        editor.setSingleStep(1)
        editor.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.UpDownArrows)
        return editor

    def setEditorData(self, editor, index):
        text = str(index.data(Qt.ItemDataRole.EditRole) or "").strip()
        try:
            editor.setValue(int(text) if text else 0)
        except ValueError:
            editor.setValue(0)

    def setModelData(self, editor, model, index):
        model.setData(index, str(editor.value()), Qt.ItemDataRole.EditRole)


class NameAutocompleteDelegate(QStyledItemDelegate):
    """
    Делегат для колонки "Найменування": підказки з активного прайс-листа
    (пошук підрядка, без урахування регістру). Ручне введення теж дозволене.
    """

    def __init__(self, db: Database, parent=None):
        super().__init__(parent)
        self.db = db

    def createEditor(self, parent, option, index):
        editor = QLineEdit(parent)
        active = self.db.get_active_price_list()
        names = []
        if active:
            names = [item.name for item in self.db.list_items(active.id)]
        completer = QCompleter(names, editor)
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        completer.setFilterMode(Qt.MatchFlag.MatchContains)
        editor.setCompleter(completer)
        return editor


class InvoiceTable(QTableWidget):
    """Таблиця позицій накладної з автопідрахунком сум."""

    def __init__(self, db: Database, on_totals_changed, parent=None):
        super().__init__(parent)
        self.db = db
        self.on_totals_changed = on_totals_changed

        self.setColumnCount(7)
        self.setHorizontalHeaderLabels(HEADERS)
        self.horizontalHeader().setSectionResizeMode(COL_NAME, QHeaderView.ResizeMode.Stretch)
        for col in (COL_NUM, COL_QTY, COL_PRICE, COL_SUM, COL_LABELS):
            self.horizontalHeader().setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)
        # Тип чаю: фіксована ширина, достатня для найдовшого варіанту у списку,
        # щоб випадаючий список одразу було читабельно (за рахунок "Найменування")
        self.horizontalHeader().setSectionResizeMode(COL_TYPE, QHeaderView.ResizeMode.Fixed)
        self.setColumnWidth(COL_TYPE, 210)
        self.verticalHeader().setVisible(False)

        self.setItemDelegateForColumn(COL_NAME, NameAutocompleteDelegate(db, self))
        self.setItemDelegateForColumn(COL_QTY, QuantitySpinDelegate(self))
        self._type_delegate = TeaTypeDelegate(self)
        self.setItemDelegateForColumn(COL_TYPE, self._type_delegate)
        self.setItemDelegateForColumn(COL_LABELS, LabelCountDelegate(self))

        self._loading = False
        self._type_just_committed = False
        # Коли тип чаю підтверджено зі списку - ставимо прапорець, щоб
        # наступний Enter перейшов на наступний рядок, а не відкрив список знову.
        self._type_delegate.closeEditor.connect(self._on_type_committed)
        self.itemChanged.connect(self._on_item_changed)
        self.currentCellChanged.connect(self._on_current_cell_changed)

        self.add_empty_row()

    def _on_type_committed(self, *args):
        self._type_just_committed = True

    def _on_current_cell_changed(self, cur_row, cur_col, prev_row, prev_col):
        # Прапорець "тип щойно підтверджено" діє рівно на один Enter-перехід.
        # Якщо перехід уже стався (змінилась комірка) - скидаємо, щоб на новій
        # комірці "Тип чаю" перший Enter знову відкривав список.
        if not (cur_row == prev_row and cur_col == COL_TYPE):
            self._type_just_committed = False

    def keyPressEvent(self, event: QKeyEvent):
        """
        Enter по ячейці (коли редактор уже закрито першим Enter) переводить
        фокус на ту саму колонку наступного рядка, за потреби створюючи новий
        порожній рядок. Так заповнення йде згори вниз у межах однієї колонки.
        """
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            # Якщо зараз відкрито редактор комірки - не перехоплюємо,
            # хай перший Enter підтвердить значення штатно.
            if self.state() != QTableWidget.State.EditingState:
                row = self.currentRow()
                col = self.currentColumn()
                if row < 0:
                    return
                if col < 0:
                    col = COL_NAME
                # Для "Тип чаю" перший Enter має відкрити випадаючий список.
                # Але якщо тип щойно підтверджено (вибір зі списку) - навпаки,
                # переходимо на наступний рядок, а не відкриваємо список знову.
                if col == COL_TYPE and not self._type_just_committed:
                    self.edit(self.currentIndex())
                    event.accept()
                    return
                self._type_just_committed = False
                next_row = row + 1
                if next_row >= self.rowCount():
                    self.add_empty_row()
                self.setCurrentCell(next_row, col)
                event.accept()
                return
        super().keyPressEvent(event)

    def closeEditor(self, editor, hint):
        """
        Після підтвердження редагування Enter'ом стандартний QTableWidget
        переміщує курсор вниз (EditNextItem). Ми хочемо, щоб курсор лишився
        в тій самій комірці - тоді наступний Enter спрацює за нашою логікою
        переходу (keyPressEvent). Виняток - колонка "Тип чаю": там після
        підтвердження вибору зі списку одразу лишаємось у комірці, щоб не
        входити знову в редагування (інакше QComboBox зациклюється).
        """
        from PyQt6.QtWidgets import QAbstractItemDelegate
        if hint in (
            QAbstractItemDelegate.EndEditHint.EditNextItem,
            QAbstractItemDelegate.EndEditHint.EditPreviousItem,
        ):
            hint = QAbstractItemDelegate.EndEditHint.NoHint
        super().closeEditor(editor, hint)

    # ------------------------------------------------------------------
    # Побудова рядків
    # ------------------------------------------------------------------

    def add_empty_row(self):
        self._loading = True
        row = self.rowCount()
        self.insertRow(row)

        num_cell = QTableWidgetItem(str(row + 1))
        num_cell.setFlags(num_cell.flags() & ~Qt.ItemFlag.ItemIsEditable)
        self.setItem(row, COL_NUM, num_cell)

        self.setItem(row, COL_NAME, QTableWidgetItem(""))
        self.setItem(row, COL_QTY, QTableWidgetItem(""))
        self.setItem(row, COL_PRICE, QTableWidgetItem(""))

        sum_cell = QTableWidgetItem("0")
        sum_cell.setFlags(sum_cell.flags() & ~Qt.ItemFlag.ItemIsEditable)
        self.setItem(row, COL_SUM, sum_cell)

        self.setItem(row, COL_TYPE, QTableWidgetItem(TEA_TYPES_UI[0]))
        self.setItem(row, COL_LABELS, QTableWidgetItem("0"))
        self._loading = False

    def delete_selected_row(self):
        row = self.currentRow()
        if row < 0:
            return
        name = self.item(row, COL_NAME).text().strip()
        # Якщо рядок повністю порожній - видаляємо/очищаємо без зайвого діалогу
        if name:
            confirmed = ask_confirmation(
                self, "Видалити рядок",
                f"Ви впевнені, що хочете видалити рядок «{name}»?",
                danger=True,
            )
            if not confirmed:
                return
        if self.rowCount() <= 1:
            # Завжди залишаємо хоча б один (порожній) рядок для вводу
            self._loading = True
            for col in (COL_NAME, COL_QTY, COL_PRICE):
                self.item(row, col).setText("")
            self.item(row, COL_SUM).setText("0")
            self.item(row, COL_TYPE).setText(TEA_TYPES_UI[0])
            self.item(row, COL_LABELS).setText("0")
            self._loading = False
            self._renumber_rows()
            self._recalculate_totals()
            return
        self.removeRow(row)
        self._renumber_rows()
        self._recalculate_totals()

    def clear_all_rows(self):
        self._loading = True
        self.setRowCount(0)
        self._loading = False
        self.add_empty_row()
        self._recalculate_totals()

    def _renumber_rows(self):
        self._loading = True
        for row in range(self.rowCount()):
            self.item(row, COL_NUM).setText(str(row + 1))
        self._loading = False

    # ------------------------------------------------------------------
    # Автопідрахунок
    # ------------------------------------------------------------------

    def _on_item_changed(self, cell: QTableWidgetItem):
        if self._loading:
            return
        row = cell.row()
        col = cell.column()

        if col == COL_NAME:
            self._autofill_price_if_known(row)
            self._set_default_quantity_if_empty(row)

        if col in (COL_NAME, COL_QTY, COL_PRICE):
            self._recalculate_row_sum(row)

        # Якщо це останній рядок і в ньому з'явилась назва - додаємо новий порожній рядок
        if col == COL_NAME and row == self.rowCount() - 1 and cell.text().strip():
            self.add_empty_row()

        self._recalculate_totals()

    def _autofill_price_if_known(self, row: int):
        name = self.item(row, COL_NAME).text().strip()
        if not name:
            return
        active = self.db.get_active_price_list()
        if not active:
            return
        for price_item in self.db.list_items(active.id):
            if price_item.name.strip().lower() == name.lower():
                self._loading = True
                self.item(row, COL_PRICE).setText(f"{price_item.price_per_kg:g}")
                self._loading = False
                break

    def _set_default_quantity_if_empty(self, row: int):
        """Якщо назву щойно введено/підтверджено, а кількість ще порожня - ставимо 1."""
        name = self.item(row, COL_NAME).text().strip()
        qty_item = self.item(row, COL_QTY)
        if name and qty_item and not qty_item.text().strip():
            self._loading = True
            qty_item.setText("1")
            self._loading = False

    def _parse_float(self, text: str) -> float:
        text = (text or "").strip().replace(",", ".")
        if not text:
            return 0.0
        try:
            return float(text)
        except ValueError:
            return 0.0

    def _recalculate_row_sum(self, row: int):
        qty = self._parse_float(self.item(row, COL_QTY).text())
        price = self._parse_float(self.item(row, COL_PRICE).text())
        total = round(qty * price, 2)
        self._loading = True
        self.item(row, COL_SUM).setText(f"{total:g}".replace(".", ","))
        self._loading = False

    def _recalculate_totals(self):
        total_qty = 0.0
        total_sum = 0.0
        valid_rows = 0
        for row in range(self.rowCount()):
            name = self.item(row, COL_NAME).text().strip()
            qty = self._parse_float(self.item(row, COL_QTY).text())
            if name and qty > 0:
                valid_rows += 1
                total_qty += qty
                total_sum += self._parse_float(self.item(row, COL_PRICE).text()) * qty
        self.on_totals_changed(total_qty, round(total_sum, 2), valid_rows)

    # ------------------------------------------------------------------
    # Отримання валідних рядків для збереження
    # ------------------------------------------------------------------

    def get_valid_rows(self) -> list[InvoiceRow]:
        rows = []
        for row in range(self.rowCount()):
            name = self.item(row, COL_NAME).text().strip()
            qty = self._parse_float(self.item(row, COL_QTY).text())
            price = self._parse_float(self.item(row, COL_PRICE).text())
            if name and qty > 0:
                rows.append(InvoiceRow(name=name, quantity_kg=qty, price_per_kg=price))
        return rows

    def get_label_items(self) -> list[LabelItem]:
        """Позиції з ненульовою кількістю наклейок (порядок як у накладній)."""
        items = []
        for row in range(self.rowCount()):
            name = self.item(row, COL_NAME).text().strip()
            ui_type = self.item(row, COL_TYPE).text().strip()
            # Коротка назва з UI -> повна назва "ЧАЙ - ..." для Word-шаблону
            tea_type = UI_TO_FULL_TYPE.get(ui_type, ui_type)
            try:
                count = int(self.item(row, COL_LABELS).text().strip() or "0")
            except ValueError:
                count = 0
            if name and count > 0 and tea_type:
                items.append(LabelItem(tea_type=tea_type, name=name, count=count))
        return items


class InvoiceTab(QWidget):
    """Вкладка створення накладної."""

    def __init__(self, db: Database, parent=None):
        super().__init__(parent)
        self.db = db

        layout = QVBoxLayout(self)

        header = QHBoxLayout()
        title = QLabel("Створення накладної")
        title.setObjectName("pageTitle")
        header.addWidget(title)
        header.addStretch()
        date_label = QLabel(date.today().strftime("%d.%m.%Y"))
        header.addWidget(date_label)
        layout.addLayout(header)

        self.table = InvoiceTable(self.db, self._on_totals_changed)
        layout.addWidget(self.table)

        row_toolbar = QHBoxLayout()
        self.btn_add_row = QPushButton("+ Рядок")
        self.btn_delete_row = QPushButton("Видалити рядок")
        self.btn_clear_all = QPushButton("Очистити")
        self.btn_delete_row.setObjectName("secondaryButton")
        self.btn_clear_all.setObjectName("secondaryButton")
        row_toolbar.addWidget(self.btn_add_row)
        row_toolbar.addWidget(self.btn_delete_row)
        row_toolbar.addWidget(self.btn_clear_all)
        row_toolbar.addStretch()
        layout.addLayout(row_toolbar)

        bottom_bar = QHBoxLayout()
        self.total_label = QLabel("Всього: 0 кг, 0 грн")
        self.total_label.setObjectName("totalLabel")
        bottom_bar.addWidget(self.total_label)
        bottom_bar.addStretch()

        self.btn_save_open = QPushButton("Зберегти та відкрити")
        self.btn_save_open.setEnabled(False)
        bottom_bar.addWidget(self.btn_save_open)
        layout.addLayout(bottom_bar)

        self.btn_add_row.clicked.connect(self.table.add_empty_row)
        self.btn_delete_row.clicked.connect(self.table.delete_selected_row)
        self.btn_clear_all.clicked.connect(self._on_clear_all)
        self.btn_save_open.clicked.connect(self._on_save_and_open)

    def _on_totals_changed(self, total_qty: float, total_sum: float, valid_rows: int):
        self.total_label.setText(f"Всього: {total_qty:g} кг, {total_sum:g} грн".replace(".", ","))
        self.btn_save_open.setEnabled(valid_rows > 0)

    def _on_clear_all(self):
        confirmed = ask_confirmation(
            self, "Очистити накладну",
            "Ви впевнені? Усі введені позиції буде видалено.",
            danger=True,
        )
        if confirmed:
            self.table.clear_all_rows()

    def _on_save_and_open(self):
        rows = self.table.get_valid_rows()
        if not rows:
            show_warning(self, "Немає даних", "Додайте хоча б одну позицію з кількістю більше нуля.")
            return

        default_name = f"Накладна_{date.today().strftime('%d.%m.%Y')}.xlsx"
        path, _ = QFileDialog.getSaveFileName(
            self, "Зберегти накладну", default_name, "Excel (*.xlsx)"
        )
        if not path:
            return
        if not path.lower().endswith(".xlsx"):
            path += ".xlsx"

        try:
            generate_invoice_xlsx(rows, path, invoice_date=date.today())
        except Exception as exc:
            show_error(self, "Помилка збереження", f"Не вдалося зберегти файл:\n{exc}")
            return

        self._open_file(path)

        # Наклейки: якщо хоч в одній позиції вказано кількість > 0 -
        # генеруємо файл поруч із накладною і теж відкриваємо (у Word).
        label_items = self.table.get_label_items()
        if label_items:
            from pathlib import Path
            labels_path = str(Path(path).with_suffix("")) + "_наклейки.docx"
            try:
                generate_labels_docx(label_items, labels_path)
                self._open_file(labels_path)
            except LabelsError as exc:
                show_warning(self, "Наклейки", f"Не вдалося створити файл наклейок:\n{exc}")
            except Exception as exc:
                show_warning(self, "Наклейки", f"Помилка при створенні наклейок:\n{exc}")

        confirmed = ask_confirmation(
            self, "Нова накладна", "Розпочати нову накладну (очистити таблицю)?"
        )
        if confirmed:
            self.table.clear_all_rows()

    def _open_file(self, path: str):
        """Відкриває файл у програмі, асоційованій з його типом (Excel/Word)."""
        try:
            if sys.platform == "win32":
                # Qt повертає шляхи з прямими слешами (в т.ч. мережеві //nas/Share/...),
                # а os.startfile у Windows потребує зворотних слешів (\\nas\Share\...).
                os.startfile(os.path.normpath(path))
            else:
                # Для розробки/тестування поза Windows
                import subprocess
                subprocess.Popen(["xdg-open", path])
        except Exception as exc:
            show_warning(
                self, "Файл збережено",
                f"Файл збережено:\n{path}\n\nАле не вдалося відкрити його автоматично:\n{exc}",
            )
