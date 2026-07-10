from __future__ import annotations

import tempfile
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import pandas as pd
import streamlit as st

from src.analyzer import analyze_transactions, build_year_bucket
from src.cleaner import clean_transactions, standardize_columns, ensure_location_columns
from src.loader import read_excel_file
from src.report import save_outputs
from src.utils import area_bucket, square_meter_to_pyeong, to_number


MOLIT_URL = "https://rt.molit.go.kr/pt/xls/xls.do?&mobileAt="

TARGET_OPTIONS = {
    "연립/다세대/다가구만 분석": ("연립", "다세대", "다가구"),
    "엑셀 전체 분석": (),
    "연립/다세대만 분석": ("연립", "다세대"),
    "다가구만 분석": ("다가구",),
}

st.set_page_config(
    page_title="빌라 실거래 분석기 V2",
    page_icon="📈",
    layout="wide",
)

st.markdown(
    """
    <style>
    .main .block-container { padding-top: 1.2rem; max-width: 1280px; }
    .hero-card {
        background: linear-gradient(135deg, #312e81 0%, #4f46e5 55%, #0ea5e9 100%);
        color: #ffffff; border-radius: 24px; padding: 30px 34px; margin-bottom: 16px;
        box-shadow: 0 14px 40px rgba(79, 70, 229, .25);
    }
    .hero-card h1 { margin: 0 0 8px 0; font-size: 34px; letter-spacing: -1.2px; color: #ffffff; }
    .hero-card p { margin: 0; font-size: 16px; line-height: 1.6; opacity: .96; color: #ffffff; }
    .hero-card .badge {
        display: inline-block; background: #fbbf24; color: #1e1b4b; font-weight: 900;
        border-radius: 999px; padding: 3px 14px; font-size: 14px; margin-bottom: 10px;
    }
    .result-card {
        border: 2px solid #c7d2fe; background: linear-gradient(180deg, #eef2ff, #f0f9ff);
        border-radius: 20px; padding: 22px; margin: 12px 0 18px 0; color: #0f172a;
    }
    .result-card h3 { margin: 0 0 8px 0; color: #4338ca; font-size: 22px; }
    .result-card .big { font-size: 25px; font-weight: 900; letter-spacing: -1px; margin: 8px 0; line-height: 1.45; color: #0f172a; }
    .result-card .note { color: #64748b; font-size: 14px; }
    div[data-testid="stMetric"] {
        background: linear-gradient(180deg, #ffffff 0%, #f5f6ff 100%);
        border: 1px solid #e0e7ff; border-top: 4px solid #6366f1;
        border-radius: 15px; padding: 14px;
        box-shadow: 0 6px 18px rgba(79, 70, 229, .08);
    }
    div[data-testid="stMetric"] label { color: #4f46e5 !important; font-weight: 700; }
    div[data-testid="stMetric"] label p { font-size: 13.5px !important; }
    div[data-testid="stMetricValue"] { color: #0f172a !important; font-weight: 800; letter-spacing: -0.8px; }
    div[data-testid="stButton"] button, div[data-testid="stDownloadButton"] button, div[data-testid="stLinkButton"] a {
        border-radius: 13px; padding: 0.72rem 1rem; font-weight: 800;
        transition: transform .12s ease;
    }
    div[data-testid="stButton"] button:hover, div[data-testid="stLinkButton"] a:hover { transform: translateY(-1px); }
    button[kind="primary"] {
        background: linear-gradient(135deg, #4f46e5 0%, #0ea5e9 100%) !important;
        border: none !important; color: #ffffff !important;
        box-shadow: 0 8px 22px rgba(79, 70, 229, .28);
    }
    button[kind="secondary"], div[data-testid="stDownloadButton"] button {
        background: #ffffff !important; border: 1.5px solid #c7d2fe !important; color: #4338ca !important;
    }
    div[data-testid="stLinkButton"] a {
        background: #eef2ff !important; border: 1.5px solid #c7d2fe !important; color: #4338ca !important;
    }
    h2, h3 { letter-spacing: -0.4px; }
    </style>
    """,
    unsafe_allow_html=True,
)


# ---------------------------------------------------------------- 공통 헬퍼

def render_dataframe_section(title: str, df: pd.DataFrame, max_rows: int = 20) -> None:
    st.subheader(title)
    if df is None or df.empty:
        st.info("표시할 데이터가 없습니다.")
    else:
        st.dataframe(df.head(max_rows), use_container_width=True, hide_index=True)


