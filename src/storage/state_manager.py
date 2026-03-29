"""
상태 관리자 — 알림 이력 (중복 방지)

data/state.json 파일을 읽고 쓰며 이미 알림을 보낸 공고를 추적합니다.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path

from src.core.models import NotifiedRecord
from src.utils.time_utils import KST, now_iso

logger = logging.getLogger(__name__)

DEFAULT_STATE_PATH = Path(__file__).parent.parent.parent / "data" / "state.json"

# 30일보다 오래된 기록은 정리
CLEANUP_DAYS = 30


def _ensure_file(path: Path) -> None:
    """상태 파일이 없으면 빈 구조로 생성"""
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        with open(path, "w", encoding="utf-8") as f:
            json.dump({
                "last_check": "",
                "notified_bids": {},
            }, f, ensure_ascii=False, indent=2)


def load_state(path: Path | None = None) -> dict:
    """상태 파일 로드"""
    if path is None:
        path = DEFAULT_STATE_PATH
    _ensure_file(path)
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_state(state: dict, path: Path | None = None) -> None:
    """상태 파일 저장"""
    if path is None:
        path = DEFAULT_STATE_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def is_notified(state: dict, unique_key: str, notice_type: str = "bid") -> bool:
    """이미 알림을 보낸 공고인지 확인"""
    return unique_key in state.get("notified_bids", {})


def mark_notified(
    state: dict,
    unique_key: str,
    profile_name: str,
    notice_type: str = "bid",
) -> None:
    """알림 발송 기록 추가"""
    if "notified_bids" not in state:
        state["notified_bids"] = {}
    state["notified_bids"][unique_key] = {
        "notified_at": now_iso(),
        "profile": profile_name,
        "notice_type": notice_type,
    }


def update_last_check(state: dict) -> None:
    """마지막 체크 시각 업데이트"""
    state["last_check"] = now_iso()


def cleanup_old_records(state: dict, days: int = CLEANUP_DAYS) -> int:
    """오래된 알림 기록 정리

    Returns:
        삭제된 레코드 수
    """
    cutoff = datetime.now(KST) - timedelta(days=days)
    removed = 0

    for section in ("notified_bids",):
        records = state.get(section, {})
        keys_to_remove = []

        for key, record in records.items():
            notified_at_str = record.get("notified_at", "")
            if not notified_at_str:
                keys_to_remove.append(key)
                continue
            try:
                notified_at = datetime.fromisoformat(notified_at_str)
                if notified_at < cutoff:
                    keys_to_remove.append(key)
            except (ValueError, TypeError):
                keys_to_remove.append(key)

        for key in keys_to_remove:
            del records[key]
            removed += 1

    if removed > 0:
        logger.info("오래된 알림 기록 %d건 정리됨", removed)

    return removed
