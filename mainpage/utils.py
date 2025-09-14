# mainpage/utils.py
from pathlib import Path
import pandas as pd


EXCEL_MAP = {
    "day1": "День1.xlsx",
    "day2": "День2.xlsx",
    "day3": "День3.xlsx",
    "day4": "Тестовый.xlsx",
    "СЛР": "GruppySLR.xlsx",
}

def load_groups_from_excel(day_key: str) -> list[str]:
    """
    Возвращает список URL-ов групп из файла excel_file/День*.xlsx для выбранного дня.
    Ищет колонку по названию с 'ссыл' (регистр не важен), иначе берёт первую.
    """
    base_dir = Path(__file__).resolve().parent.parent  # .../vkparser
    excel_dir = base_dir / "excel_file"
    fname = EXCEL_MAP.get(day_key)
    if not fname:
        raise ValueError(f"Неизвестный день: {day_key}")

    path = excel_dir / fname
    if not path.exists():
        raise FileNotFoundError(f"Файл не найден: {path}")

    df = pd.read_excel(path)
    df.columns = df.columns.str.strip()

    # пытаемся найти колонку со словом 'ссыл'
    link_col = next((c for c in df.columns if "ссыл" in c.lower()), None)
    if not link_col:
        link_col = df.columns[0]

    groups = df[link_col].dropna().astype(str).tolist()
    return groups

