from __future__ import annotations

from pathlib import Path

import pandas as pd

SUPPORTED_EXTENSIONS = {".xlsx", ".xls"}
HEADER_KEYWORDS = {"시군구", "법정동", "거래금액", "전용면적", "계약년월"}


def find_input_files(input_dir: str | Path) -> list[Path]:
    path = Path(input_dir)
    if not path.exists():
        path.mkdir(parents=True, exist_ok=True)
    return sorted([p for p in path.iterdir() if p.suffix.lower() in SUPPORTED_EXTENSIONS and not p.name.startswith("~$")])


def detect_header_row(excel_path: Path) -> int:
    preview = pd.read_excel(excel_path, header=None, nrows=30, engine="openpyxl")
    best_index = 0
    best_score = -1
    for idx, row in preview.iterrows():
        text = " ".join(str(v) for v in row.dropna().tolist())
        score = sum(1 for keyword in HEADER_KEYWORDS if keyword in text)
        if score > best_score:
            best_score = score
            best_index = int(idx)
    return best_index


def read_excel_file(excel_path: str | Path) -> pd.DataFrame:
    path = Path(excel_path)
    header_row = detect_header_row(path)
    df = pd.read_excel(path, header=header_row, engine="openpyxl")
    df = df.dropna(how="all")
    df["원본파일"] = path.name
    return df


def load_input_folder(input_dir: str | Path = "input") -> pd.DataFrame:
    files = find_input_files(input_dir)
    if not files:
        raise FileNotFoundError(f"입력 폴더에 엑셀 파일이 없습니다: {Path(input_dir).resolve()}")
    frames = [read_excel_file(file) for file in files]
    return pd.concat(frames, ignore_index=True)
