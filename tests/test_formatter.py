"""
FCM payload formatter tests
"""

from src.core.formatter import format_bid_payload, format_prebid_payload
from src.core.models import BidNotice, BidType, PreBidNotice


def test_format_bid_payload_includes_calendar_dates():
    notice = BidNotice(
        bid_ntce_no="R26BK01475175",
        bid_ntce_ord="000",
        bid_ntce_nm="지적측량 용역",
        ntce_instt_nm="서울특별시",
        dmnd_instt_nm="서울특별시",
        presmpt_prce=434_274_546,
        bid_ntce_dt="2026-04-20 11:17:19",
        bid_clse_dt="2026-05-07 16:00:00",
        openg_dt="2026-05-07 17:00:00",
        bid_ntce_dtl_url="https://example.com/bid",
        prtcpt_psbl_rgn_nm="전국",
        bid_type=BidType.SERVICE,
        ntce_div_nm="일반",
        bid_methd_nm="전자입찰",
        cntrct_methd_nm="제한경쟁",
        sucsfbid_methd_nm="적격심사",
        bid_begin_dt="2026-05-01 10:00:00",
    )

    payload = format_bid_payload(notice, "측량")["data"]

    assert payload["bidBeginDate"] == "2026-05-01 10:00:00"
    assert payload["bidBeginDateISO"] == "2026-05-01T10:00:00+09:00"
    assert payload["closingDateISO"] == "2026-05-07T16:00:00+09:00"
    assert payload["openingDateISO"] == "2026-05-07T17:00:00+09:00"
    assert payload["noticeDivision"] == "일반"
    assert payload["bidMethod"] == "전자입찰"
    assert payload["successfulBidMethod"] == "적격심사"


def test_format_bid_payload_includes_ios_history_required_fields():
    notice = BidNotice(
        bid_ntce_no="R26BK01510475",
        bid_ntce_ord="000",
        bid_ntce_nm="지적측량 용역",
        ntce_instt_nm="서울특별시",
        dmnd_instt_nm="서울특별시",
        presmpt_prce=434_274_546,
        bid_ntce_dt="2026-04-20 11:17:19",
        bid_clse_dt="2026-05-07 16:00:00",
        openg_dt="2026-05-07 17:00:00",
        bid_ntce_dtl_url="https://example.com/bid",
        prtcpt_psbl_rgn_nm="전국",
        bid_type=BidType.SERVICE,
    )

    payload = format_bid_payload(notice, "측량")
    data = payload["data"]

    assert payload["notification"]["title"]
    assert payload["notification"]["body"]
    assert data["noticeId"] == "R26BK01510475-000"
    assert data["title"] == "지적측량 용역"
    assert data["agency"] == "서울특별시"
    assert data["demandAgency"] == "서울특별시"
    assert data["price"] == "434274546"
    assert data["detailUrl"] == "https://example.com/bid"
    assert data["bidType"] == "service"
    assert data["keyword"] == "측량"
    assert data["type"] == "bid"
    assert data["closingDateISO"] == "2026-05-07T16:00:00+09:00"
    assert data["noticeDateISO"] == "2026-04-20T11:17:19+09:00"
    assert float(data["receivedTimestamp"]) > 0


def test_format_prebid_payload_includes_iso_dates_and_procure_fields():
    notice = PreBidNotice(
        prcure_no="P20260420001",
        prcure_nm="지적측량 사전규격",
        ntce_instt_nm="서울특별시",
        rcpt_dt="2026-04-20 11:17:19",
        opnn_reg_clse_dt="2026-05-07 16:00:00",
        asign_bdgt_amt=434_274_546,
        dtl_url="https://example.com/prebid",
        bid_type=BidType.SERVICE,
        prcure_div="용역",
        prcure_way="총액",
    )

    payload = format_prebid_payload(notice, "측량")["data"]

    assert payload["noticeDateISO"] == "2026-04-20T11:17:19+09:00"
    assert payload["closingDateISO"] == "2026-05-07T16:00:00+09:00"
    assert payload["procureDivision"] == "용역"
    assert payload["procureWay"] == "총액"


def test_format_prebid_payload_includes_ios_history_required_fields():
    notice = PreBidNotice(
        prcure_no="R26BD00224791",
        prcure_nm="지적측량 사전규격",
        ntce_instt_nm="서울특별시",
        rcpt_dt="2026-04-20 11:17:19",
        opnn_reg_clse_dt="2026-05-07 16:00:00",
        asign_bdgt_amt=120_000_000,
        dtl_url="https://example.com/prebid",
        bid_type=BidType.SERVICE,
        prcure_div="용역",
        prcure_way="총액",
    )

    payload = format_prebid_payload(notice, "측량")
    data = payload["data"]

    assert payload["notification"]["title"]
    assert payload["notification"]["body"]
    assert data["noticeId"] == "R26BD00224791"
    assert data["title"] == "지적측량 사전규격"
    assert data["agency"] == "서울특별시"
    assert data["price"] == "120000000"
    assert data["detailUrl"] == "https://example.com/prebid"
    assert data["bidType"] == "service"
    assert data["keyword"] == "측량"
    assert data["type"] == "prebid"
    assert data["closingDateISO"] == "2026-05-07T16:00:00+09:00"
    assert data["noticeDateISO"] == "2026-04-20T11:17:19+09:00"
    assert float(data["receivedTimestamp"]) > 0
