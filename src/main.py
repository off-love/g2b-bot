"""
메인 실행 스크립트

GitHub Actions cron 에 의해 30분마다 실행됩니다.
프로필별로 입찰공고 + 사전규격을 조회하고, 필터링 후 텔레그램으로 알림을 보냅니다.
"""

from __future__ import annotations

import logging
import sys

from src.api.bid_client import fetch_bid_notices_multi_keywords
from src.api.prebid_client import fetch_prebid_notices
from src.core.filter import filter_bid_notices, filter_prebid_notices
from src.core.formatter import (
    format_bid_notice,
    format_prebid_notice,
    format_summary,
)
from src.core.models import AlertProfile, BidType
from src.storage.profile_manager import load_profiles
from src.storage.state_manager import (
    cleanup_old_records,
    is_notified,
    load_state,
    mark_notified,
    save_state,
    update_last_check,
)
from src.telegram_bot import send_bid_notifications, send_message
from src.utils.time_utils import now_kst

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def process_profile(profile: AlertProfile, state: dict, settings: dict) -> tuple[int, int]:
    """단일 프로필을 처리합니다.

    Args:
        profile: 알림 프로필
        state: 상태 데이터
        settings: 전역 설정

    Returns:
        (입찰공고 알림 수, 사전규격 알림 수)
    """
    logger.info("━━━ 프로필 처리: %s ━━━", profile.name)

    bid_messages: list[str] = []
    prebid_messages: list[str] = []
    buffer_hours = settings.get("query_buffer_hours", 1)
    max_results = settings.get("max_results_per_page", 999)

    # ── 1. 입찰공고 조회 & 필터링 ──
    for bid_type in profile.bid_types:
        logger.info("입찰공고 조회: %s / %s", profile.name, bid_type.display_name)

        # API 레벨: 수요기관 코드 (첫 번째만 사용)
        dmnd_cd = ""
        if profile.demand_agencies.by_code:
            dmnd_cd = profile.demand_agencies.by_code[0]

        # API 호출 (OR 키워드 개별 호출 + 합침)
        raw_notices = fetch_bid_notices_multi_keywords(
            bid_type=bid_type,
            keywords=profile.keywords.or_keywords,
            dmnd_instt_cd=dmnd_cd,
            buffer_hours=buffer_hours,  # 원래 설정으로 복구 (기본 1시간)
            max_results=max_results,
        )

        # 코드 레벨 필터링
        filtered = filter_bid_notices(raw_notices, profile)

        # 중복 체크 & 메시지 생성
        for notice in filtered:
            if is_notified(state, notice.unique_key, "bid"):
                logger.debug("이미 알림 완료: %s", notice.unique_key)
                continue

            msg = format_bid_notice(notice, profile.name)
            bid_messages.append(msg)
            mark_notified(state, notice.unique_key, profile.name, "bid")

    # ── 2. 사전규격 조회 & 필터링 ──
    if profile.include_prebid:
        for bid_type in profile.bid_types:
            logger.info("사전규격 조회: %s / %s", profile.name, bid_type.display_name)

            raw_prebids = fetch_prebid_notices(
                bid_type=bid_type,
                buffer_hours=buffer_hours,
                max_results=max_results,
            )

            filtered_prebids = filter_prebid_notices(raw_prebids, profile)

            for prebid in filtered_prebids:
                if is_notified(state, prebid.unique_key, "prebid"):
                    continue

                msg = format_prebid_notice(prebid, profile.name)
                prebid_messages.append(msg)
                mark_notified(state, prebid.unique_key, profile.name, "prebid")

    # ── 3. 텔레그램 발송 ──
    all_messages = bid_messages + prebid_messages

    if all_messages:
        logger.info(
            "알림 발송: 입찰 %d건, 사전규격 %d건",
            len(bid_messages), len(prebid_messages),
        )
        sent = send_bid_notifications(all_messages)
        logger.info("발송 완료: %d/%d건", sent, len(all_messages))
    else:
        logger.info("신규 알림 없음")

    # 요약 메시지 (알림이 있을 때만)
    if all_messages:
        summary = format_summary(
            profile_name=profile.name,
            bid_count=len(bid_messages),
            prebid_count=len(prebid_messages),
            check_time=now_kst().strftime("%H:%M"),
        )
        send_message(summary)

    return len(bid_messages), len(prebid_messages)


def main() -> None:
    """메인 실행"""
    logger.info("=" * 50)
    logger.info("나라장터 입찰공고 알림 서비스 시작")
    logger.info("=" * 50)

    try:
        # 프로필 로드
        profiles, settings_obj = load_profiles()
        settings = {
            "query_buffer_hours": settings_obj.query_buffer_hours,
            "max_results_per_page": settings_obj.max_results_per_page,
        }

        if not profiles:
            logger.warning("활성 프로필이 없습니다. profiles.yaml을 확인하세요.")
            return

        logger.info("활성 프로필 %d개 로드 완료", len(profiles))

        # 상태 로드
        state = load_state()

        # 오래된 기록 정리
        cleanup_old_records(state)

        total_bids = 0
        total_prebids = 0

        # 프로필별 처리
        for profile in profiles:
            try:
                bid_count, prebid_count = process_profile(profile, state, settings)
                total_bids += bid_count
                total_prebids += prebid_count
            except Exception as e:
                logger.error("프로필 '%s' 처리 오류: %s", profile.name, e, exc_info=True)
                # 오류 알림
                try:
                    send_message(
                        f"⚠️ 프로필 '{profile.name}' 처리 중 오류 발생: {e}"
                    )
                except Exception:
                    pass

        # 상태 저장
        update_last_check(state)
        save_state(state)

        logger.info("=" * 50)
        logger.info(
            "전체 완료: 입찰공고 %d건, 사전규격 %d건 알림",
            total_bids, total_prebids,
        )
        logger.info("=" * 50)

    except Exception as e:
        logger.critical("치명적 오류: %s", e, exc_info=True)
        try:
            send_message(f"🚨 나라장터 알림 서비스 오류: {e}")
        except Exception:
            pass
        sys.exit(1)


if __name__ == "__main__":
    main()
