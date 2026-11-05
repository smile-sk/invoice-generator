"""
modules/excel_engine.py
Генерація стилізованої накладної (.xlsx) та імпорт прайс-листів з Excel/CSV.
"""

import csv
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font, Alignment, Border, Side, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet


@dataclass
class InvoiceRow:
    name: str
    quantity_kg: float
    price_per_kg: float

    @property
    def sum(self) -> float:
        return round(self.quantity_kg * self.price_per_kg, 2)


# ----------------------------------------------------------------------
# Стилі
# ----------------------------------------------------------------------

THIN = Side(style="thin", color="000000")
BORDER_ALL = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)

HEADER_FILL = PatternFill("solid", fgColor="F1F2F6")
HEADER_FONT = Font(bold=True, size=11)
TITLE_FONT = Font(bold=True, size=14)
DATE_FONT = Font(size=11)
TOTAL_FONT = Font(bold=True, size=11)

CENTER = Alignment(horizontal="center", vertical="center")
LEFT = Alignment(horizontal="left", vertical="center")
RIGHT = Alignment(horizontal="right", vertical="center")

COLUMNS = ["№", "Найменування", "Кількість, кг", "Ціна за кг", "Сума"]
COL_WIDTHS = [6, 34, 14, 12, 12]


def _write_invoice_sheet(ws: Worksheet, rows: list[InvoiceRow], invoice_date: date, title: str):
    ws.sheet_view.showGridLines = False

    # Дата (без заголовку "Накладна" - за прикладом реальної накладної)
    ws["E1"] = invoice_date.strftime("%d.%m.%Y")
    ws["E1"].font = DATE_FONT
    ws["E1"].alignment = RIGHT

    header_row = 3
    for col_idx, header in enumerate(COLUMNS, start=1):
        cell = ws.cell(row=header_row, column=col_idx, value=header)
        cell.font = HEADER_FONT
        cell.fill = HEADER_FILL
        cell.alignment = CENTER
        cell.border = BORDER_ALL

    total_qty = 0.0
    total_sum = 0.0
    row_idx = header_row + 1
    for i, row in enumerate(rows, start=1):
        ws.cell(row=row_idx, column=1, value=i).alignment = CENTER
        ws.cell(row=row_idx, column=2, value=row.name).alignment = LEFT
        ws.cell(row=row_idx, column=3, value=row.quantity_kg).alignment = CENTER
        ws.cell(row=row_idx, column=4, value=row.price_per_kg).alignment = CENTER
        ws.cell(row=row_idx, column=5, value=row.sum).alignment = CENTER
        for col_idx in range(1, 6):
            ws.cell(row=row_idx, column=col_idx).border = BORDER_ALL
        total_qty += row.quantity_kg
        total_sum += row.sum
        row_idx += 1

    # Підсумковий рядок
    ws.merge_cells(start_row=row_idx, start_column=1, end_row=row_idx, end_column=2)
    total_label_cell = ws.cell(row=row_idx, column=1, value="ЗАГАЛОМ ЗА НАКЛАДНОЮ")
    total_label_cell.font = TOTAL_FONT
    total_label_cell.alignment = LEFT

    qty_cell = ws.cell(row=row_idx, column=3, value=round(total_qty, 2))
    qty_cell.font = TOTAL_FONT
    qty_cell.alignment = CENTER

    sum_cell = ws.cell(row=row_idx, column=5, value=round(total_sum, 2))
    sum_cell.font = TOTAL_FONT
    sum_cell.alignment = CENTER

    for col_idx in range(1, 6):
        ws.cell(row=row_idx, column=col_idx).border = BORDER_ALL

    for i, width in enumerate(COL_WIDTHS, start=1):
        ws.column_dimensions[get_column_letter(i)].width = width

    # Налаштування друку під А4
    ws.page_setup.orientation = "portrait"
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 0
    ws.sheet_properties.pageSetUpPr.fitToPage = True


def generate_invoice_xlsx(
    rows: list[InvoiceRow],
    output_path: str | Path,
    invoice_date: date | None = None,
    title: str = "Накладна",
) -> Path:
    """Генерує файл накладної .xlsx (одна накладна на аркуш)."""
    invoice_date = invoice_date or date.today()
    output_path = Path(output_path)

    wb = Workbook()
    ws = wb.active
    ws.title = "Накладна"

    _write_invoice_sheet(ws, rows, invoice_date, title)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(output_path)
    return output_path


# ----------------------------------------------------------------------
# Імпорт прайс-листів з Excel/CSV
# ----------------------------------------------------------------------

def import_price_rows_from_excel(path: str | Path, sheet_name: str | None = None) -> list[tuple[str, float]]:
    """
    Читає прайс-лист з .xlsx. Очікує колонки: Найменування, Ціна за кг
    (порядок і назви заголовків можуть відрізнятись регістром/пробілами).
    Повертає список (назва, ціна).
    """
    wb = load_workbook(path, data_only=True)
    ws = wb[sheet_name] if sheet_name else wb.active

    rows_iter = ws.iter_rows(values_only=True)
    header = next(rows_iter, None)
    if header is None:
        return []

    name_col, price_col = _detect_columns(header)

    result = []
    for row in rows_iter:
        if row is None or name_col >= len(row) or row[name_col] is None:
            continue
        name = str(row[name_col]).strip()
        if not name:
            continue
        price_raw = row[price_col] if price_col < len(row) else None
        try:
            price = float(str(price_raw).replace(",", "."))
        except (TypeError, ValueError):
            continue
        result.append((name, price))
    return result


def import_price_rows_from_csv(path: str | Path, delimiter: str = ",") -> list[tuple[str, float]]:
    result = []
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.reader(f, delimiter=delimiter)
        header = next(reader, None)
        if header is None:
            return []
        name_col, price_col = _detect_columns(header)
        for row in reader:
            if not row or name_col >= len(row) or not row[name_col].strip():
                continue
            name = row[name_col].strip()
            try:
                price = float(row[price_col].replace(",", "."))
            except (IndexError, ValueError):
                continue
            result.append((name, price))
    return result


def _detect_columns(header: tuple) -> tuple[int, int]:
    """
    Намагається знайти колонки 'Найменування' та 'Ціна' за назвою заголовка.
    Якщо не вдалось - використовує перші дві колонки як (назва, ціна).
    """
    normalized = [str(h).strip().lower() if h else "" for h in header]

    name_col = next(
        (i for i, h in enumerate(normalized) if "найменування" in h or "назва" in h or "name" in h),
        0,
    )
    price_col = next(
        (i for i, h in enumerate(normalized) if "ціна" in h or "цена" in h or "price" in h),
        1 if len(normalized) > 1 else 0,
    )
    return name_col, price_col


if __name__ == "__main__":
    # Швидка ручна перевірка: генеруємо тестову накладну.
    sample_rows = [
        InvoiceRow("Ройбуш ягідний", 0.5, 615),
        InvoiceRow("Ассам 17", 1, 480),
        InvoiceRow("Оолонг з Годжі", 1, 495),
    ]
    out = generate_invoice_xlsx(sample_rows, "test_output/накладна_приклад.xlsx")
    print("Файл збережено:", out)
