"""
관리자 관리 모듈

관리자(Admin) 목록을 data/admins.json에 저장/로드하고,
권한 체크 함수를 제공합니다.

권한 계층:
  슈퍼관리자 (Super Admin) — 환경변수 TELEGRAM_CHAT_ID로 지정
  관리자 (Admin)           — admins.json에 등록된 사용자
  일반 사용자              — 위 두 그룹에 속하지 않는 사용자
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import TypedDict

logger = logging.getLogger(__name__)

# admins.json 파일 경로 (프로젝트 루트 기준)
_ADMINS_FILE = Path(__file__).parent.parent.parent / "data" / "admins.json"

KST = timezone(timedelta(hours=9))


class AdminRecord(TypedDict):
    chat_id: str
    name: str
    added_at: str


# ──────────────────────────────────────────────
# 내부 헬퍼
# ──────────────────────────────────────────────

def _load_raw() -> dict:
    """admins.json 원본을 반환합니다. 파일이 없으면 빈 구조를 반환합니다."""
    if not _ADMINS_FILE.exists():
        return {"admins": []}
    try:
        with open(_ADMINS_FILE, encoding="utf-8") as f:
            data = json.load(f)
        if "admins" not in data:
            data["admins"] = []
        return data
    except (json.JSONDecodeError, OSError) as e:
        logger.error("admins.json 로드 실패: %s", e)
        return {"admins": []}


def _save_raw(data: dict) -> None:
    """admins.json에 데이터를 저장합니다."""
    try:
        _ADMINS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(_ADMINS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except OSError as e:
        logger.error("admins.json 저장 실패: %s", e)


# ──────────────────────────────────────────────
# 공개 API
# ──────────────────────────────────────────────

def get_super_admin_id() -> str:
    """슈퍼관리자 chat_id를 반환합니다. (TELEGRAM_CHAT_ID 환경변수 사용)"""
    return os.environ.get("TELEGRAM_CHAT_ID", "").strip()


def is_super_admin(chat_id: str) -> bool:
    """해당 chat_id가 슈퍼관리자인지 확인합니다."""
    super_id = get_super_admin_id()
    return bool(super_id) and chat_id == super_id


def get_admins() -> list[AdminRecord]:
    """등록된 관리자 목록을 반환합니다. (슈퍼관리자 미포함)"""
    return _load_raw().get("admins", [])


def is_admin(chat_id: str) -> bool:
    """해당 chat_id가 관리자 또는 슈퍼관리자인지 확인합니다."""
    if is_super_admin(chat_id):
        return True
    admins = get_admins()
    return any(a["chat_id"] == chat_id for a in admins)


def add_admin(chat_id: str, name: str) -> bool:
    """관리자를 추가합니다.

    Args:
        chat_id: 추가할 사용자의 텔레그램 chat_id
        name: 관리자 이름(식별용)

    Returns:
        True  — 추가 성공
        False — 이미 존재하거나 슈퍼관리자인 경우
    """
    # 슈퍼관리자는 admins.json에 저장하지 않음
    if is_super_admin(chat_id):
        logger.warning("슈퍼관리자(%s)를 일반 관리자로 추가할 수 없습니다.", chat_id)
        return False

    data = _load_raw()
    admins: list[AdminRecord] = data["admins"]

    if any(a["chat_id"] == chat_id for a in admins):
        logger.info("이미 등록된 관리자: %s", chat_id)
        return False

    admins.append({
        "chat_id": chat_id,
        "name": name,
        "added_at": datetime.now(KST).isoformat(),
    })
    data["admins"] = admins
    _save_raw(data)
    logger.info("관리자 추가: %s (%s)", name, chat_id)
    return True


def remove_admin(chat_id: str) -> bool:
    """관리자를 삭제합니다.

    Returns:
        True  — 삭제 성공
        False — 존재하지 않는 경우
    """
    data = _load_raw()
    admins: list[AdminRecord] = data["admins"]

    new_admins = [a for a in admins if a["chat_id"] != chat_id]
    if len(new_admins) == len(admins):
        return False  # 삭제할 대상 없음

    data["admins"] = new_admins
    _save_raw(data)
    logger.info("관리자 삭제: %s", chat_id)
    return True
