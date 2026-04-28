"""
시간 유틸리티 유닛 테스트
"""

from datetime import datetime

from src.utils import time_utils


def test_get_incremental_query_range_uses_last_check_with_overlap(monkeypatch):
    fixed_now = datetime(2026, 4, 21, 12, 0, tzinfo=time_utils.KST)
    monkeypatch.setattr(time_utils, "now_kst", lambda: fixed_now)

    begin, end = time_utils.get_incremental_query_range(
        "2026-04-20T11:30:00+09:00",
        buffer_minutes=30,
        overlap_minutes=15,
    )

    assert begin == "202604201115"
    assert end == "202604211200"


def test_get_incremental_query_range_falls_back_without_last_check(monkeypatch):
    fixed_now = datetime(2026, 4, 21, 12, 0, tzinfo=time_utils.KST)
    monkeypatch.setattr(time_utils, "now_kst", lambda: fixed_now)

    begin, end = time_utils.get_incremental_query_range("", buffer_minutes=30)

    assert begin == "202604211130"
    assert end == "202604211200"
