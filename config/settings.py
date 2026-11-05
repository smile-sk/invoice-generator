"""
config/settings.py
Централізовані налаштування застосунку: базові шляхи (БД, іконка, лого)
та невеликий JSON-сховище для налаштувань користувача на майбутнє.
"""

import os
import sys
import json
from pathlib import Path


def get_app_data_dir() -> Path:
    """
    Повертає директорію для збереження даних застосунку
    (%APPDATA%/InvoiceGenerator на Windows, або домашню теку на інших ОС).
    """
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home()))
    else:
        base = Path.home() / ".local" / "share"
    app_dir = base / "InvoiceGenerator"
    app_dir.mkdir(parents=True, exist_ok=True)
    return app_dir


# --- Базові шляхи ---
# У зібраному PyInstaller .exe (режим --onefile) файли розпаковуються у
# тимчасову теку sys._MEIPASS; у звичайному запуску (python main.py) -
# використовуємо розташування самого проєкту.
if getattr(sys, "frozen", False):
    BASE_DIR = Path(sys._MEIPASS)
else:
    BASE_DIR = Path(__file__).resolve().parent.parent

ASSETS_DIR = BASE_DIR / "assets"
APP_DATA_DIR = get_app_data_dir()

DATABASE_PATH = APP_DATA_DIR / "prices.db"
SETTINGS_FILE = APP_DATA_DIR / "app_settings.json"

APP_ICON_PATH = ASSETS_DIR / "app_icon.ico"
LOGO_PATH = ASSETS_DIR / "indigo_logo-240x65.png"

# --- Значення за замовчуванням ---
DEFAULT_SETTINGS = {}


class AppSettings:
    """Обгортка над JSON-файлом налаштувань із зручним доступом."""

    def __init__(self):
        self._data = dict(DEFAULT_SETTINGS)
        self.load()

    def load(self):
        if SETTINGS_FILE.exists():
            try:
                with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                self._data.update(saved)
            except (json.JSONDecodeError, OSError):
                # Файл пошкоджено - використовуємо значення за замовчуванням
                pass

    def save(self):
        try:
            with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
                json.dump(self._data, f, ensure_ascii=False, indent=2)
        except OSError as exc:
            print(f"Не вдалося зберегти налаштування: {exc}")

    def get(self, key, default=None):
        return self._data.get(key, default)

    def set(self, key, value):
        self._data[key] = value
        self.save()


settings = AppSettings()
