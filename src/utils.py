from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

PYEONG_DIVISOR = 3.305785
AREA_BUCKETS = [
    (float("-inf"), 10, "10평 이하"),
    (10, 12, "10~12평"),
    (12, 14, "12~14평"),
    (14, 16, "14~16평"),
    (16, 18, "16~18평"),
    (18, 20, "18~20평"),
    (20, 24, "20~24평"),
    (24, 30, "24~30평"),
    (30, float("inf"), "30평 이상"),
]


def ensure_dir(path: str | Path) -> Path:
    target = Path(path)
    target.mkdir(parents=True, exist_ok=True)
    return target


def to_number(value: Any) -> float | None:
    if pd.isna(value):
        return None
    text = str(value).strip().replace(",", "")
    if text in {"", "-", "nan", "None"}:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def square_meter_to_pyeong(value: Any) -> float | None:
    number = to_number(value)
    if number is None:
        return None
    return number / PYEONG_DIVISOR


def area_bucket(pyeong: Any) -> str:
    number = to_number(pyeong)
    if number is None:
        return "미상"
    for lower, upper, label in AREA_BUCKETS:
        if lower < number <= upper:
            return label
    return "미상"


def safe_filename(name: str) -> str:
    return "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in name).strip("_")
