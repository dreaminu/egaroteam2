from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from .utils import ensure_dir


SHEET_NAMES = {
    "top_dong_area": "동네_평수_TOP",
    "road_volume": "도로명별_TOP",
    "road_build_year": "도로명_연식별",
    "road_area": "도로명_면적대별",
    "road_year_area_combo": "도로명_연식_면적조합",
    "follow_up_candidates": "추가조사_후보",
    "by_sigungu": "시군구별_거래량",
    "top_dong_volume": "법정동_TOP",
    "by_area": "면적대별_거래량",
    "popular_area_by_dong": "법정동별_인기면적",
    "top_avg_price": "평균가_TOP",
    "top_unit_price": "평당가_TOP",
    "by_build_year": "연식별_분포",
    "by_floor": "층별_분포",
}


def df_to_html_table(df: pd.DataFrame | None, max_rows: int = 20) -> str:
    if df is None or df.empty:
        return "<p class='empty'>데이터 없음</p>"
    return df.head(max_rows).to_html(index=False, classes="data-table", border=0)


def make_investment_notes(analysis: dict[str, Any]) -> list[str]:
    summary = analysis["summary"]
    notes = [
        "이 리포트는 업로드한 국토교통부 실거래가 엑셀에 포함된 거래 데이터만 집계합니다.",
        "거래량이 많은 지역은 시장 참여가 상대적으로 활발했다는 의미이며, 투자 가치가 높다는 뜻은 아닙니다.",
        "재개발·재건축 가능성, 전세가율, 임대수익률, 권리관계, 건물 상태는 이 매매 데이터만으로 판단하지 않았습니다.",
    ]
    if summary.get("avg_trade_price_manwon") is not None:
        notes.append(f"전체 평균 거래금액은 약 {summary['avg_trade_price_manwon']:,}만원입니다.")
    if summary.get("avg_unit_price_manwon") is not None:
        notes.append(f"전체 평균 평당가는 약 {summary['avg_unit_price_manwon']:,}만원입니다.")
    return notes


def _top_sentence(analysis: dict[str, Any]) -> str:
    combo = analysis.get("road_year_area_combo")
    if isinstance(combo, pd.DataFrame) and not combo.empty:
        row = combo.iloc[0]
        return (
            f"가장 반복적으로 관찰된 조합은 <b>{row.get('법정동', '')} · {row.get('도로명', '')} · "
            f"{row.get('건축년도구간', '')} · {row.get('면적구간', '')}</b>이며, "
            f"거래건수는 <b>{int(row.get('거래건수', 0)):,}건</b>입니다."
        )
    top = analysis.get("top_dong_area")
    if isinstance(top, pd.DataFrame) and not top.empty:
        row = top.iloc[0]
        return f"가장 거래량이 많은 조합은 <b>{row.get('법정동', '')} · {row.get('면적구간', '')}</b>입니다."
    return "조건에 맞는 핵심 조합을 찾지 못했습니다."


