"""
메시지 포맷터

텔레그램 알림 메시지를 HTML 형식으로 구성합니다.
"""

from __future__ import annotations

from src.core.models import BidNotice
from src.utils.time_utils import calc_d_day, format_display_dt


def format_bid_notice(notice: BidNotice, profile_name: str, matched_keyword: str = "") -> str:
    """입찰공고 알림 메시지 포맷팅"""
    d_day = calc_d_day(notice.bid_clse_dt)
    d_day_text = f" ({d_day})" if d_day else ""
    
    bid_name = _escape_html(notice.bid_ntce_nm)
    if matched_keyword:
        bid_name = _highlight_keyword(bid_name, matched_keyword)

    lines = [
        "🔔 <b>나라장터 신규 입찰공고</b>",
        "━━━━━━━━━━━━━━━━━",
        "",
        f"📋 {bid_name}",
        f"📌 유형: {notice.bid_type.display_name}",
    ]

    if notice.ntce_div_nm:
        lines[-1] += f" | 공고구분: {_escape_html(notice.ntce_div_nm)}"

    lines.append("")
    lines.append(f"🏢 공고기관: {_escape_html(notice.ntce_instt_nm)}")

    if notice.dmnd_instt_nm:
        lines.append(f"🏗️ 수요기관: {_escape_html(notice.dmnd_instt_nm)}")

    if notice.prtcpt_psbl_rgn_nm:
        lines.append(f"📍 참가가능지역: {_escape_html(notice.prtcpt_psbl_rgn_nm)}")

    lines.append(f"💰 추정가격: {notice.price_display}")

    if notice.cntrct_methd_nm:
        lines.append(f"💼 계약방법: {_escape_html(notice.cntrct_methd_nm)}")

    if notice.sucsfbid_methd_nm:
        lines.append(f"🏆 낙찰방법: {_escape_html(notice.sucsfbid_methd_nm)}")

    lines.append("")
    lines.append(f"📅 공고일: {format_display_dt(notice.bid_ntce_dt)}")

    if notice.bid_begin_dt:
        lines.append(f"📅 입찰개시: {format_display_dt(notice.bid_begin_dt)}")

    lines.append(f"⏰ 입찰마감: {format_display_dt(notice.bid_clse_dt)}{d_day_text}")

    if notice.openg_dt:
        lines.append(f"📅 개찰일: {format_display_dt(notice.openg_dt)}")

    if notice.bid_ntce_dtl_url:
        lines.append("")
        lines.append(f'🔗 <a href="{notice.bid_ntce_dtl_url}">상세보기</a>')

    return "\n".join(lines)


def _highlight_keyword(text: str, keyword: str) -> str:
    """텍스트 내의 키워드에 볼드+코드 태그를 입혀 시각적 강조(음영) 효과를 줍니다."""
    if not keyword:
        return text
    
    import re
    # 대소문자 구분 없이 매칭 (HTML 이스케이프된 텍스트 기준이므로 조심)
    # 키워드 자체도 이스케이프해서 검색해야 안전함
    escaped_kw = _escape_html(keyword)
    
    # 정규표현식으로 교체 (대소문자 보존하며 태그 감싸기)
    pattern = re.compile(re.escape(escaped_kw), re.IGNORECASE)
    return pattern.sub(lambda m: f"<b>{m.group(0)}</b>", text)


def format_share_message(notice: BidNotice) -> str:
    """공유용 텍스트 포맷 (강조 없이 깔끔하게)"""
    d_day = calc_d_day(notice.bid_clse_dt)
    d_day_text = f" ({d_day})" if d_day else ""

    lines = [
        "━━━━━━━━━━━━━━━━━",
        "📋 나라장터 입찰공고 공유",
        "",
        f"공고명: {notice.bid_ntce_nm}",
        f"공고기관: {notice.ntce_instt_nm}",
    ]

    if notice.dmnd_instt_nm:
        lines.append(f"수요기관: {notice.dmnd_instt_nm}")

    lines.append(f"추정가격: {notice.price_display}")
    lines.append(f"마감일: {format_display_dt(notice.bid_clse_dt)}{d_day_text}")

    if notice.bid_ntce_dtl_url:
        lines.append(f"상세: {notice.bid_ntce_dtl_url}")

    lines.append("━━━━━━━━━━━━━━━━━")

    return "\n".join(lines)


def format_summary(
    profile_name: str,
    bid_count: int,
    check_time: str,
) -> str:
    """실행 요약 메시지"""
    lines = [
        f"📊 <b>[{_escape_html(profile_name)}] 조회 결과</b> ({_escape_html(check_time)})",
    ]

    if bid_count > 0:
        lines.append(f"• 신규 입찰공고: <b>{bid_count}건</b>")
    else:
        lines.append("• 신규 공고 없음")

    return "\n".join(lines)


def _escape_html(text: str) -> str:
    """HTML 특수문자 이스케이프"""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )
