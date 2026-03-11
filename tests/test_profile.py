"""
프로필 매니저 유닛 테스트
"""

from pathlib import Path

import pytest

from src.core.models import BidType
from src.storage.profile_manager import load_profiles


def test_load_default_profiles():
    """기본 profiles.yaml 로드 테스트"""
    config_path = Path(__file__).parent.parent / "config" / "profiles.yaml"
    profiles, settings = load_profiles(config_path)

    assert len(profiles) >= 1
    assert profiles[0].name == "지적측량 용역"
    assert profiles[0].enabled is True
    assert BidType.SERVICE in profiles[0].bid_types
    assert "지적측량" in profiles[0].keywords.or_keywords
    assert "확정측량" in profiles[0].keywords.or_keywords
    assert "지적재조사" in profiles[0].keywords.or_keywords
    assert "취소공고" in profiles[0].keywords.exclude

    assert settings.check_interval_minutes == 30
    assert settings.timezone == "Asia/Seoul"


def test_load_nonexistent_file():
    """존재하지 않는 파일 → FileNotFoundError"""
    with pytest.raises(FileNotFoundError):
        load_profiles(Path("/tmp/nonexistent.yaml"))
