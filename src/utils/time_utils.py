"""
시간 관련 유틸리티

KST(한국 표준시) 기준 변환, 포맷팅, D-day 계산 등
기존 나라장터_입찰공고 프로젝트에서 검증된 코드 재활용
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

# 한국 표준시 (UTC+9)
KST = timezone(timedelta(hours=9))


def now_kst() -> datetime:
    """현재 KST 시각"""
    return datetime.now(KST)


def format_api_dt(dt: datetime) -> str:
    """API 요청 파라미터 형식: yyyyMMddHHmm"""
    return dt.strftime("%Y%m%d%H%M")


def parse_api_dt(dt_str: str) -> datetime | None:
    """API 응답의 날짜 문자열을 datetime 으로 파싱

    다양한 형식을 지원합니다:
    - '2026/03/11 14:00:00'
    - '2026-03-11 14:00:00'
    - '20260311'
    - '202603111400'
    - '' (빈 문자열)
    """
    if not dt_str or not dt_str.strip():
        return None

    dt_str = dt_str.strip()

    formats = [
        "%Y/%m/%d %H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
        "%Y/%m/%d %H:%M",
        "%Y-%m-%d %H:%M",
        "%Y%m%d%H%M%S",
        "%Y%m%d%H%M",
        "%Y%m%d",
    ]

    for fmt in formats:
        try:
            dt = datetime.strptime(dt_str, fmt)
            return dt.replace(tzinfo=KST)
        except ValueError:
            continue

    return None


def get_query_range(buffer_minutes: int = 60) -> tuple[str, str]:
    """조회 시간 범위를 반환 (시작일시, 종료일시)

    Args:
        buffer_minutes: 조회 범위 여유 시간

    Returns:
        (시작일시, 종료일시) - API 요청 형식 (yyyyMMddHHmm)
    """
    now = now_kst()
    begin = now - timedelta(minutes=buffer_minutes)
    return format_api_dt(begin), format_api_dt(now)


def get_incremental_query_range(
    last_check_iso: str = "",
    buffer_minutes: int = 60,
    overlap_minutes: int = 15,
) -> tuple[str, str]:
    """마지막 성공 실행 시각을 기준으로 조회 시간 범위를 반환합니다."""
    now = now_kst()
    fallback_begin = now - timedelta(minutes=buffer_minutes)

    if not last_check_iso:
        return format_api_dt(fallback_begin), format_api_dt(now)

    try:
        last_check = datetime.fromisoformat(last_check_iso)
    except ValueError:
        return format_api_dt(fallback_begin), format_api_dt(now)

    if last_check.tzinfo is None:
        last_check = last_check.replace(tzinfo=KST)
    else:
        last_check = last_check.astimezone(KST)

    begin = last_check - timedelta(minutes=max(overlap_minutes, 0))
    if begin > now:
        begin = fallback_begin

    return format_api_dt(begin), format_api_dt(now)


def calc_d_day(close_dt_str: str) -> str:
    """마감일까지 남은 일수 계산

    Returns:
        'D-14', 'D-0(오늘)', '마감' 등
    """
    close_dt = parse_api_dt(close_dt_str)
    if not close_dt:
        return ""

    now = now_kst()
    delta = (close_dt.date() - now.date()).days

    if delta < 0:
        return "마감"
    elif delta == 0:
        return "D-0(오늘)"
    else:
        return f"D-{delta}"


def format_display_dt(dt_str: str) -> str:
    """날짜를 사람이 읽기 쉬운 형식으로 변환

    Returns:
        '2026-03-11 14:00' 형식 또는 원본 문자열
    """
    dt = parse_api_dt(dt_str)
    if not dt:
        return dt_str if dt_str else "-"
    return dt.strftime("%Y-%m-%d %H:%M")


def now_iso() -> str:
    """현재 KST 시각의 ISO 형식 문자열"""
    return now_kst().isoformat()
