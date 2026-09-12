from pathlib import Path

import pandas as pd


DAY_FILES = {
    0: "Тестовый.xlsx",
    10: "GruppySLR.xlsx",
    50: "GruppySLR2.xlsx",
}


def excel_path_for_day(day: int, groups_dir: str | Path = "group_target") -> Path:
    """
    day=0  → Тестовый.xlsx
    day=1..9 → День_{day}.xlsx
    day=10..49 → GruppySLR.xlsx
    day>=50 → GruppySLR2.xlsx
    """
    if isinstance(day, str):
        key = day.strip().lower()
        if key in {"0", "test", "тест", "тестовый"}:
            day = 0
        else:
            day = int(day)

    if day < 0:
        raise ValueError(f"Некорректный день: {day}")

    if day == 0:
        name = DAY_FILES[0]
    elif 1 <= day <= 9:
        name = f"День_{day}.xlsx"
    elif day < 50:
        name = DAY_FILES[10]
    else:
        name = DAY_FILES[50]

    path = Path(groups_dir) / name
    if not path.exists():
        raise FileNotFoundError(f"Нет файла списка групп: {path}")
    return path


def _link_column(columns) -> str:
    for name in columns:
        if "ссыл" in str(name).strip().lower():
            return name
    raise KeyError("В Excel нет колонки со ссылками")


def load_group_urls(day: int, groups_dir: str | Path = "group_target") -> pd.DataFrame:
    path = excel_path_for_day(day, groups_dir)
    try:
        frame = pd.read_excel(path, sheet_name="Предложка")
    except ValueError:
        frame = pd.read_excel(path)

    frame.columns = [str(col).strip() for col in frame.columns]
    if "Commit" in frame.columns:
        frame = frame[frame["Commit"].isna()].copy()

    link_col = _link_column(frame.columns)
    frame = frame.rename(columns={link_col: "url"})
    frame["url"] = frame["url"].astype(str).str.strip()
    frame = frame[frame["url"].str.startswith("http")]
    if frame.empty:
        raise ValueError(f"В файле {path} нет ссылок для рассылки")
    return frame.reset_index(drop=True)