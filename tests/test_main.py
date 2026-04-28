"""
메인 실행 로직 유닛 테스트
"""

import pytest

from src import main as main_module
from src.core.models import BidNotice, BidType, KeywordConfig
from src.storage.state_manager import is_notified


def _make_keyword() -> KeywordConfig:
    return KeywordConfig(
        original="지적측량",
        keyword_hash="abc123def4567890",
        exclude=[],
        bid_types=["service"],
    )


def _make_bid_notice() -> BidNotice:
    return BidNotice(
        bid_ntce_no="R26BK01475175",
        bid_ntce_ord="000",
        bid_ntce_nm="토지정보 통합관리를 위한 지적측량포털 고도화 사업",
        ntce_instt_nm="서울특별시",
        dmnd_instt_nm="서울특별시",
        presmpt_prce=434_274_546,
        bid_ntce_dt="2026-04-20 11:17:19",
        bid_clse_dt="2026-05-07 16:00:00",
        openg_dt="2026-05-07 17:00:00",
        bid_ntce_dtl_url="https://example.com/bid",
        prtcpt_psbl_rgn_nm="",
        bid_type=BidType.SERVICE,
    )


def test_process_bid_notices_marks_only_successes(monkeypatch):
    kw = _make_keyword()
    notice = _make_bid_notice()
    state = {"notified_bids": {}, "notified_prebids": {}}
    captured = {}

    def fake_fetch(**kwargs):
        captured["inqry_bgn_dt"] = kwargs["inqry_bgn_dt"]
        captured["inqry_end_dt"] = kwargs["inqry_end_dt"]
        return [notice]

    monkeypatch.setattr(main_module, "fetch_bid_notices", fake_fetch)
    monkeypatch.setattr(
        main_module,
        "filter_bid_notices",
        lambda notices, keyword, exclude_keywords: list(notices),
    )
    monkeypatch.setattr(
        main_module,
        "format_bid_payload",
        lambda notice, keyword: {"data": {"id": notice.unique_key}},
    )
    monkeypatch.setattr(main_module, "send_bid_notification", lambda topic, payload: True)

    result = main_module.process_bid_notices(
        kw,
        state,
        "202604201100",
        "202604201200",
    )

    topic = kw.get_topic("bid", BidType.SERVICE)
    assert result.sent_count == 1
    assert result.had_failures is False
    assert captured["inqry_bgn_dt"] == "202604201100"
    assert captured["inqry_end_dt"] == "202604201200"
    assert is_notified(
        state,
        notice.unique_key,
        "bid",
        topic=topic,
        keyword=kw.original,
    ) is True


def test_process_bid_notices_keeps_failed_notice_retryable(monkeypatch):
    kw = _make_keyword()
    notice = _make_bid_notice()
    state = {"notified_bids": {}, "notified_prebids": {}}

    monkeypatch.setattr(main_module, "fetch_bid_notices", lambda **kwargs: [notice])
    monkeypatch.setattr(
        main_module,
        "filter_bid_notices",
        lambda notices, keyword, exclude_keywords: list(notices),
    )
    monkeypatch.setattr(
        main_module,
        "format_bid_payload",
        lambda notice, keyword: {"data": {"id": notice.unique_key}},
    )
    monkeypatch.setattr(main_module, "send_bid_notification", lambda topic, payload: False)

    result = main_module.process_bid_notices(
        kw,
        state,
        "202604201100",
        "202604201200",
    )

    topic = kw.get_topic("bid", BidType.SERVICE)
    assert result.sent_count == 0
    assert result.had_failures is True
    assert is_notified(
        state,
        notice.unique_key,
        "bid",
        topic=topic,
        keyword=kw.original,
    ) is False


def test_main_keeps_last_check_when_delivery_failed(monkeypatch):
    kw = _make_keyword()
    state = {
        "last_check": "2026-04-20T10:00:00+09:00",
        "notified_bids": {},
        "notified_prebids": {},
    }
    update_called = False
    save_called = False

    monkeypatch.setattr(main_module, "validate_runtime_config", lambda: None)
    monkeypatch.setattr(main_module, "load_state", lambda: state)
    monkeypatch.setattr(main_module, "cleanup_old_records", lambda current_state: 0)
    monkeypatch.setattr(main_module, "load_keywords", lambda: [kw])
    monkeypatch.setattr(
        main_module,
        "process_bid_notices",
        lambda kw, current_state, query_begin, query_end: main_module.ProcessResult(
            sent_count=0,
            had_failures=True,
        ),
    )
    monkeypatch.setattr(
        main_module,
        "process_prebid_notices",
        lambda kw, current_state, query_begin, query_end: main_module.ProcessResult(),
    )

    def fake_update_last_check(current_state):
        nonlocal update_called
        update_called = True
        current_state["last_check"] = "SHOULD_NOT_BE_SET"

    def fake_save_state(current_state):
        nonlocal save_called
        save_called = True

    monkeypatch.setattr(main_module, "update_last_check", fake_update_last_check)
    monkeypatch.setattr(main_module, "save_state", fake_save_state)

    with pytest.raises(RuntimeError):
        main_module.main()

    assert update_called is False
    assert save_called is True
    assert state["last_check"] == "2026-04-20T10:00:00+09:00"