def make_download_button(label: str, path: Path, mime: str) -> None:
    if path.exists():
        st.download_button(label=label, data=path.read_bytes(), file_name=path.name,
                           mime=mime, use_container_width=True)


def load_uploaded_excels(uploaded_files) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for uploaded in uploaded_files:
        suffix = Path(uploaded.name).suffix or ".xlsx"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(uploaded.getbuffer())
            tmp_path = Path(tmp.name)
        try:
            df = read_excel_file(tmp_path)
            df["업로드파일명"] = uploaded.name
            frames.append(df)
        finally:
            tmp_path.unlink(missing_ok=True)
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


# ---------------------------------------------------------------- 전월세 데이터 처리

RENT_DEPOSIT_KEYS = ("보증금",)
RENT_MONTHLY_KEYS = ("월세",)


def _normalize(name: object) -> str:
    return str(name).strip().replace(" ", "").replace("\n", "")


def clean_rent(df: pd.DataFrame, include_keywords=(), dong: str | None = None) -> pd.DataFrame:
    """국토부 전월세 엑셀을 정리해 전세/월세 구분과 면적구간을 붙인다."""
    if df is None or df.empty:
        return pd.DataFrame()

    work = standardize_columns(df)
    work = ensure_location_columns(work)

    deposit_col = next((c for c in work.columns if any(k in _normalize(c) for k in RENT_DEPOSIT_KEYS)), None)
    monthly_col = next((c for c in work.columns if any(k in _normalize(c) for k in RENT_MONTHLY_KEYS)), None)
    if deposit_col is None or "법정동" not in work.columns or "전용면적(㎡)" not in work.columns:
        raise ValueError("전월세 엑셀에서 보증금/법정동/전용면적 컬럼을 찾지 못했습니다. 국토부 전월세 파일인지 확인해 주세요.")

    work["보증금_만원"] = work[deposit_col].apply(to_number)
    work["월세_만원"] = work[monthly_col].apply(to_number) if monthly_col is not None else 0
    work["월세_만원"] = pd.to_numeric(work["월세_만원"], errors="coerce").fillna(0)
    work = work[work["보증금_만원"].notna()].copy()

    if include_keywords:
        type_col = "주택유형" if "주택유형" in work.columns else None
        if type_col:
            mask = work[type_col].astype(str).apply(lambda v: any(k in v for k in include_keywords))
            if mask.any():
                work = work[mask].copy()

    if dong:
        work = work[work["법정동"].astype(str).str.contains(dong, na=False)].copy()

    work["법정동"] = work["법정동"].astype(str).str.strip()
    work["전용면적_평"] = work["전용면적(㎡)"].apply(to_number).apply(square_meter_to_pyeong).round(2)
    work["면적구간"] = work["전용면적_평"].apply(area_bucket)
    work["임대구분"] = work["월세_만원"].apply(lambda v: "전세" if v == 0 else "월세")
    return work.reset_index(drop=True)


def jeonse_ratio_table(sale: pd.DataFrame, rent: pd.DataFrame) -> pd.DataFrame:
    """법정동×면적구간별 전세가율 = 평균 전세보증금 / 평균 매매가 * 100"""
    jeonse = rent[rent["임대구분"] == "전세"]
    if sale.empty or jeonse.empty:
        return pd.DataFrame()
    s = (sale.groupby(["법정동", "면적구간"], dropna=False)
         .agg(매매건수=("거래금액_만원", "size"), 평균매매가_만원=("거래금액_만원", "mean"))
         .reset_index())
    j = (jeonse.groupby(["법정동", "면적구간"], dropna=False)
         .agg(전세건수=("보증금_만원", "size"), 평균전세보증금_만원=("보증금_만원", "mean"))
         .reset_index())
    merged = s.merge(j, on=["법정동", "면적구간"], how="inner")
    merged = merged[(merged["매매건수"] >= 2) & (merged["전세건수"] >= 2)].copy()
    if merged.empty:
        return merged
    merged["전세가율_%"] = (merged["평균전세보증금_만원"] / merged["평균매매가_만원"] * 100).round(1)

    def risk(v):
        if v >= 90:
            return "⚠️ 깡통 위험"
        if v >= 80:
            return "주의"
        if v >= 70:
            return "갭 작음"
        return "갭 큼"

    merged["판정"] = merged["전세가율_%"].apply(risk)
    for c in ["평균매매가_만원", "평균전세보증금_만원"]:
        merged[c] = merged[c].round(0).astype("Int64")
    merged["갭_만원"] = merged["평균매매가_만원"] - merged["평균전세보증금_만원"]
    cols = ["법정동", "면적구간", "평균매매가_만원", "평균전세보증금_만원", "갭_만원", "전세가율_%", "판정", "매매건수", "전세건수"]
    return merged[cols].sort_values("전세가율_%", ascending=False).reset_index(drop=True)


