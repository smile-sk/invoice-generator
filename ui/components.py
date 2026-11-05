"""
ui/components.py
Спільні стилізовані віджети та QSS-стиль застосунку.
Мінімалістична світла палітра з м'якими кутами та чіткими станами фокусу.
"""

# Базова QSS-палітра застосунку.
# Використовується один раз при старті (main.py -> app.setStyleSheet(...)).
STYLE_SHEET = """
QWidget {
    background-color: #F7F8FA;
    color: #1F2430;
    font-family: "Segoe UI", "Arial", sans-serif;
    font-size: 14px;
}

QMainWindow {
    background-color: #F7F8FA;
}

QTabWidget::pane {
    border: 1px solid #E1E4EA;
    border-top: none;
    border-radius: 10px;
    background-color: #FFFFFF;
}

QTabBar::tab {
    background: transparent;
    color: #6B7280;
    padding: 10px 18px;
    margin-right: 4px;
    border-radius: 8px;
    font-weight: 600;
}

/* Головна (верхня) панель вкладок: більший вертикальний відступ, щоб рядок
   природньо мав достатню висоту під логотип (240x65) у кутовому віджеті. */
QTabBar#mainTabBar::tab {
    padding: 24px 20px;
    margin-right: 6px;
}

QTabBar::tab:selected {
    background: #342C82;
    color: #FFFFFF;
}

QTabBar::tab:hover:!selected {
    background: #E6E3F5;
}

QPushButton {
    background-color: #342C82;
    color: #FFFFFF;
    border: none;
    border-radius: 8px;
    padding: 8px 16px;
    font-weight: 600;
}

QPushButton:hover {
    background-color: #241D63;
}

QPushButton:pressed {
    background-color: #1B1650;
}

QPushButton:disabled {
    background-color: #C7C9D9;
    color: #F1F1F5;
}

QPushButton#secondaryButton {
    background-color: #FFFFFF;
    color: #342C82;
    border: 1px solid #342C82;
}

QPushButton#secondaryButton:hover {
    background-color: #E6E3F5;
}

QLineEdit, QComboBox, QDoubleSpinBox, QSpinBox {
    background-color: #FFFFFF;
    border: 1px solid #D8DAE5;
    border-radius: 6px;
    padding: 6px 8px;
    selection-background-color: #342C82;
}

QLineEdit:focus, QComboBox:focus, QDoubleSpinBox:focus, QSpinBox:focus {
    border: 1px solid #342C82;
}

QTableWidget {
    background-color: #FFFFFF;
    border: 1px solid #E1E4EA;
    border-radius: 8px;
    gridline-color: #EEF0F4;
    selection-background-color: #E6E3F5;
    selection-color: #1F2430;
}

QHeaderView::section {
    background-color: #F1F2F6;
    color: #4B5165;
    padding: 6px;
    border: none;
    font-weight: 600;
}

QScrollBar:vertical {
    background: transparent;
    width: 10px;
    margin: 2px;
}

QScrollBar::handle:vertical {
    background: #C7C9D9;
    border-radius: 5px;
    min-height: 24px;
}

QScrollBar::handle:vertical:hover {
    background: #9CA0B8;
}

QLabel#pageTitle {
    font-size: 20px;
    font-weight: 700;
    color: #1F2430;
}

QLabel#totalLabel {
    font-size: 16px;
    font-weight: 700;
    color: #342C82;
}
"""


# ----------------------------------------------------------------------
# Локалізовані діалоги (українською)
# ----------------------------------------------------------------------
# PyQt6 сам не перекладає стандартні кнопки (OK/Cancel/Yes/No) на українську,
# тож для узгодженого UI використовуємо ці хелпери замість статичних методів
# QMessageBox.question(...) / QInputDialog.getText(...) напряму.

from PyQt6.QtWidgets import QMessageBox, QInputDialog, QDialogButtonBox, QDialog


def _localize_button_box(dialog):
    box = dialog.findChild(QDialogButtonBox)
    if box is None:
        return
    ok_btn = box.button(QDialogButtonBox.StandardButton.Ok)
    if ok_btn:
        ok_btn.setText("ОК")
    cancel_btn = box.button(QDialogButtonBox.StandardButton.Cancel)
    if cancel_btn:
        cancel_btn.setText("Скасувати")


def ask_confirmation(parent, title: str, text: str, danger: bool = False) -> bool:
    """Діалог 'Так/Ні'. danger=True підкреслює, що дія незворотна (напр. видалення)."""
    box = QMessageBox(parent)
    box.setWindowTitle(title)
    box.setText(text)
    box.setIcon(QMessageBox.Icon.Warning if danger else QMessageBox.Icon.Question)
    yes_btn = box.addButton("Так, видалити" if danger else "Так", QMessageBox.ButtonRole.YesRole)
    no_btn = box.addButton("Скасувати", QMessageBox.ButtonRole.NoRole)
    box.setDefaultButton(no_btn)
    box.exec()
    return box.clickedButton() == yes_btn


def show_info(parent, title: str, text: str):
    box = QMessageBox(parent)
    box.setWindowTitle(title)
    box.setText(text)
    box.setIcon(QMessageBox.Icon.Information)
    box.addButton("ОК", QMessageBox.ButtonRole.AcceptRole)
    box.exec()


def show_warning(parent, title: str, text: str):
    box = QMessageBox(parent)
    box.setWindowTitle(title)
    box.setText(text)
    box.setIcon(QMessageBox.Icon.Warning)
    box.addButton("ОК", QMessageBox.ButtonRole.AcceptRole)
    box.exec()


def show_error(parent, title: str, text: str):
    box = QMessageBox(parent)
    box.setWindowTitle(title)
    box.setText(text)
    box.setIcon(QMessageBox.Icon.Critical)
    box.addButton("ОК", QMessageBox.ButtonRole.AcceptRole)
    box.exec()


def get_text_uk(parent, title: str, label: str, text: str = "") -> tuple[str, bool]:
    dialog = QInputDialog(parent)
    dialog.setWindowTitle(title)
    dialog.setLabelText(label)
    dialog.setTextValue(text)
    _localize_button_box(dialog)
    ok = dialog.exec() == QDialog.DialogCode.Accepted
    return dialog.textValue(), ok


def get_double_uk(
    parent, title: str, label: str, value: float = 0, min_value: float = -1e9,
    max_value: float = 1e9, decimals: int = 2,
) -> tuple[float, bool]:
    dialog = QInputDialog(parent)
    dialog.setWindowTitle(title)
    dialog.setLabelText(label)
    dialog.setInputMode(QInputDialog.InputMode.DoubleInput)
    dialog.setDoubleRange(min_value, max_value)
    dialog.setDoubleDecimals(decimals)
    dialog.setDoubleValue(value)
    _localize_button_box(dialog)
    ok = dialog.exec() == QDialog.DialogCode.Accepted
    return dialog.doubleValue(), ok
