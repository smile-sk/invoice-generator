"""
modules/database.py
Локальне зберігання прайс-листів у SQLite.

Схема:
    price_lists(id, name, is_active)
    price_items(id, price_list_id, position, name, price_per_kg)

Тільки один прайс-лист може бути позначений як "Основний" (is_active = 1).
"""

import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Optional

from config.settings import DATABASE_PATH


@dataclass
class PriceItem:
    id: Optional[int]
    price_list_id: int
    position: int
    name: str
    price_per_kg: float


@dataclass
class PriceList:
    id: Optional[int]
    name: str
    is_active: bool


class Database:
    def __init__(self, db_path=None):
        self.db_path = str(db_path or DATABASE_PATH)
        self._init_schema()

    @contextmanager
    def _connect(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init_schema(self):
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS price_lists (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    is_active INTEGER NOT NULL DEFAULT 0
                );

                CREATE TABLE IF NOT EXISTS price_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    price_list_id INTEGER NOT NULL,
                    position INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    price_per_kg REAL NOT NULL,
                    FOREIGN KEY (price_list_id) REFERENCES price_lists(id)
                        ON DELETE CASCADE
                );
                """
            )

    # ------------------------------------------------------------------
    # Прайс-листи
    # ------------------------------------------------------------------

    def list_price_lists(self) -> list[PriceList]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT id, name, is_active FROM price_lists ORDER BY id"
            ).fetchall()
        return [PriceList(r["id"], r["name"], bool(r["is_active"])) for r in rows]

    def create_price_list(self, name: str, make_active: bool = False) -> int:
        with self._connect() as conn:
            cursor = conn.execute(
                "INSERT INTO price_lists (name, is_active) VALUES (?, 0)", (name,)
            )
            new_id = cursor.lastrowid
        if make_active:
            self.set_active_price_list(new_id)
        return new_id

    def rename_price_list(self, price_list_id: int, new_name: str):
        with self._connect() as conn:
            conn.execute(
                "UPDATE price_lists SET name = ? WHERE id = ?",
                (new_name, price_list_id),
            )

    def delete_price_list(self, price_list_id: int):
        with self._connect() as conn:
            conn.execute("DELETE FROM price_lists WHERE id = ?", (price_list_id,))

    def set_active_price_list(self, price_list_id: int):
        """Позначає прайс-лист як 'Основний', знімаючи прапорець з усіх інших."""
        with self._connect() as conn:
            conn.execute("UPDATE price_lists SET is_active = 0")
            conn.execute(
                "UPDATE price_lists SET is_active = 1 WHERE id = ?", (price_list_id,)
            )

    def get_active_price_list(self) -> Optional[PriceList]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT id, name, is_active FROM price_lists WHERE is_active = 1"
            ).fetchone()
        if row is None:
            return None
        return PriceList(row["id"], row["name"], bool(row["is_active"]))

    def clone_price_list(self, price_list_id: int, new_name: str) -> int:
        """Клонує прайс-лист разом з усіма позиціями. Повертає id нового списку."""
        items = self.list_items(price_list_id)
        new_id = self.create_price_list(new_name, make_active=False)
        with self._connect() as conn:
            conn.executemany(
                """INSERT INTO price_items (price_list_id, position, name, price_per_kg)
                   VALUES (?, ?, ?, ?)""",
                [(new_id, it.position, it.name, it.price_per_kg) for it in items],
            )
        return new_id

    # ------------------------------------------------------------------
    # Позиції прайс-листа
    # ------------------------------------------------------------------

    def list_items(self, price_list_id: int) -> list[PriceItem]:
        with self._connect() as conn:
            rows = conn.execute(
                """SELECT id, price_list_id, position, name, price_per_kg
                   FROM price_items WHERE price_list_id = ? ORDER BY position""",
                (price_list_id,),
            ).fetchall()
        return [
            PriceItem(r["id"], r["price_list_id"], r["position"], r["name"], r["price_per_kg"])
            for r in rows
        ]

    def add_item(self, price_list_id: int, name: str, price_per_kg: float) -> int:
        with self._connect() as conn:
            max_pos = conn.execute(
                "SELECT COALESCE(MAX(position), 0) AS m FROM price_items WHERE price_list_id = ?",
                (price_list_id,),
            ).fetchone()["m"]
            cursor = conn.execute(
                """INSERT INTO price_items (price_list_id, position, name, price_per_kg)
                   VALUES (?, ?, ?, ?)""",
                (price_list_id, max_pos + 1, name, price_per_kg),
            )
            return cursor.lastrowid

    def update_item(self, item_id: int, name: str = None, price_per_kg: float = None):
        fields, values = [], []
        if name is not None:
            fields.append("name = ?")
            values.append(name)
        if price_per_kg is not None:
            fields.append("price_per_kg = ?")
            values.append(price_per_kg)
        if not fields:
            return
        values.append(item_id)
        with self._connect() as conn:
            conn.execute(f"UPDATE price_items SET {', '.join(fields)} WHERE id = ?", values)

    def delete_item(self, item_id: int):
        with self._connect() as conn:
            conn.execute("DELETE FROM price_items WHERE id = ?", (item_id,))

    def adjust_prices_by_percent(self, price_list_id: int, percent: float):
        """
        Змінює всі ціни в прайс-листі на вказаний відсоток.
        percent=10 -> +10%, percent=-5 -> -5%.
        """
        factor = 1 + (percent / 100)
        with self._connect() as conn:
            conn.execute(
                "UPDATE price_items SET price_per_kg = ROUND(price_per_kg * ?, 2) "
                "WHERE price_list_id = ?",
                (factor, price_list_id),
            )

    def import_items_from_rows(self, price_list_id: int, rows: list[tuple[str, float]]):
        """
        Масовий імпорт позицій (наприклад, з CSV/Excel).
        rows: список (назва, ціна_за_кг).
        Існуючі позиції прайс-листа НЕ видаляються - додаються нові.
        """
        with self._connect() as conn:
            max_pos = conn.execute(
                "SELECT COALESCE(MAX(position), 0) AS m FROM price_items WHERE price_list_id = ?",
                (price_list_id,),
            ).fetchone()["m"]
            data = [
                (price_list_id, max_pos + i + 1, name, price)
                for i, (name, price) in enumerate(rows)
            ]
            conn.executemany(
                """INSERT INTO price_items (price_list_id, position, name, price_per_kg)
                   VALUES (?, ?, ?, ?)""",
                data,
            )


# ----------------------------------------------------------------------
# Сід-дані: приклад наповнення на основі реальної накладної (чаї)
# ----------------------------------------------------------------------

SAMPLE_TEA_PRICE_LIST = [
    ("Ройбуш ягідний", 615),
    ("Ройбуш з Годжі", 615),
    ("Ройбуш Оранж", 565),
    ("Пу-Ер з вишнею", 510),
    ("Ассам 17", 480),
    ("Ассам терпкий", 550),
    ("Оолонг з Годжі", 495),
    ("Кардіо", 380),
    ("Персиковий Оолонг", 495),
    ("В'ялена вишня", 410),
    ("Діабетичний збір", 450),
    ("Антистрес", 430),
    ("Альпійський луг", 380),
    ("Шлунковий збір", 450),
    ("Для підшлункової", 450),
]


def seed_sample_data(db: Database):
    """Створює демонстраційний прайс-лист 'Чай (приклад)' і робить його активним."""
    existing = {pl.name for pl in db.list_price_lists()}
    if "Чай (приклад)" in existing:
        return
    list_id = db.create_price_list("Чай (приклад)", make_active=True)
    db.import_items_from_rows(list_id, SAMPLE_TEA_PRICE_LIST)


if __name__ == "__main__":
    # Швидка ручна перевірка модуля.
    db = Database()
    seed_sample_data(db)
    active = db.get_active_price_list()
    print("Активний прайс-лист:", active)
    for item in db.list_items(active.id):
        print(f"  {item.position}. {item.name} - {item.price_per_kg} грн/кг")
