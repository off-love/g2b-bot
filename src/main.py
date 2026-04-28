"""
입찰톡 메인 실행 스크립트

GitHub Actions에서 10분 간격으로 실행됩니다.

실행 흐름:
1. state.json 로드 + 오래된 기록 정리
2. keywords.json 로드
3. 마지막 성공 실행 시각 기준 조회 범위 계산
4. 키워드별 × 업종별 API 호출
5. 2단계 필터링 (제외 키워드 + 중복 체크)
6. 신규 공고 → FCM Topic 발송 (업무구분별 토픽)
7. 성공한 공고만 state.json 업데이트
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import logging
import os
import sys
from pathlib import Path

from src.api.bid_client import fetch_bid_notices
from src.api.prebid_client import fetch_prebid_notices
from src.core.filter import filter_bid_notices, filter_prebid_notices
from src.core.formatter import format_bid_payload, format_prebid_payload
from src.core.models import KeywordConfig
from src.core.topic_hasher import keyword_hash
from src.fcm.sender import send_bid_notification
from src.storage.state_manager import (
    cleanup_old_records,
    is_notified,
    load_state,
    mark_notified,
    save_state,
    update_last_check,
)
from src.utils.time_utils import get_incremental_query_range

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

KEYWORDS_PATH = Path(__file__).parent.parent / "data" / "keywords.json"
FIREBASE_CREDENTIALS_PATH = Path(__file__).parent.parent / "firebase-credentials.json"
QUERY_BUFFER_MINUTES = 30
QUERY_OVERLAP_MINUTES = 15


@dataclass
class ProcessResult:
    """키워드 처리 결과"""

    sent_count: int = 0
    had_failures: bool = False


def validate_runtime_config() -> None:
    """운영 실행에 필요한 필수 설정을 검증합니다."""
    missing: list[str] = []

    if not os.environ.get("G2B_API_KEY", "").strip():
        missing.append("G2B_API_KEY")

    has_firebase_env = bool(os.environ.get("FIREBASE_CREDENTIALS", "").strip())
    has_firebase_file = FIREBASE_CREDENTIALS_PATH.exists()
    if not has_firebase_env and not has_firebase_file:
        missing.append("FIREBASE_CREDENTIALS or server/firebase-credentials.json")

    if missing:
        raise RuntimeError(
            "필수 런타임 설정이 누락되었습니다: " + ", ".join(missing)
        )


def load_keywords() -> list[KeywordConfig]:
    """keywords.json에서 키워드 목록을 로드합니다."""
    if not KEYWORDS_PATH.exists():
        logger.error("keywords.json 파일이 없습니다: %s", KEYWORDS_PATH)
        return []

    with open(KEYWORDS_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    keywords = []
    for kw_data in data.get("keywords", []):
        kw_hash = kw_data.get("keyword_hash", "")
        if not kw_hash:
            kw_hash = keyword_hash(kw_data["original"])

        kw = KeywordConfig(
            original=kw_data["original"],
            keyword_hash=kw_hash,
            exclude=kw_data.get("exclude", []),
            bid_types=kw_data.get("bid_types", ["service", "goods", "construction"]),
        )
        keywords.append(kw)

    global_exclude = data.get("global_exclude", [])
    for kw in keywords:
        kw.exclude = list(set(kw.exclude + global_exclude))

    logger.info("키워드 %d개 로드 완료", len(keywords))
    return keywords


def process_bid_notices(
    kw: KeywordConfig,
    state: dict,
    query_begin: str,
    query_end: str,
) -> ProcessResult:
    """입찰공고 수집 + 필터링 + FCM 발송"""
    result = ProcessResult()

    for bid_type in kw.bid_type_enums:
        notices = fetch_bid_notices(
            bid_type=bid_type,
            keyword=kw.original,
            buffer_minutes=QUERY_BUFFER_MINUTES,
            inqry_bgn_dt=query_begin,
            inqry_end_dt=query_end,
        )

        if not notices:
            continue

        filtered = filter_bid_notices(
            notices,
            keyword=kw.original,
            exclude_keywords=kw.exclude,
        )

        topic = kw.get_topic("bid", bid_type)

        for notice in filtered:
            if is_notified(
                state,
                notice.unique_key,
                "bid",
                topic=topic,
                keyword=kw.original,
            ):
                continue

            payload = format_bid_payload(notice, kw.original)
            success = send_bid_notification(topic, payload)

            if success:
                mark_notified(
                    state,
                    notice.unique_key,
                    kw.original,
                    "bid",
                    topic=topic,
                )
                result.sent_count += 1
                logger.info(
                    "📱 입찰 알림 발송: [%s/%s] %s → %s",
                    kw.original,
                    bid_type.display_name,
                    notice.bid_ntce_nm,
                    topic,
                )
            else:
                result.had_failures = True
                logger.warning(
                    "❌ 입찰 알림 실패: [%s/%s] %s",
                    kw.original,
                    bid_type.display_name,
                    notice.bid_ntce_nm,
                )

    return result


def process_prebid_notices(
    kw: KeywordConfig,
    state: dict,
    query_begin: str,
    query_end: str,
) -> ProcessResult:
    """사전규격 수집 + 필터링 + FCM 발송"""
    result = ProcessResult()

    for bid_type in kw.bid_type_enums:
        notices = fetch_prebid_notices(
            bid_type=bid_type,
            keyword=kw.original,
            buffer_minutes=QUERY_BUFFER_MINUTES,
            inqry_bgn_dt=query_begin,
            inqry_end_dt=query_end,
        )

        if not notices:
            continue

        filtered = filter_prebid_notices(
            notices,
            keyword=kw.original,
            exclude_keywords=kw.exclude,
        )

        topic = kw.get_topic("pre", bid_type)

        for notice in filtered:
            if is_notified(
                state,
                notice.unique_key,
                "prebid",
                topic=topic,
                keyword=kw.original,
            ):
                continue

            payload = format_prebid_payload(notice, kw.original)
            success = send_bid_notification(topic, payload)

            if success:
                mark_notified(
                    state,
                    notice.unique_key,
                    kw.original,
                    "prebid",
                    topic=topic,
                )
                result.sent_count += 1
                logger.info(
                    "📱 사전규격 알림 발송: [%s/%s] %s → %s",
                    kw.original,
                    bid_type.display_name,
                    notice.prcure_nm,
                    topic,
                )
            else:
                result.had_failures = True
                logger.warning(
                    "❌ 사전규격 알림 실패: [%s/%s] %s",
                    kw.original,
                    bid_type.display_name,
                    notice.prcure_nm,
                )

    return result


def main() -> None:
    """메인 실행 함수"""
    logger.info("=" * 60)
    logger.info("🚀 입찰톡 공고 체크 시작")
    logger.info("=" * 60)

    validate_runtime_config()

    state = load_state()
    removed = cleanup_old_records(state)
    if removed > 0:
        logger.info("오래된 기록 %d건 정리", removed)

    query_begin, query_end = get_incremental_query_range(
        state.get("last_check", ""),
        buffer_minutes=QUERY_BUFFER_MINUTES,
        overlap_minutes=QUERY_OVERLAP_MINUTES,
    )
    logger.info("조회 범위: %s ~ %s", query_begin, query_end)

    keywords = load_keywords()
    if not keywords:
        logger.warning("처리할 키워드가 없습니다. 종료합니다.")
        return

    total_bid_sent = 0
    total_prebid_sent = 0
    had_failures = False

    for i, kw in enumerate(keywords, 1):
        logger.info(
            "━━━ [%d/%d] 키워드: %s (업종: %s) ━━━",
            i,
            len(keywords),
            kw.original,
            ", ".join(bt.display_name for bt in kw.bid_type_enums),
        )

        bid_result = process_bid_notices(kw, state, query_begin, query_end)
        total_bid_sent += bid_result.sent_count
        had_failures = had_failures or bid_result.had_failures

        prebid_result = process_prebid_notices(kw, state, query_begin, query_end)
        total_prebid_sent += prebid_result.sent_count
        had_failures = had_failures or prebid_result.had_failures

    if not had_failures:
        update_last_check(state)
    save_state(state)

    logger.info("=" * 60)
    logger.info("✅ 공고 체크 완료")
    logger.info("   키워드 수: %d", len(keywords))
    logger.info("   입찰공고 알림: %d건", total_bid_sent)
    logger.info("   사전규격 알림: %d건", total_prebid_sent)
    logger.info("   발송 실패 여부: %s", "있음" if had_failures else "없음")
    logger.info("=" * 60)

    if had_failures:
        raise RuntimeError(
            "일부 알림 발송에 실패했습니다. "
            "last_check를 갱신하지 않아 다음 실행에서 재시도됩니다."
        )


if __name__ == "__main__":
    main()
