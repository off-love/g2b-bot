"""
구독자 관리자 (Subscriber Manager)

알림을 받을 일반 사용자(구독자) 목록을 관리합니다.
- 구독자 데이터: data/subscribers.json 에 저장
- 기능: 목록 로드, 저장, 추가, 제거 및 전체 카운트
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# subscribers.json 경로 (프로젝트 루트/data/subscribers.json)
_SUBSCRIBERS_PATH = Path(__file__).parent.parent.parent / "data" / "subscribers.json"


def load_subscribers() -> set[str]:
    """subscribers.json에서 구독자 Chat ID 목록을 로드합니다.

    Returns:
        구독자 Chat ID의 집합 (str). 파일이 없으면 빈 집합 반환.
    """
    if not _SUBSCRIBERS_PATH.exists():
        return set()

    try:
        with open(_SUBSCRIBERS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return set(str(item) for item in data.get("subscribers", []))
    except (json.JSONDecodeError, OSError) as e:
        logger.error("subscribers.json 로드 실패: %s", e)
        return set()


def save_subscribers(subscribers: set[str]) -> None:
    """구독자 목록을 subscribers.json에 저장합니다.

    Args:
        subscribers: 저장할 구독자 Chat ID 집합
    """
    _SUBSCRIBERS_PATH.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(_SUBSCRIBERS_PATH, "w", encoding="utf-8") as f:
            json.dump({"subscribers": sorted(list(subscribers))}, f, ensure_ascii=False, indent=2)
    except OSError as e:
        logger.error("subscribers.json 저장 실패: %s", e)


def add_subscriber(chat_id: str) -> bool:
    """새로운 구독자를 추가합니다.

    Args:
        chat_id: 추가할 텔레그램 Chat ID

    Returns:
        추가 성공(새로 추가됨) 시 True, 이미 존재하면 False
    """
    chat_id = str(chat_id)
    subscribers = load_subscribers()

    if chat_id in subscribers:
        return False

    subscribers.add(chat_id)
    save_subscribers(subscribers)
    logger.info("새로운 구독자 자동 등록: %s", chat_id)
    return True


def remove_subscriber(chat_id: str) -> bool:
    """구독자를 제거합니다.

    Args:
        chat_id: 제거할 텔레그램 Chat ID

    Returns:
        제거 성공 시 True, 존재하지 않으면 False
    """
    chat_id = str(chat_id)
    subscribers = load_subscribers()
    
    if chat_id not in subscribers:
        return False

    subscribers.discard(chat_id)
    save_subscribers(subscribers)
    logger.info("구독 취소: %s", chat_id)
    return True


def get_subscriber_count() -> int:
    """현재 등록된 총 구독자 수를 반환합니다."""
    return len(load_subscribers())
