from __future__ import annotations

from typing import Iterable

import pandas as pd

from .utils import area_bucket, square_meter_to_pyeong, to_number

DEFAULT_TARGET_TYPES = ("다세대", "연립")
KNOWN_TYPE_KEYWORDS = (
    "아파트",
    "다세대",
    "연립",
    "다가구",
    "단독",
    "단독주택",
    "오피스텔",
    "상가",
    "상업",
    "업무",
    "토지",
    "분양권",
    "입주권",
    "공장",
    "창고",
)

COLUMN_ALIASES = {
    "주택유형": ["주택유형", "유형", "건물용도", "부동산유형", "구분", "용도", "건물주용도"],
    "시군구": ["시군구", "시군구명", "지역", "소재지", "시도", "시도명"],
    "법정동": ["법정동", "법정동명", "동", "읍면동"],
    "도로명": ["도로명", "도로명주소", "도로명 주소", "도로명주소명", "도로명건물본번호코드", "도로명건물부번호코드"],
    "지번": ["지번", "본번", "부번", "번지"],
    "단지명": ["단지명", "건물명", "연립다세대명", "아파트명", "명칭"],
    "전용면적(㎡)": ["전용면적(㎡)", "전용면적", "면적", "계약면적", "연면적(㎡)", "대지면적(㎡)", "건물면적(㎡)", "토지면적(㎡)", "면적(㎡)"],
    "거래금액(만원)": ["거래금액(만원)", "거래금액", "거래가액", "매매가", "금액"],
    "계약년월": ["계약년월", "계약 년월", "년월"],
    "계약일": ["계약일", "계약 일", "일"],
    "건축년도": ["건축년도", "건축연도", "건축년", "준공년도"],
    "층": ["층", "해당층"],
}


def normalize_column_name(name: object) -> str:
    text = str(name).strip()
    return text.replace(" ", "").replace("\n", "")


def standardize_columns(df: pd.DataFrame) -> pd.DataFrame:
    normalized = {col: normalize_column_name(col) for col in df.columns}
    reverse_alias: dict[str, str] = {}
    for standard, aliases in COLUMN_ALIASES.items():
        for alias in aliases:
            reverse_alias[normalize_column_name(alias)] = standard

    rename_map = {}
    for original, compact in normalized.items():
        if compact in reverse_alias:
            rename_map[original] = reverse_alias[compact]

    result = df.rename(columns=rename_map).copy()
    result = result.loc[:, ~result.columns.duplicated()]
    return result


def infer_housing_type(row: pd.Series) -> str:
    explicit = str(row.get("주택유형", "")).strip()
    if explicit:
        return explicit

    joined = " ".join(str(v) for v in row.dropna().tolist())
    for keyword in KNOWN_TYPE_KEYWORDS:
        if keyword in joined:
            return keyword
    return "미상"


def contains_any_keyword(value: object, keywords: Iterable[str]) -> bool:
    text = str(value)
    return any(keyword in text for keyword in keywords)


def filter_by_region(
    df: pd.DataFrame,
    sido: str | None = None,
    sigungu: str | None = None,
    dong: str | None = None,
) -> pd.DataFrame:
    result = df.copy()
    if sido:
        result = result[result["시군구"].astype(str).str.contains(sido, na=False)]
    if sigungu:
        result = result[result["시군구"].astype(str).str.contains(sigungu, na=False)]
    if dong:
        result = result[result["법정동"].astype(str).str.contains(dong, na=False)]
    return result


def split_sigungu_and_dong(address: object) -> tuple[str, str]:
    """Split MOLIT full address like '인천광역시 남동구 장수동'."""
    parts = str(address).strip().split()
    if len(parts) >= 3:
        return " ".join(parts[:-1]), parts[-1]
    if len(parts) == 2:
        return parts[0], parts[1]
    text = str(address).strip()
    return text, text


