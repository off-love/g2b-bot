"""
알림 프로필 관리자

profiles.yaml 파일을 로드하고 AlertProfile 데이터 객체로 변환합니다.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

from src.core.models import (
    AlertProfile,
    BidType,
    DemandAgencyConfig,
    GlobalSettings,
    KeywordConfig,
    PriceRange,
)


def _find_config_path() -> Path:
    """프로필 설정 파일 경로 탐색

    우선순위:
    1. PROFILES_PATH 환경변수
    2. 프로젝트 루트의 config/profiles.yaml
    """
    env_path = os.environ.get("PROFILES_PATH")
    if env_path:
        return Path(env_path)

    # 프로젝트 루트 기준 (src/storage/ → 2단계 상위)
    project_root = Path(__file__).parent.parent.parent
    return project_root / "config" / "profiles.yaml"


def _parse_bid_type(value: str) -> BidType:
    """문자열을 BidType 열거형으로 변환"""
    mapping = {
        "service": BidType.SERVICE,
        "goods": BidType.GOODS,
        "construction": BidType.CONSTRUCTION,
        "foreign": BidType.FOREIGN,
    }
    bt = mapping.get(value.lower())
    if bt is None:
        raise ValueError(
            f"알 수 없는 bid_type: '{value}'. "
            f"가능한 값: {list(mapping.keys())}"
        )
    return bt


def _parse_keywords(data: dict[str, Any] | None) -> KeywordConfig:
    """키워드 설정 파싱"""
    if not data:
        return KeywordConfig()
    return KeywordConfig(
        or_keywords=[str(k) for k in data.get("or", [])],
        and_keywords=[str(k) for k in data.get("and", [])],
        exclude=[str(k) for k in data.get("exclude", [])],
    )


def _parse_demand_agencies(data: dict[str, Any] | None) -> DemandAgencyConfig:
    """수요기관 필터 설정 파싱"""
    if not data:
        return DemandAgencyConfig()
    return DemandAgencyConfig(
        by_code=[str(c) for c in data.get("by_code", [])],
        by_name=[str(n) for n in data.get("by_name", [])],
    )


def _parse_price_range(data: dict[str, Any] | None) -> PriceRange:
    """금액 범위 설정 파싱"""
    if not data:
        return PriceRange()
    return PriceRange(
        min_price=int(data.get("min", 0)),
        max_price=int(data.get("max", 0)),
    )


def _parse_profile(data: dict[str, Any]) -> AlertProfile:
    """단일 프로필 데이터를 AlertProfile 으로 변환"""
    name = data.get("name", "이름없는 프로필")
    enabled = data.get("enabled", True)

    # bid_types 파싱
    bid_types_raw = data.get("bid_types", [])
    bid_types = [_parse_bid_type(bt) for bt in bid_types_raw]

    return AlertProfile(
        name=name,
        enabled=enabled,
        bid_types=bid_types,
        keywords=_parse_keywords(data.get("keywords")),
        demand_agencies=_parse_demand_agencies(data.get("demand_agencies")),
        regions=[str(r) for r in data.get("regions", [])],
        price_range=_parse_price_range(data.get("price_range")),
        include_prebid=data.get("include_prebid", True),
    )


def _parse_settings(data: dict[str, Any] | None) -> GlobalSettings:
    """전역 설정 파싱"""
    if not data:
        return GlobalSettings()
    return GlobalSettings(
        check_interval_minutes=int(data.get("check_interval_minutes", 30)),
        query_buffer_hours=int(data.get("query_buffer_hours", 1)),
        max_results_per_page=int(data.get("max_results_per_page", 999)),
        timezone=str(data.get("timezone", "Asia/Seoul")),
    )


def load_profiles(config_path: Path | None = None) -> tuple[list[AlertProfile], GlobalSettings]:
    """프로필 설정 파일을 로드합니다.

    Args:
        config_path: 설정 파일 경로 (None이면 자동 탐색)

    Returns:
        (활성 프로필 목록, 전역 설정) 튜플

    Raises:
        FileNotFoundError: 설정 파일이 없을 때
        ValueError: YAML 파싱 오류 시
    """
    if config_path is None:
        config_path = _find_config_path()

    if not config_path.exists():
        raise FileNotFoundError(f"프로필 설정 파일을 찾을 수 없습니다: {config_path}")

    with open(config_path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    if not raw or not isinstance(raw, dict):
        raise ValueError(f"유효하지 않은 프로필 설정 파일: {config_path}")

    # 프로필 목록 파싱
    profiles_raw = raw.get("profiles", [])
    all_profiles = [_parse_profile(p) for p in profiles_raw]

    # 활성 프로필만 필터
    active_profiles = [p for p in all_profiles if p.enabled]

    # 전역 설정 파싱
    settings = _parse_settings(raw.get("settings"))

    return active_profiles, settings
