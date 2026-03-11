"""
메시지 포맷터

텔레그램 알림 메시지를 Markdown 형식으로 구성합니다.
"""

from __future__ import annotations

from src.core.models import BidNotice, PreBidNotice
from src.utils.time_utils import calc_d_day, format_display_dt


def format_bid_notice(notice: BidNotice, profile_name: str) -> str:
    """입찰공고 알림 메시지 포맷팅 (Telegram MarkdownV2 대신 HTML 사용)"""
    d_day = calc_d_day(notice.bid_clse_dt)
    d_day_text = f" ({d_day})" if d_day else ""

    lines = [
        "🔔 <b>나라장터 신규 입찰공고</b>",
        "━━━━━━━━━━━━━━━━━",
        "",
        f"📋 <b>{_escape_html(notice.bid_ntce_nm)}</b>",
        f"🏷️ 프로필: {_escape_html(profile_name)}",
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


def format_prebid_notice(notice: PreBidNotice, profile_name: str) -> str:
    """사전규격공개 알림 메시지 포맷팅"""
    lines = [
        "📢 <b>[사전규격] 신규 공개</b>",
        "━━━━━━━━━━━━━━━━━",
        "",
        f"📋 <b>{_escape_html(notice.prcure_nm)}</b>",
        f"🏷️ 프로필: {_escape_html(profile_name)}",
        f"📌 유형: {notice.bid_type.display_name}",
        "",
        f"🏢 공고기관: {_escape_html(notice.ntce_instt_nm)}",
        f"📅 공개일: {format_display_dt(notice.rcpt_dt)}",
        f"📝 의견등록마감: {format_display_dt(notice.opnn_reg_clse_dt)}",
        "",
        "⚠️ 사전규격 단계입니다. 추후 입찰공고가 게시됩니다.",
    ]

    if notice.dtl_url:
        lines.append("")
        lines.append(f'🔗 <a href="{notice.dtl_url}">상세보기</a>')

    return "\n".join(lines)


def format_share_message(notice: BidNotice) -> str:
    """공유용 텍스트 포맷"""
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
    prebid_count: int,
    check_time: str,
) -> str:
    """실행 요약 메시지"""
    lines = [
        f"📊 <b>나라장터 조회 결과</b> ({_escape_html(check_time)})",
        f"🏷️ 프로필: {_escape_html(profile_name)}",
    ]

    if bid_count > 0:
        lines.append(f"• 신규 입찰공고: <b>{bid_count}건</b>")
    if prebid_count > 0:
        lines.append(f"• 신규 사전규격: <b>{prebid_count}건</b>")

    if bid_count == 0 and prebid_count == 0:
        lines.append("• 신규 공고 없음")

    return "\n".join(lines)


def _escape_html(text: str) -> str:
    """HTML 특수문자 이스케이프"""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )
