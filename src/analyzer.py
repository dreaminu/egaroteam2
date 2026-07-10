from __future__ import annotations

import pandas as pd

AREA_ORDER = [
    "10평 이하",
    "10~12평",
    "12~14평",
    "14~16평",
    "16~18평",
    "18~20평",
    "20~24평",
    "24~30평",
    "30평 이상",
    "미상",
]

BUILD_YEAR_ORDER = [
    "1990년 이전",
    "1990~1999년식",
    "2000~2009년식",
    "2010~2019년식",
    "2020년 이후",
    "미상",
]


def count_by(df: pd.DataFrame, columns: list[str], count_name: str = "거래건수") -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=columns + [count_name])
    return (
        df.groupby(columns, dropna=False)
        .size()
        .reset_index(name=count_name)
        .sort_values(count_name, ascending=False)
        .reset_index(drop=True)
    )


def average_by(df: pd.DataFrame, columns: list[str], value: str, name: str) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=columns + [name, "거래건수"])
    return (
        df.groupby(columns, dropna=False)
        .agg(**{name: (value, "mean"), "거래건수": (value, "size")})
        .reset_index()
        .assign(**{name: lambda x: x[name].round(0).astype("Int64")})
        .sort_values(name, ascending=False)
        .reset_index(drop=True)
    )


def build_year_bucket(value: object) -> str:
    if pd.isna(value):
        return "미상"
    try:
        year = int(float(str(value)))
    except (TypeError, ValueError):
        return "미상"
    if year < 1990:
        return "1990년 이전"
    if year <= 1999:
        return "1990~1999년식"
    if year <= 2009:
        return "2000~2009년식"
    if year <= 2019:
        return "2010~2019년식"
    return "2020년 이후"


def _latest_trade(series: pd.Series) -> str | None:
    value = pd.to_datetime(series, errors="coerce").max()
    if pd.isna(value):
        return None
    return pd.Timestamp(value).strftime("%Y-%m-%d")


def group_transaction_stats(df: pd.DataFrame, columns: list[str], limit: int | None = None) -> pd.DataFrame:
    result_columns = columns + [
        "거래건수",
        "평균거래금액_만원",
        "최저거래금액_만원",
        "최고거래금액_만원",
        "평균평당가_만원",
        "최근거래일",
        "대표면적구간",
        "대표연식구간",
    ]
    if df.empty:
        return pd.DataFrame(columns=result_columns)

    work = df.copy()
    if "건축년도구간" not in work.columns:
        work["건축년도구간"] = work["건축년도"].apply(build_year_bucket)

    grouped = (
        work.groupby(columns, dropna=False)
        .agg(
            거래건수=("거래금액_만원", "size"),
            평균거래금액_만원=("거래금액_만원", "mean"),
            최저거래금액_만원=("거래금액_만원", "min"),
            최고거래금액_만원=("거래금액_만원", "max"),
            평균평당가_만원=("평당가_만원", "mean"),
            최근거래일=("거래일", _latest_trade),
            대표면적구간=("면적구간", lambda s: s.mode().iloc[0] if not s.mode().empty else "미상"),
            대표연식구간=("건축년도구간", lambda s: s.mode().iloc[0] if not s.mode().empty else "미상"),
        )
        .reset_index()
    )
    for col in ["평균거래금액_만원", "최저거래금액_만원", "최고거래금액_만원", "평균평당가_만원"]:
        grouped[col] = grouped[col].round(0).astype("Int64")

    grouped = grouped.sort_values(["거래건수", "평균평당가_만원"], ascending=[False, True]).reset_index(drop=True)
    grouped = grouped[result_columns]
    if limit:
        grouped = grouped.head(limit)
    return grouped


def popular_area_by_dong(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=["법정동", "인기면적대", "거래건수"])
    counts = count_by(df, ["법정동", "면적구간"])
    counts["면적구간"] = pd.Categorical(counts["면적구간"], categories=AREA_ORDER, ordered=True)
    counts = counts.sort_values(["법정동", "거래건수", "면적구간"], ascending=[True, False, True])
    result = counts.drop_duplicates("법정동", keep="first").copy()
    result = result.rename(columns={"면적구간": "인기면적대"})
    return result[["법정동", "인기면적대", "거래건수"]].sort_values("거래건수", ascending=False).reset_index(drop=True)


