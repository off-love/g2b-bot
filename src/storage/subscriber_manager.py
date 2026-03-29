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

# 베이스 경로
_DATA_DIR = Path(__file__).parent.parent.parent / "data"

def _get_path(mode: str) -> Path:
    """모드별 구독자 파일 경로 반환"""
    return _DATA_DIR / f"subscribers_{mode}.json"


def load_subscribers(mode: str = "bid") -> set[str]:
    """모드별 subscribers_{mode}.json에서 구독자 Chat ID 목록을 로드합니다.
    (기존 subscribers.json 파일이 있다면 모드 변경에 따라 자동 마이그레이션 합니다.)

    Args:
        mode: 실행 모드

    Returns:
        구독자 Chat ID의 집합 (str). 파일이 없으면 빈 집합 반환.
    """
    path = _get_path(mode)
    legacy_path = _DATA_DIR / "subscribers.json"

    # 타겟 파일이 없으나 옛 버전 파일이 있다면 마이그레이션 시도
    if not path.exists():
        if mode == "bid" and legacy_path.exists():
            try:
                with open(legacy_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                legacy_subs = set(str(item) for item in data.get("subscribers", []))
                if legacy_subs:
                    logger.info(f"💾 기존 subscribers.json에서 {path.name}으로 자동 마이그레이션을 진행합니다.")
                    save_subscribers(legacy_subs, mode="bid")
                    return legacy_subs
            except Exception as e:
                logger.error(f"⚠️ 기존 구독자 데이터 마이그레이션 실패: {e}")
        return set()

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return set(str(item) for item in data.get("subscribers", []))
    except (json.JSONDecodeError, OSError) as e:
        logger.error(f"{path.name} 로드 실패: {e}")
        return set()


def save_subscribers(subscribers: set[str], mode: str = "bid") -> None:
    """구독자 목록을 subscribers_{mode}.json에 저장합니다.

    Args:
        subscribers: 저장할 구독자 Chat ID 집합
        mode: 실행 모드
    """
    path = _get_path(mode)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"subscribers": sorted(list(subscribers))}, f, ensure_ascii=False, indent=2)
    except OSError as e:
        logger.error(f"{path.name} 저장 실패: {e}")


def add_subscriber(chat_id: str, mode: str = "bid") -> bool:
    """새로운 구독자를 추가합니다.

    Args:
        chat_id: 추가할 텔레그램 Chat ID
        mode: 실행 모드

    Returns:
        추가 성공(새로 추가됨) 시 True, 이미 존재하면 False
    """
    chat_id = str(chat_id)
    subscribers = load_subscribers(mode)

    if chat_id in subscribers:
        return False

    subscribers.add(chat_id)
    save_subscribers(subscribers, mode)
    logger.info(f"새로운 구독자 자동 등록 ({mode}): {chat_id}")
    return True


def remove_subscriber(chat_id: str, mode: str = "bid") -> bool:
    """구독자를 제거합니다.

    Args:
        chat_id: 제거할 텔레그램 Chat ID
        mode: 실행 모드

    Returns:
        제거 성공 시 True, 존재하지 않으면 False
    """
    chat_id = str(chat_id)
    subscribers = load_subscribers(mode)
    
    if chat_id not in subscribers:
        return False

    subscribers.discard(chat_id)
    save_subscribers(subscribers, mode)
    logger.info(f"구독 취소 ({mode}): {chat_id}")
    return True


def get_subscriber_count(mode: str = "bid") -> int:
    """현재 등록된 총 구독자 수를 반환합니다."""
    return len(load_subscribers(mode))