def rental_yield_table(sale: pd.DataFrame, rent: pd.DataFrame) -> pd.DataFrame:
    """법정동×면적구간별 임대수익률 (월세 기준)"""
    monthly = rent[rent["임대구분"] == "월세"]
    if sale.empty or monthly.empty:
        return pd.DataFrame()
    s = (sale.groupby(["법정동", "면적구간"], dropna=False)
         .agg(매매건수=("거래금액_만원", "size"), 평균매매가_만원=("거래금액_만원", "mean"))
         .reset_index())
    m = (monthly.groupby(["법정동", "면적구간"], dropna=False)
         .agg(월세건수=("월세_만원", "size"), 평균월세_만원=("월세_만원", "mean"), 평균보증금_만원=("보증금_만원", "mean"))
         .reset_index())
    merged = s.merge(m, on=["법정동", "면적구간"], how="inner")
    merged = merged[(merged["매매건수"] >= 2) & (merged["월세건수"] >= 2)].copy()
    if merged.empty:
        return merged
    merged["표면수익률_%"] = (merged["평균월세_만원"] * 12 / merged["평균매매가_만원"] * 100).round(2)
    invested = (merged["평균매매가_만원"] - merged["평균보증금_만원"]).clip(lower=1)
    merged["보증금감안수익률_%"] = (merged["평균월세_만원"] * 12 / invested * 100).round(2)
    for c in ["평균매매가_만원", "평균월세_만원", "평균보증금_만원"]:
        merged[c] = merged[c].round(0).astype("Int64")
    cols = ["법정동", "면적구간", "평균매매가_만원", "평균보증금_만원", "평균월세_만원", "표면수익률_%", "보증금감안수익률_%", "매매건수", "월세건수"]
    return merged[cols].sort_values("표면수익률_%", ascending=False).reset_index(drop=True)


# ---------------------------------------------------------------- 저평가 비교

def undervalue_table(sale: pd.DataFrame, min_deals: int = 3) -> pd.DataFrame:
    """같은 연식·면적대 안에서 전체 중앙값보다 평당가가 낮은 동네 찾기"""
    if sale.empty:
        return pd.DataFrame()
    work = sale.copy()
    work["건축년도구간"] = work["건축년도"].apply(build_year_bucket)
    grp = (work.groupby(["건축년도구간", "면적구간", "법정동"], dropna=False)
           .agg(거래건수=("평당가_만원", "size"), 동평당가_만원=("평당가_만원", "mean"))
           .reset_index())
    grp = grp[grp["거래건수"] >= min_deals].copy()
    if grp.empty:
        return grp
    med = (grp.groupby(["건축년도구간", "면적구간"])["동평당가_만원"]
           .median().rename("그룹중앙값_만원").reset_index())
    merged = grp.merge(med, on=["건축년도구간", "면적구간"])
    counts = merged.groupby(["건축년도구간", "면적구간"])["법정동"].transform("nunique")
    merged = merged[counts >= 2].copy()  # 비교 대상 동네가 2개 이상인 그룹만
    if merged.empty:
        return merged
    merged["편차_%"] = ((merged["동평당가_만원"] - merged["그룹중앙값_만원"]) / merged["그룹중앙값_만원"] * 100).round(1)
    for c in ["동평당가_만원", "그룹중앙값_만원"]:
        merged[c] = merged[c].round(0).astype("Int64")
    merged = merged.sort_values("편차_%").reset_index(drop=True)
    cols = ["법정동", "건축년도구간", "면적구간", "동평당가_만원", "그룹중앙값_만원", "편차_%", "거래건수"]
    return merged[cols]


# ---------------------------------------------------------------- 거래 추세