def top_dong_area_combinations(df: pd.DataFrame) -> pd.DataFrame:
    """Find the neighborhood + size band combinations with the highest transaction volume."""
    columns = [
        "시군구",
        "법정동",
        "면적구간",
        "거래건수",
        "평균거래금액_만원",
        "평균평당가_만원",
        "최근거래일",
    ]
    if df.empty:
        return pd.DataFrame(columns=columns)

    grouped = (
        df.groupby(["시군구", "법정동", "면적구간"], dropna=False)
        .agg(
            거래건수=("거래금액_만원", "size"),
            평균거래금액_만원=("거래금액_만원", "mean"),
            평균평당가_만원=("평당가_만원", "mean"),
            최근거래일=("거래일", "max"),
        )
        .reset_index()
    )
    grouped["평균거래금액_만원"] = grouped["평균거래금액_만원"].round(0).astype("Int64")
    grouped["평균평당가_만원"] = grouped["평균평당가_만원"].round(0).astype("Int64")
    grouped["최근거래일"] = pd.to_datetime(grouped["최근거래일"], errors="coerce").dt.strftime("%Y-%m-%d")
    grouped["면적구간"] = pd.Categorical(grouped["면적구간"], categories=AREA_ORDER, ordered=True)
    return (
        grouped.sort_values(["거래건수", "평균거래금액_만원", "면적구간"], ascending=[False, False, True])
        .reset_index(drop=True)
        [columns]
    )


def latest_trade_date(df: pd.DataFrame) -> str | None:
    if df.empty or "거래일" not in df.columns:
        return None
    value = df["거래일"].max()
    if pd.isna(value):
        return None
    return pd.Timestamp(value).strftime("%Y-%m-%d")


def make_follow_up_candidates(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=["법정동", "도로명", "건축년도구간", "면적구간", "거래건수", "평균거래금액_만원", "평균평당가_만원", "최근거래일", "확인메모"])
    combo = group_transaction_stats(df, ["법정동", "도로명", "건축년도구간", "면적구간"])
    if combo.empty:
        return combo
    dong_avg = df.groupby("법정동", dropna=False)["평당가_만원"].mean().round(0).rename("동평균평당가_만원").reset_index()
    result = combo.merge(dong_avg, on="법정동", how="left")
    result["동평균평당가_만원"] = result["동평균평당가_만원"].astype("Int64")
    result["평당가비교"] = result["평균평당가_만원"] - result["동평균평당가_만원"]
    result = result.sort_values(["거래건수", "평당가비교", "최근거래일"], ascending=[False, True, False]).head(20)
    result["확인메모"] = "거래량과 가격이 반복 관찰되는 후보입니다. 권리관계·건물상태·전세가율·임대수요는 별도 확인 필요."
    cols = ["법정동", "도로명", "건축년도구간", "면적구간", "거래건수", "평균거래금액_만원", "평균평당가_만원", "동평균평당가_만원", "평당가비교", "최근거래일", "확인메모"]
    return result[cols].reset_index(drop=True)


def analyze_transactions(df: pd.DataFrame) -> dict:
    work = df.copy()
    work["건축년도구간"] = work["건축년도"].apply(build_year_bucket)

    by_sigungu = count_by(work, ["시군구"])
    by_dong = count_by(work, ["법정동"])
    by_area = count_by(work, ["면적구간"])
    by_build_year = count_by(work, ["건축년도구간"])
    by_floor = count_by(work, ["층"])
    avg_price_by_dong = average_by(work, ["법정동"], "거래금액_만원", "평균거래금액_만원")
    avg_unit_price_by_dong = average_by(work, ["법정동"], "평당가_만원", "평균평당가_만원")
    popular_area = popular_area_by_dong(work)
    top_dong_area = top_dong_area_combinations(work)
    road_volume = group_transaction_stats(work, ["법정동", "도로명"], limit=50)
    road_build_year = group_transaction_stats(work, ["법정동", "도로명", "건축년도구간"], limit=100)
    road_area = group_transaction_stats(work, ["법정동", "도로명", "면적구간"], limit=100)
    road_year_area_combo = group_transaction_stats(work, ["법정동", "도로명", "건축년도구간", "면적구간"], limit=100)
    follow_up_candidates = make_follow_up_candidates(work)
    latest = latest_trade_date(work)

    summary = {
        "total_transactions": int(len(work)),
        "sigungu_count": int(work["시군구"].nunique()) if "시군구" in work.columns else 0,
        "dong_count": int(work["법정동"].nunique()) if "법정동" in work.columns else 0,
        "road_count": int(work["도로명"].nunique()) if "도로명" in work.columns else 0,
        "avg_trade_price_manwon": int(round(work["거래금액_만원"].mean())) if not work.empty else None,
        "avg_unit_price_manwon": int(round(work["평당가_만원"].mean())) if not work.empty else None,
        "latest_trade_date": latest,
    }

    return {
        "summary": summary,
        "latest_trade_date": latest,
        "by_sigungu": by_sigungu,
        "by_dong": by_dong,
        "by_area": by_area,
        "popular_area_by_dong": popular_area,
        "top_dong_area": top_dong_area,
        "road_volume": road_volume,
        "road_build_year": road_build_year,
        "road_area": road_area,
        "road_year_area_combo": road_year_area_combo,
        "follow_up_candidates": follow_up_candidates,
        "avg_price_by_dong": avg_price_by_dong,
        "avg_unit_price_by_dong": avg_unit_price_by_dong,
        "by_build_year": by_build_year,
        "by_floor": by_floor,
        "top_dong_volume": by_dong.head(20),
        "top_avg_price": avg_price_by_dong.head(20),
        "top_unit_price": avg_unit_price_by_dong.head(20),
    }
