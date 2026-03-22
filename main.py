"""
메인 실행 스크립트

GitHub Actions cron 에 의해 30분마다 실행됩니다.
프로필별로 입찰공고 + 사전규격을 조회하고, 필터링 후 텔레그램으로 알림을 보냅니다.
"""

from __future__ import annotations

import argparse
import logging
import sys
from typing import Any

from src.api.bid_client import fetch_bid_notices
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


def process_profile(profile: AlertProfile, state: dict, settings: dict, mode: str) -> tuple[int, int]:
    """단일 프로필을 처리합니다.

    Args:
        profile: 알림 프로필
        state: 상태 데이터
        settings: 전역 설정
        mode: 실행 모드 (bid 또는 prebid)

    Returns:
        (입찰공고 알림 수, 사전규격 알림 수)
    """
    logger.info("━━━ 프로필 처리: %s (모드: %s) ━━━", profile.name, mode)

    bid_messages: list[Any] = []
    prebid_messages: list[Any] = []
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

    def fetch_all_prebids():
        messages = []
        if not profile.include_prebid: return []
        seen_keys = set()
        for bid_type in profile.bid_types:
            keywords = profile.keywords.or_keywords or [""]
            for kw in keywords:
                raw_prebids = fetch_prebid_notices(
                    bid_type=bid_type,
                    keyword=kw,
                    buffer_hours=buffer_hours,
                    max_results=max_results,
                )
                filtered = filter_prebid_notices(raw_prebids, profile)
                for prebid in filtered:
                    if prebid.unique_key in seen_keys: continue
                    seen_keys.add(prebid.unique_key)
                    if is_notified(state, prebid.unique_key, "prebid"): continue
                    msg = format_prebid_notice(prebid, profile.name)
                    messages.append({"text": msg})
                    mark_notified(state, prebid.unique_key, profile.name, "prebid")
        return messages

    if mode == "bid":
        bid_messages = fetch_all_bids()
    elif mode == "prebid":
        prebid_messages = fetch_all_prebids()

    # ── 3. 텔레그램 발송 ──
    all_messages = bid_messages + prebid_messages

    if all_messages:
        logger.info(
            "알림 발송: 입찰 %d건, 사전규격 %d건",
            len(bid_messages), len(prebid_messages),
        )
        sent = send_bid_notifications(all_messages, mode=mode)
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
        send_message(summary, mode=mode)

    return len(bid_messages), len(prebid_messages)


def main() -> None:
    """메인 실행"""
    parser = argparse.ArgumentParser(description="나라장터 알림 봇 스크립트")
    parser.add_argument("--mode", type=str, choices=["bid", "prebid"], default="bid", help="스크립트 실행 모드 (bid 또는 prebid)")
    args = parser.parse_args()
    
    mode = args.mode
    
    logger.info("=" * 50)
    logger.info("나라장터 알림 서비스 시작 (모드: %s)", mode.upper())
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
                bid_count, prebid_count = process_profile(profile, state, settings, mode)
                total_bids += bid_count
                total_prebids += prebid_count
            except Exception as e:
                logger.error("프로필 '%s' 처리 오류: %s", profile.name, e, exc_info=True)
                # 오류 알림
                try:
                    success = send_message(
                        f"⚠️ 프로필 '{profile.name}' 처리 중 오류 발생 (모드: {mode}): {e}", mode=mode
                    )
                    # 사전규격 봇으로 전송 실패 시 입찰 봇으로 폴백 알림 (chat_id 누락 등)
                    if not success and mode == "prebid":
                        send_message(
                            f"🚨 [사전규격 봇 오류] 사전규격 알림 처리에 실패했습니다. 봇 토큰이나 환경변수(Chat ID)를 확인해주세요: {e}", mode="bid"
                        )
                except Exception:
                    # send_message 내에서 에러 발생 시 (ValueError 등)
                    if mode == "prebid":
                        try:
                            send_message(
                                f"🚨 [사전규격 봇 오류] 사전규격 봇 설정에 문제가 있습니다 (토큰/채팅ID 누락 등). 설정(Secrets)을 다시 확인해주세요! ({e})", mode="bid"
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
            send_message(f"🚨 나라장터 알림 서비스 오류 (모드: {mode}): {e}", mode=mode)
        except Exception:
            pass
        sys.exit(1)


if __name__ == "__main__":
    main()