def monthly_trend(sale: pd.DataFrame) -> pd.DataFrame:
    if sale.empty or sale["거래일"].isna().all():
        return pd.DataFrame()
    work = sale[sale["거래일"].notna()].copy()
    work["월"] = work["거래일"].dt.to_period("M").astype(str)
    trend = (work.groupby("월")
             .agg(거래건수=("거래금액_만원", "size"), 평균평당가_만원=("평당가_만원", "mean"))
             .reset_index().sort_values("월"))
    trend["평균평당가_만원"] = trend["평균평당가_만원"].round(0).astype("Int64")
    return trend


def dong_momentum(sale: pd.DataFrame) -> pd.DataFrame:
    """법정동별 최근 3개월 vs 직전 3개월 거래량 비교"""
    if sale.empty or sale["거래일"].isna().all():
        return pd.DataFrame()
    work = sale[sale["거래일"].notna()].copy()
    last = work["거래일"].max()
    recent_start = last - pd.DateOffset(months=3)
    prev_start = last - pd.DateOffset(months=6)
    recent = work[work["거래일"] > recent_start].groupby("법정동").size().rename("최근3개월")
    prev = work[(work["거래일"] > prev_start) & (work["거래일"] <= recent_start)].groupby("법정동").size().rename("직전3개월")
    merged = pd.concat([recent, prev], axis=1).fillna(0).astype(int).reset_index()
    merged = merged.rename(columns={"index": "법정동"})
    merged["증감"] = merged["최근3개월"] - merged["직전3개월"]

    def label(row):
        if row["증감"] > 0:
            return "📈 증가"
        if row["증감"] < 0:
            return "📉 감소"
        return "→ 유지"

    merged["추세"] = merged.apply(label, axis=1)
    return merged.sort_values(["증감", "최근3개월"], ascending=[False, False]).reset_index(drop=True)


# ---------------------------------------------------------------- 샘플 데이터

def make_sample_sales() -> pd.DataFrame:
    rows = []
    base = [
        ("다세대", "주안동", "석바위로", 39.66, 18000, 2003),
        ("다세대", "주안동", "석바위로", 40.00, 17500, 2004),
        ("다세대", "주안동", "석바위로", 38.20, 18300, 2006),
        ("연립", "주안동", "경인로", 52.89, 23000, 2012),
        ("연립", "용현동", "인주대로", 49.50, 19800, 1998),
        ("다세대", "용현동", "인주대로", 39.00, 15500, 2005),
        ("다가구", "도화동", "숙골로", 63.40, 25500, 2016),
        ("다세대", "도화동", "숙골로", 40.10, 14800, 2004),
    ]
    ym_cycle = [202501, 202502, 202503, 202503, 202504, 202505, 202505, 202506]
    for i, (t, dong, road, area, price, built) in enumerate(base * 3):
        rows.append({
            "주택유형": t, "시군구": "인천광역시 미추홀구", "법정동": dong, "도로명": road,
            "전용면적(㎡)": area + (i % 3) * 0.5, "거래금액(만원)": f"{price + (i % 5) * 300:,}",
            "계약년월": ym_cycle[i % len(ym_cycle)], "계약일": (i % 27) + 1,
            "건축년도": built, "층": (i % 4) + 1,
        })
    return pd.DataFrame(rows)


def make_sample_rent() -> pd.DataFrame:
    rows = []
    base = [
        ("주안동", 39.5, 14500, 0), ("주안동", 40.0, 15000, 0), ("주안동", 38.8, 2000, 55),
        ("용현동", 49.0, 15500, 0), ("용현동", 39.2, 1000, 60), ("용현동", 39.5, 13500, 0),
        ("도화동", 63.0, 20000, 0), ("도화동", 40.0, 3000, 50), ("도화동", 40.2, 12200, 0),
    ]
    for i, (dong, area, deposit, monthly) in enumerate(base * 3):
        rows.append({
            "시군구": "인천광역시 미추홀구", "법정동": dong, "전용면적(㎡)": area + (i % 2) * 0.4,
            "보증금(만원)": f"{deposit + (i % 4) * 200:,}", "월세(만원)": monthly,
            "계약년월": 202501 + (i % 6), "계약일": (i % 25) + 1,
        })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------- 화면