def render_html(cleaned: pd.DataFrame, analysis: dict[str, Any], title: str = "실거래가 거래량 분석 리포트") -> str:
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    summary = analysis["summary"]
    notes = make_investment_notes(analysis)
    note_html = "".join(f"<li>{note}</li>" for note in notes)
    top_sentence = _top_sentence(analysis)

    return f"""<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <title>{title}</title>
  <style>
    * {{ box-sizing: border-box; }}
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Noto Sans KR', sans-serif; margin: 0; color: #172033; background: #eef3f8; }}
    .page {{ max-width: 1200px; margin: 0 auto; padding: 28px; }}
    .hero {{ background: linear-gradient(135deg, #123c69, #2563eb 55%, #14b8a6); color: white; border-radius: 28px; padding: 34px; box-shadow: 0 18px 50px rgba(37,99,235,.25); }}
    .hero h1 {{ margin: 0 0 12px 0; font-size: 34px; letter-spacing: -1.2px; }}
    .hero p {{ margin: 0; font-size: 18px; line-height: 1.65; opacity: .96; }}
    .answer {{ background: #ecfdf5; border: 2px solid #9ae6b4; border-radius: 22px; padding: 22px; margin: 20px 0; font-size: 20px; line-height: 1.65; }}
    .card {{ background: white; border-radius: 22px; padding: 24px; margin: 18px 0; box-shadow: 0 8px 26px rgba(15,23,42,.07); }}
    .card h2 {{ margin-top: 0; color: #123c69; letter-spacing: -0.6px; }}
    .summary-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: 14px; }}
    .metric {{ background: linear-gradient(180deg, #f8fbff, #eef6ff); border: 1px solid #dbeafe; border-radius: 18px; padding: 18px; }}
    .metric .label {{ color: #64748b; font-size: 13px; }}
    .metric .value {{ font-size: 25px; font-weight: 900; margin-top: 7px; letter-spacing: -0.8px; }}
    table.data-table {{ width: 100%; border-collapse: collapse; font-size: 14px; overflow: hidden; border-radius: 14px; }}
    table.data-table th {{ background: #1e3a8a; color: white; text-align: left; padding: 10px; white-space: nowrap; }}
    table.data-table td {{ border-bottom: 1px solid #e5e7eb; padding: 9px; }}
    table.data-table tr:nth-child(even) td {{ background: #f8fafc; }}
    .warning {{ background: #fff7ed; border-left: 7px solid #f97316; }}
    .empty {{ color: #777; }}
    .two {{ display: grid; grid-template-columns: 1fr 1fr; gap: 18px; }}
    @media (max-width: 900px) {{ .two {{ grid-template-columns: 1fr; }} .page {{ padding: 14px; }} }}
  </style>
</head>
<body>
<div class="page">
  <section class="hero">
    <h1>{title}</h1>
    <p>업로드한 엑셀을 기준으로 거래량이 많은 동네, 도로명, 연식, 면적대 조합을 자동으로 찾아낸 리포트입니다.<br>생성일시: {generated_at}</p>
  </section>

  <section class="answer">{top_sentence}<br><span style="font-size:14px;color:#64748b;">거래량 기준 관찰 결과이며 투자 추천이 아닙니다.</span></section>

  <div class="card">
    <h2>전체 요약</h2>
    <div class="summary-grid">
      <div class="metric"><div class="label">총 거래건수</div><div class="value">{summary.get('total_transactions', 0):,}건</div></div>
      <div class="metric"><div class="label">시군구 수</div><div class="value">{summary.get('sigungu_count', 0):,}</div></div>
      <div class="metric"><div class="label">법정동 수</div><div class="value">{summary.get('dong_count', 0):,}</div></div>
      <div class="metric"><div class="label">도로명 수</div><div class="value">{summary.get('road_count', 0):,}</div></div>
      <div class="metric"><div class="label">평균 거래금액</div><div class="value">{summary.get('avg_trade_price_manwon') or 0:,}만원</div></div>
      <div class="metric"><div class="label">평균 평당가</div><div class="value">{summary.get('avg_unit_price_manwon') or 0:,}만원</div></div>
      <div class="metric"><div class="label">최근 거래일</div><div class="value">{summary.get('latest_trade_date') or '미상'}</div></div>
    </div>
  </div>

  <div class="card warning"><h2>해석 주의사항</h2><ul>{note_html}</ul></div>

  <div class="card"><h2>핵심: 도로명 + 연식 + 면적대 조합 TOP 30</h2>{df_to_html_table(analysis.get('road_year_area_combo'), 30)}</div>
  <div class="two">
    <div class="card"><h2>도로명별 거래량 TOP 20</h2>{df_to_html_table(analysis.get('road_volume'), 20)}</div>
    <div class="card"><h2>추가조사 후보 TOP 20</h2>{df_to_html_table(analysis.get('follow_up_candidates'), 20)}</div>
  </div>
  <div class="card"><h2>거래량 많은 동네 + 평수대 TOP 20</h2>{df_to_html_table(analysis.get('top_dong_area'), 20)}</div>
  <div class="two">
    <div class="card"><h2>도로명 + 연식별 분석</h2>{df_to_html_table(analysis.get('road_build_year'), 30)}</div>
    <div class="card"><h2>도로명 + 면적대별 분석</h2>{df_to_html_table(analysis.get('road_area'), 30)}</div>
  </div>
  <div class="two">
    <div class="card"><h2>법정동별 거래량</h2>{df_to_html_table(analysis['top_dong_volume'])}</div>
    <div class="card"><h2>면적 구간별 거래건수</h2>{df_to_html_table(analysis['by_area'], 50)}</div>
  </div>
  <div class="two">
    <div class="card"><h2>연식별 거래 분포</h2>{df_to_html_table(analysis['by_build_year'], 100)}</div>
    <div class="card"><h2>층별 거래 분포</h2>{df_to_html_table(analysis['by_floor'], 100)}</div>
  </div>
</div>
</body>
</html>"""


def dataframe_to_records(df: pd.DataFrame) -> list[dict[str, Any]]:
    if df.empty:
        return []
    safe = df.copy()
    for col in safe.columns:
        if pd.api.types.is_datetime64_any_dtype(safe[col]):
            safe[col] = safe[col].dt.strftime("%Y-%m-%d")
    safe = safe.where(pd.notnull(safe), None)
    return safe.to_dict(orient="records")


def save_outputs(
    cleaned: pd.DataFrame,
    analysis: dict[str, Any],
    output_dir: str | Path = "output",
    title: str = "실거래가 거래량 분석 리포트",
) -> dict[str, Path]:
    out = ensure_dir(output_dir)
    html_path = out / "realestate_report.html"
    excel_path = out / "realestate_analysis.xlsx"
    csv_path = out / "cleaned_transactions.csv"
    json_path = out / "analysis_result.json"

    html_path.write_text(render_html(cleaned, analysis, title=title), encoding="utf-8")
    cleaned.to_csv(csv_path, index=False, encoding="utf-8-sig")

    with pd.ExcelWriter(excel_path, engine="openpyxl") as writer:
        pd.DataFrame([analysis["summary"]]).to_excel(writer, sheet_name="전체요약", index=False)
        for key, sheet in SHEET_NAMES.items():
            value = analysis.get(key)
            if isinstance(value, pd.DataFrame):
                value.to_excel(writer, sheet_name=sheet[:31], index=False)
        cleaned.to_excel(writer, sheet_name="정리된_원본거래", index=False)

    json_ready = {
        "summary": analysis["summary"],
        "tables": {
            key: dataframe_to_records(value)
            for key, value in analysis.items()
            if isinstance(value, pd.DataFrame)
        },
    }
    json_path.write_text(json.dumps(json_ready, ensure_ascii=False, indent=2, default=str), encoding="utf-8")

    return {
        "html": html_path,
        "excel": excel_path,
        "csv": csv_path,
        "json": json_path,
    }
