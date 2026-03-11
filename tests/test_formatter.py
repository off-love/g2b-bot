"""
포맷터 유닛 테스트
"""

from src.core.formatter import format_bid_notice, format_prebid_notice, format_summary
from src.core.models import BidNotice, BidType, PreBidNotice


def test_bid_notice_format():
    """입찰공고 알림 메시지 포맷 테스트"""
    notice = BidNotice(
        bid_ntce_no="20260311001234",
        bid_ntce_ord="00",
        bid_ntce_nm="지적측량 업무 위탁용역",
        ntce_instt_nm="한국국토정보공사",
        dmnd_instt_nm="서울시청",
        presmpt_prce=150_000_000,
        bid_ntce_dt="2026/03/11 14:00:00",
        bid_clse_dt="2026/03/25 10:00:00",
        openg_dt="2026/03/25 11:00:00",
        bid_ntce_dtl_url="https://example.com",
        prtcpt_psbl_rgn_nm="서울",
        bid_type=BidType.SERVICE,
        cntrct_methd_nm="일반경쟁",
    )
    result = format_bid_notice(notice, "지적측량 용역")

    assert "지적측량 업무 위탁용역" in result
    assert "한국국토정보공사" in result
    assert "서울시청" in result
    assert "150,000,000원" in result
    assert "용역" in result
    assert "상세보기" in result


def test_prebid_format():
    """사전규격 알림 메시지 포맷 테스트"""
    notice = PreBidNotice(
        prcure_no="PS001",
        prcure_nm="지적측량 사전규격",
        ntce_instt_nm="한국국토정보공사",
        rcpt_dt="2026/03/11 00:00:00",
        opnn_reg_clse_dt="2026/03/18 00:00:00",
        dtl_url="https://example.com",
        bid_type=BidType.SERVICE,
    )
    result = format_prebid_notice(notice, "지적측량 용역")

    assert "사전규격" in result
    assert "지적측량 사전규격" in result
    assert "한국국토정보공사" in result


def test_summary_format():
    """요약 메시지 포맷 테스트"""
    result = format_summary("지적측량 용역", 3, 1, "14:30")
    assert "3건" in result
    assert "1건" in result
    assert "지적측량 용역" in result


def test_summary_no_results():
    """결과 없을 때 요약"""
    result = format_summary("테스트", 0, 0, "14:30")
    assert "신규 공고 없음" in result


def test_html_escape():
    """HTML 특수문자 이스케이프"""
    notice = BidNotice(
        bid_ntce_no="T001",
        bid_ntce_ord="00",
        bid_ntce_nm="<script>alert('xss')</script>",
        ntce_instt_nm="기관&회사",
        dmnd_instt_nm="",
        presmpt_prce=0,
        bid_ntce_dt="",
        bid_clse_dt="",
        openg_dt="",
        bid_ntce_dtl_url="",
        prtcpt_psbl_rgn_nm="",
        bid_type=BidType.SERVICE,
    )
    result = format_bid_notice(notice, "테스트")
    assert "<script>" not in result
    assert "&lt;script&gt;" in result
    assert "&amp;회사" in result
