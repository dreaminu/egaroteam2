from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SectionConfig:
    key: str
    title: str
    include_keywords: tuple[str, ...]
    area_column_hint: str = "전용면적(㎡)"
    unit_price_label: str = "평당가_만원"


SECTION_CONFIGS: dict[str, SectionConfig] = {
    "apt": SectionConfig(
        key="apt",
        title="아파트",
        include_keywords=("아파트",),
    ),
    "villa": SectionConfig(
        key="villa",
        title="연립/다세대",
        include_keywords=("연립", "다세대"),
    ),
    "single_multi": SectionConfig(
        key="single_multi",
        title="단독/다가구",
        include_keywords=("단독", "다가구", "단독주택", "다가구주택"),
    ),
    "officetel": SectionConfig(
        key="officetel",
        title="오피스텔",
        include_keywords=("오피스텔",),
    ),
    "land": SectionConfig(
        key="land",
        title="토지",
        include_keywords=("토지", "대지", "전", "답", "임야"),
        area_column_hint="대지면적(㎡)",
        unit_price_label="평당가_만원",
    ),
    "pre_sale_right": SectionConfig(
        key="pre_sale_right",
        title="분양/입주권",
        include_keywords=("분양권", "입주권"),
    ),
    "commercial": SectionConfig(
        key="commercial",
        title="상업/업무용",
        include_keywords=("상업", "업무", "근린", "상가", "사무", "판매", "생활시설"),
    ),
    "factory_warehouse": SectionConfig(
        key="factory_warehouse",
        title="공장/창고 등",
        include_keywords=("공장", "창고", "제조", "산업", "물류"),
    ),
    "all": SectionConfig(
        key="all",
        title="전체",
        include_keywords=(),
    ),
}


def get_section_config(section: str | None) -> SectionConfig:
    key = (section or "villa").strip()
    if key not in SECTION_CONFIGS:
        valid = ", ".join(SECTION_CONFIGS)
        raise ValueError(f"알 수 없는 섹션입니다: {key}. 사용 가능 섹션: {valid}")
    return SECTION_CONFIGS[key]


def section_help_text() -> str:
    return ", ".join(f"{key}={config.title}" for key, config in SECTION_CONFIGS.items())