st.markdown(
    """
    <div class="hero-card">
      <span class="badge">VERSION 2</span>
      <h1>📈 빌라 실거래 분석기 V2</h1>
      <p>매매 엑셀에 <b>전월세 엑셀</b>까지 올리면 — 거래 많은 유형 찾기에 더해
      <b>전세가율 · 임대수익률 · 저평가 동네 · 거래 추세</b>까지 한 번에 분석합니다.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

left, right = st.columns([1, 2.2])

with left:
    st.header("① 국토부에서 엑셀 받기")
    st.link_button("🏛️ 국토교통부 실거래가 사이트 열기", MOLIT_URL, use_container_width=True)
    st.caption("매매 파일과 전월세 파일을 각각 내려받으세요. (같은 지역·기간 권장)")

    st.header("② 매매 엑셀 업로드")
    sale_files = st.file_uploader("매매 실거래가 엑셀", type=["xlsx", "xls"], accept_multiple_files=True, key="sale")

    st.header("③ 전월세 엑셀 업로드 (선택)")
    rent_files = st.file_uploader("전월세 실거래가 엑셀 — 전세가율·수익률 분석에 사용", type=["xlsx", "xls"], accept_multiple_files=True, key="rent")

    st.header("④ 분석 설정")
    target_label = st.selectbox("물건 종류 필터", options=list(TARGET_OPTIONS.keys()), index=0)
    target_keywords = TARGET_OPTIONS[target_label]
    with st.expander("세부 필터 (선택사항)", expanded=False):
        dong_keyword = st.text_input("특정 법정동만 보기", placeholder="예: 주안동")
        title_hint = st.text_input("리포트 제목에 넣을 지역명", placeholder="예: 인천 미추홀구 2025년")

    analyze_clicked = st.button("📊 분석하기", type="primary", use_container_width=True)
    sample_clicked = st.button("👀 결과 화면 미리보기 (샘플)", use_container_width=True)

with right:
    st.header("분석 결과")
    if not analyze_clicked and not sample_clicked:
        st.info("왼쪽에서 매매 엑셀(필수)과 전월세 엑셀(선택)을 올리고 '분석하기'를 누르세요.")
        st.stop()
    if analyze_clicked and not sale_files:
        st.warning("매매 엑셀 파일을 1개 이상 업로드해 주세요.")
        st.stop()

    try:
        with st.spinner("데이터를 정리하고 분석하는 중입니다..."):
            if sample_clicked and not analyze_clicked:
                raw_sale = make_sample_sales()
                raw_rent = make_sample_rent()
                report_title = title_hint.strip() or "인천 미추홀구 2025년 샘플"
                st.caption("샘플 데이터 미리보기 모드입니다. 실제 분석은 엑셀 업로드 후 실행하세요.")
            else:
                raw_sale = load_uploaded_excels(sale_files)
                raw_rent = load_uploaded_excels(rent_files) if rent_files else pd.DataFrame()
                report_title = title_hint.strip() or "빌라 실거래 분석 리포트 V2"
            if raw_sale.empty:
                st.warning("매매 엑셀에서 데이터를 읽지 못했습니다.")
                st.stop()

            dong = dong_keyword.strip() or None
            cleaned = clean_transactions(raw_sale, include_keywords=target_keywords, dong=dong)
            if cleaned.empty:
                st.warning("조건에 맞는 매매 데이터가 없습니다. 필터를 '엑셀 전체 분석'으로 바꿔보세요.")
                st.stop()

            rent_cleaned = pd.DataFrame()
            rent_error = None
            if not raw_rent.empty:
                try:
                    rent_cleaned = clean_rent(raw_rent, include_keywords=(), dong=dong)
                except ValueError as ve:
                    rent_error = str(ve)

            analysis = analyze_transactions(cleaned)
            jeonse = jeonse_ratio_table(cleaned, rent_cleaned) if not rent_cleaned.empty else pd.DataFrame()
            yields = rental_yield_table(cleaned, rent_cleaned) if not rent_cleaned.empty else pd.DataFrame()
            undervalued = undervalue_table(cleaned)
            trend = monthly_trend(cleaned)
            momentum = dong_momentum(cleaned)

        # ---- 핵심 요약
        combo = analysis.get("road_year_area_combo")
        if combo is not None and not combo.empty:
            top = combo.iloc[0]
            st.markdown(
                f"""
                <div class="result-card">
                  <h3>🔍 핵심 발견</h3>
                  <div class="big">{report_title}에서 가장 반복적으로 거래된 유형은<br>
                  “{top['법정동']} · {top['도로명']} · {top['건축년도구간']} · {top['면적구간']}” 입니다.</div>
                  <div class="note">거래량 기준 관찰 결과이며, 투자 추천을 의미하지 않습니다.</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        summary = analysis["summary"]
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("총 매매건수", f"{summary['total_transactions']:,}건")
        m2.metric("평균 평당가", f"{summary.get('avg_unit_price_manwon') or 0:,}만원")
        m3.metric("전월세 데이터", f"{len(rent_cleaned):,}건" if not rent_cleaned.empty else "없음")
        m4.metric("최근 거래일", summary.get("latest_trade_date") or "미상")

        st.divider()
        tab1, tab2, tab3, tab4, tab5 = st.tabs(
            ["🏘️ 핵심 분석", "🔑 전세가율", "💰 임대수익률", "🔻 저평가 비교", "📅 거래 추세"]
        )

        with tab1:
            render_dataframe_section("도로명 + 연식 + 면적대 조합 TOP 50", analysis["road_year_area_combo"], 50)
            render_dataframe_section("추가조사 후보", analysis["follow_up_candidates"], 20)

        with tab2:
            st.caption("전세가율 = 평균 전세보증금 ÷ 평균 매매가. 90% 이상은 깡통전세 위험, 70% 안팎은 갭이 작은 구간입니다.")
            if rent_error:
                st.error(rent_error)
            elif jeonse.empty:
                st.info("전월세 엑셀을 올리면 동네·평수대별 전세가율이 계산됩니다. (매매·전세 각 2건 이상인 조합만 표시)")
            else:
                high = jeonse[jeonse["전세가율_%"] >= 90]
                if not high.empty:
                    st.warning(f"전세가율 90% 이상 조합이 {len(high)}개 있습니다. 역전세·깡통 위험을 확인하세요.")
                render_dataframe_section("동네 × 평수대별 전세가율", jeonse, 50)

        with tab3:
            st.caption("표면수익률 = 연간 월세 ÷ 매매가, 보증금감안수익률 = 연간 월세 ÷ (매매가 − 보증금). 공실·수리비·세금 미반영.")
            if rent_error:
                st.error(rent_error)
            elif yields.empty:
                st.info("전월세 엑셀에 월세 거래가 있으면 동네·평수대별 임대수익률이 계산됩니다.")
            else:
                render_dataframe_section("동네 × 평수대별 임대수익률", yields, 50)

        with tab4:
            st.caption("같은 연식·평수대 그룹 안에서 전체 중앙값보다 평당가가 낮은 동네입니다. 싼 데는 이유가 있을 수 있으니 현장 확인이 필수입니다.")
            if undervalued.empty:
                st.info("비교할 수 있는 동네 조합이 부족합니다. (같은 연식·평수대에 동네 2곳 이상, 각 3건 이상 필요)")
            else:
                cheap = undervalued[undervalued["편차_%"] <= -10]
                if not cheap.empty:
                    st.success(f"그룹 중앙값보다 10% 이상 낮게 거래된 조합이 {len(cheap)}개 있습니다.")
                render_dataframe_section("연식·평수대 그룹 내 평당가 편차 (낮은 순)", undervalued, 50)

        with tab5:
            if trend.empty:
                st.info("계약년월 정보가 없어 추세를 계산할 수 없습니다.")
            else:
                st.subheader("월별 거래량")
                st.bar_chart(trend.set_index("월")["거래건수"])
                st.subheader("월별 평균 평당가 (만원)")
                st.line_chart(trend.set_index("월")["평균평당가_만원"])
                render_dataframe_section("동네별 거래 모멘텀 (최근 3개월 vs 직전 3개월)", momentum, 50)

        # ---- 다운로드
        with tempfile.TemporaryDirectory(prefix="realestate-v2-") as tmpdir:
            outputs = save_outputs(cleaned, analysis, tmpdir, title=report_title)
            st.divider()
            st.subheader("📥 다운로드")
            d1, d2 = st.columns(2)
            with d1:
                make_download_button("📄 분석 리포트 다운로드", outputs["html"], "text/html")
            with d2:
                make_download_button("📊 상세 엑셀 다운로드", outputs["excel"],
                                     "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    except Exception as exc:
        st.error("분석 중 문제가 생겼습니다. 엑셀 컬럼에 시군구, 법정동, 전용면적, 거래금액이 있는지 확인해 주세요.")
        with st.expander("오류 자세히 보기", expanded=False):
            st.exception(exc)
