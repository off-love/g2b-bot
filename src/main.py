"""
메인 실행 스크립트

GitHub Actions cron 에 의해 30분마다 실행됩니다.
프로필별로 입찰공고를 조회하고, 필터링 후 텔레그램으로 알림을 보냅니다.
"""

from __future__ import annotations

import logging
import os
import sys
from typing import Any

from src.api.bid_client import fetch_bid_notices
from src.core.filter import filter_bid_notices
from src.core.formatter import (
    format_bid_notice,
    format_summary,
)
from src.core.models import AlertProfile
from src.storage.profile_manager import load_profiles
from src.storage.state_manager import (
    cleanup_old_records,
    is_notified,
    load_state,
    mark_notified,
    save_state,
    update_last_check,
)
from src.storage.admin_manager import get_all_admins
from src.storage.subscriber_manager import load_subscribers, remove_subscriber
from src.telegram_bot import (
    send_message,
    broadcast_message,
    broadcast_notifications,
)
from src.utils.time_utils import now_kst

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def process_profile(profile: AlertProfile, state: dict, settings: dict) -> int:
    """단일 프로필을 처리합니다.

    Args:
        profile: 알림 프로필
        state: 상태 데이터
        settings: 전역 설정

    Returns:
        입찰공고 알림 수
    """
    logger.info("━━━ 프로필 처리: %s ━━━", profile.name)

    bid_messages: list[Any] = []
    buffer_hours = settings.get("query_buffer_hours", 1)
    max_results = settings.get("max_results_per_page", 999)

    def fetch_all_bids():
        messages = []
        seen_keys = set()
        for bid_type in profile.bid_types:
            dmnd_cd = profile.demand_agencies.by_code[0] if profile.demand_agencies.by_code else ""
            keywords = profile.keywords.or_keywords or [""]
            for kw in keywords:
                raw_notices = fetch_bid_notices(
                    bid_type=bid_type,
                    keyword=kw,
                    dmnd_instt_cd=dmnd_cd,
                    buffer_hours=buffer_hours,
                    max_results=max_results,
                )
                filtered = filter_bid_notices(raw_notices, profile)
                for notice in filtered:
                    if notice.unique_key in seen_keys: continue
                    seen_keys.add(notice.unique_key)
                    if is_notified(state, notice.unique_key, "bid"): continue
                    msg = format_bid_notice(notice, profile.name, matched_keyword=kw)
                    messages.append({"text": msg})
                    mark_notified(state, notice.unique_key, profile.name, "bid")
        return messages

    bid_messages = fetch_all_bids()

    # ── 텔레그램 발송 ──
    if bid_messages:
        logger.info("알림 발송: 입찰 %d건", len(bid_messages))

        # 전송 대상 수집: 슈퍼관리자 + 일반관리자 + 구독자 (중복 제거)
        super_admin = os.environ.get("SUPER_ADMIN_CHAT_ID", "")
        admin_ids = get_all_admins()
        subscribers = load_subscribers(mode="bid")

        target_chat_ids = set()
        if super_admin:
            target_chat_ids.add(str(super_admin))
        for aid in admin_ids:
            target_chat_ids.add(str(aid))
        for sub_id in subscribers:
            target_chat_ids.add(str(sub_id))

        invalid_ids = broadcast_notifications(bid_messages, target_chat_ids=target_chat_ids, mode="bid")

        for inv_id in invalid_ids:
            if inv_id in subscribers:
                remove_subscriber(inv_id, mode="bid")
                logger.info("차단/탈퇴한 구독자 자동 삭제 완료: %s", inv_id)

        logger.info("발송 완료: 총 %d명 대상 (유효하지 않은 사용자 %d명 제외)", len(target_chat_ids), len(invalid_ids))

        # 요약 메시지
        summary = format_summary(
            profile_name=profile.name,
            bid_count=len(bid_messages),
            check_time=now_kst().strftime("%H:%M"),
        )
        filtered_targets = target_chat_ids - set(invalid_ids)
        if filtered_targets:
            broadcast_message(summary, target_chat_ids=filtered_targets, mode="bid")
    else:
        logger.info("신규 알림 없음")

    return len(bid_messages)


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

        # 프로필별 처리
        for profile in profiles:
            try:
                bid_count = process_profile(profile, state, settings)
                total_bids += bid_count
            except Exception as e:
                logger.error("프로필 '%s' 처리 오류: %s", profile.name, e, exc_info=True)
                try:
                    send_message(
                        f"⚠️ 프로필 '{profile.name}' 처리 중 오류 발생: {e}", mode="bid"
                    )
                except Exception:
                    pass

        # 상태 저장
        update_last_check(state)
        save_state(state)

        logger.info("=" * 50)
        logger.info("전체 완료: 입찰공고 %d건 알림", total_bids)
        logger.info("=" * 50)

    except Exception as e:
        logger.critical("치명적 오류: %s", e, exc_info=True)
        try:
            send_message(f"🚨 나라장터 알림 서비스 오류: {e}", mode="bid")
        except Exception:
            pass
        sys.exit(1)


if __name__ == "__main__":
    main()
