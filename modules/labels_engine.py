"""
modules/labels_engine.py
Генерація файлу наклейок (.docx) на основі шаблону assets/labels_template_33.docx.

Шаблон - аркуш А4 з таблицею 11x3 (33 наклейки, ячейка 7.00 x 2.54 см).
Кожна наклейка: перший рядок - тип чаю (Times New Roman 12, для довгого
"ФРУКТОВА І ТРАВ'ЯНА СУМІШ" - 8), другий рядок - назва чаю ВЕЛИКИМИ
літерами (Times New Roman 18 Bold). Все по центру, все жирне.

Якщо наклейок більше 33 - додаються нові сторінки з такою ж таблицею.
"""

import copy
from dataclasses import dataclass
from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.shared import Pt

from config.settings import ASSETS_DIR

TEMPLATE_PATH = ASSETS_DIR / "labels_template_33.docx"

# Чотири типи чаю. Для найдовшого типу - менший шрифт, щоб вміщався в ячейку.
TEA_TYPES = [
    "ЧАЙ - ЧОРНИЙ",
    "ЧАЙ - ЗЕЛЕНИЙ",
    "ЧАЙ - СУМІШ",
    "ЧАЙ - ФРУКТОВА І ТРАВ'ЯНА СУМІШ",
]
SMALL_FONT_TYPE = "ЧАЙ - ФРУКТОВА І ТРАВ'ЯНА СУМІШ"

# Короткі назви для інтерфейсу (випадаючий список у накладній).
# У Word-шаблон завжди потрапляє повна назва ВЕЛИКИМИ з "ЧАЙ - ".
TEA_TYPES_UI = [
    "Чорний",
    "Зелений",
    "Суміш",
    "Фруктова і трав'яна суміш",
]
UI_TO_FULL_TYPE = dict(zip(TEA_TYPES_UI, TEA_TYPES))

FONT_NAME = "Times New Roman"
TYPE_FONT_SIZE = Pt(12)
TYPE_FONT_SIZE_SMALL = Pt(8)
NAME_FONT_SIZE = Pt(18)

CELLS_PER_PAGE = 33  # 11 x 3


@dataclass
class LabelItem:
    tea_type: str
    name: str
    count: int


class LabelsError(Exception):
    """Помилка генерації наклейок (немає шаблону тощо)."""


def _set_run_font(run, size, bold=True):
    font = run.font
    font.name = FONT_NAME
    font.size = size
    font.bold = bold
    # Явно прописуємо шрифт для кирилиці (rFonts w:cs / w:hAnsi)
    rPr = run._element.get_or_add_rPr()
    rFonts = rPr.find(
        "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}rFonts"
    )
    if rFonts is None:
        from docx.oxml.ns import qn
        rFonts = rPr.makeelement(qn("w:rFonts"), {})
        rPr.insert(0, rFonts)
    from docx.oxml.ns import qn
    rFonts.set(qn("w:ascii"), FONT_NAME)
    rFonts.set(qn("w:hAnsi"), FONT_NAME)
    rFonts.set(qn("w:cs"), FONT_NAME)


def _fill_cell(cell, tea_type: str, name: str):
    """Заповнює одну ячейку наклейки: тип чаю + назва ВЕЛИКИМИ літерами."""
    # Очищаємо ячейку до одного порожнього параграфа
    for p in cell.paragraphs[1:]:
        p._element.getparent().remove(p._element)
    p_type = cell.paragraphs[0]
    for run in list(p_type.runs):
        run._element.getparent().remove(run._element)

    p_type.alignment = WD_ALIGN_PARAGRAPH.CENTER
    type_size = TYPE_FONT_SIZE_SMALL if tea_type == SMALL_FONT_TYPE else TYPE_FONT_SIZE
    run_type = p_type.add_run(tea_type)
    _set_run_font(run_type, type_size)

    p_name = cell.add_paragraph()
    p_name.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run_name = p_name.add_run(name.upper())
    _set_run_font(run_name, NAME_FONT_SIZE)


def generate_labels_docx(items: list[LabelItem], output_path: str | Path) -> Path:
    """
    Генерує файл наклейок. items - список позицій (тип, назва, кількість
    наклейок); порядок збережено, кожна позиція повторюється count разів.
    """
    if not TEMPLATE_PATH.exists():
        raise LabelsError(f"Не знайдено шаблон наклейок: {TEMPLATE_PATH}")

    # Розгортаємо у плоский список наклейок
    labels = []
    for item in items:
        labels.extend([(item.tea_type, item.name)] * max(0, int(item.count)))

    if not labels:
        raise LabelsError("Немає жодної наклейки для друку (усі кількості нульові).")

    doc = Document(str(TEMPLATE_PATH))
    base_table = doc.tables[0]

    # Скільки сторінок потрібно
    total_pages = (len(labels) + CELLS_PER_PAGE - 1) // CELLS_PER_PAGE

    # Додаємо додаткові сторінки (копії таблиці) за потреби
    tables = [base_table]
    for _ in range(total_pages - 1):
        # Розрив сторінки
        br_p = doc.add_paragraph()
        br_run = br_p.add_run()
        br_run.add_break(WD_BREAK.PAGE)
        # Копія таблиці
        new_tbl_element = copy.deepcopy(base_table._tbl)
        br_p._element.addnext(new_tbl_element)

    # Перечитуємо список таблиць після вставки копій
    tables = doc.tables

    # Заповнюємо ячейки послідовно: зліва направо, зверху вниз
    label_idx = 0
    for table in tables:
        for row in table.rows:
            for cell in row.cells:
                if label_idx >= len(labels):
                    break
                tea_type, name = labels[label_idx]
                _fill_cell(cell, tea_type, name)
                label_idx += 1

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(output_path))
    return output_path


if __name__ == "__main__":
    # Швидка ручна перевірка
    test_items = [
        LabelItem("ЧАЙ - ЧОРНИЙ", "Орловський", 3),
        LabelItem("ЧАЙ - ФРУКТОВА І ТРАВ'ЯНА СУМІШ", "Альпійський луг", 2),
        LabelItem("ЧАЙ - СУМІШ", "1001 Ніч", 1),
    ]
    out = generate_labels_docx(test_items, "test_output/наклейки_тест.docx")
    print("Файл збережено:", out)