def ensure_location_columns(df: pd.DataFrame) -> pd.DataFrame:
    result = df.copy()
    if "시군구" in result.columns and "법정동" not in result.columns:
        split = result["시군구"].apply(split_sigungu_and_dong)
        result["법정동"] = split.apply(lambda value: value[1])
        result["시군구"] = split.apply(lambda value: value[0])
    return result


def require_columns(df: pd.DataFrame, required: Iterable[str]) -> None:
    missing = [col for col in required if col not in df.columns]
    if missing:
        raise ValueError(f"필수 컬럼을 찾을 수 없습니다: {', '.join(missing)}")


def make_trade_date(row: pd.Series) -> pd.Timestamp | pd.NaT:
    ym = row.get("계약년월")
    day = row.get("계약일")
    ym_num = to_number(ym)
    day_num = to_number(day)
    if ym_num is None or day_num is None:
        return pd.NaT
    ym_text = str(int(ym_num))
    if len(ym_text) != 6:
        return pd.NaT
    return pd.to_datetime(f"{ym_text}{int(day_num):02d}", format="%Y%m%d", errors="coerce")


def clean_transactions(
    df: pd.DataFrame,
    include_keywords: Iterable[str] | None = None,
    sido: str | None = None,
    sigungu: str | None = None,
    dong: str | None = None,
) -> pd.DataFrame:
    if df.empty:
        return df.copy()

    cleaned = standardize_columns(df)
    cleaned = ensure_location_columns(cleaned)
    required = ["시군구", "법정동", "전용면적(㎡)", "거래금액(만원)"]
    require_columns(cleaned, required)

    cleaned["주택유형"] = cleaned.apply(infer_housing_type, axis=1)
    cleaned["주택유형"] = cleaned["주택유형"].astype(str).str.strip()

    keywords = tuple(include_keywords or DEFAULT_TARGET_TYPES)
    if keywords:
        mask = cleaned["주택유형"].apply(lambda value: contains_any_keyword(value, keywords))
        cleaned = cleaned[mask].copy()

    cleaned["시군구"] = cleaned["시군구"].astype(str).str.strip()
    cleaned["법정동"] = cleaned["법정동"].astype(str).str.strip()
    cleaned = filter_by_region(cleaned, sido=sido, sigungu=sigungu, dong=dong)

    cleaned["전용면적_㎡"] = cleaned["전용면적(㎡)"].apply(to_number)
    cleaned["전용면적_평"] = cleaned["전용면적_㎡"].apply(square_meter_to_pyeong).round(2)
    cleaned["면적구간"] = cleaned["전용면적_평"].apply(area_bucket)
    cleaned["거래금액_만원"] = cleaned["거래금액(만원)"].apply(to_number).round(0).astype("Int64")
    cleaned["평당가_만원"] = (cleaned["거래금액_만원"] / cleaned["전용면적_평"]).round(0).astype("Int64")

    if "계약년월" in cleaned.columns and "계약일" in cleaned.columns:
        cleaned["거래일"] = cleaned.apply(make_trade_date, axis=1)
    else:
        cleaned["거래일"] = pd.NaT

    if "건축년도" in cleaned.columns:
        cleaned["건축년도"] = cleaned["건축년도"].apply(to_number).round(0).astype("Int64")
    else:
        cleaned["건축년도"] = pd.NA

    if "도로명" not in cleaned.columns:
        cleaned["도로명"] = "미상"
    cleaned["도로명"] = cleaned["도로명"].fillna("미상").astype(str).str.strip()
    cleaned.loc[cleaned["도로명"].isin(["", "nan", "None"]), "도로명"] = "미상"

    if "단지명" not in cleaned.columns:
        cleaned["단지명"] = "미상"
    cleaned["단지명"] = cleaned["단지명"].fillna("미상").astype(str).str.strip()
    cleaned.loc[cleaned["단지명"].isin(["", "nan", "None"]), "단지명"] = "미상"

    if "층" in cleaned.columns:
        cleaned["층"] = cleaned["층"].apply(to_number).round(0).astype("Int64")
    else:
        cleaned["층"] = pd.NA

    return cleaned.reset_index(drop=True)
