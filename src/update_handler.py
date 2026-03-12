"""
텔레그램 업데이트 핸들러 (단발성 실행)

전용 웹서버 호스팅 없이 GitHub Actions 스케줄링 안에서
사용자가 남긴 텔레그램 명령어를 수거(getUpdates API)하여
프로필 설정 파일(profiles.yaml)을 수정하는 역할을 수행합니다.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

import requests

from src.storage.profile_manager import (
    add_profile_keyword,
    get_profile_keywords,
    load_profiles,
    remove_profile_keyword,
)
from src.storage.state_manager import load_state, save_state
from src.telegram_bot import send_message

# 로깅 설정
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)


def get_active_profile_name() -> str | None:
    """활성화된 첫 번째 프로필의 이름을 반환합니다."""
    profiles, _ = load_profiles()
    if not profiles:
        return None
    return profiles[0].name


def handle_list_command(chat_id: str) -> None:
    """/list 명령어 처리"""
    profile_name = get_active_profile_name()
    if not profile_name:
        send_message("활성화된 프로필(프로젝트)이 없습니다.", chat_id=chat_id)
        return

    keywords = get_profile_keywords(profile_name)
    if not keywords:
        send_message("현재 <b>등록된 검색 키워드</b>가 없습니다.", chat_id=chat_id)
        return

    text = "🔍 <b>현재 등록된 검색 키워드</b>\n━━━━━━━━━━━━━━\n"
    for i, kw in enumerate(keywords, 1):
        text += f"{i}. <code>{kw}</code>\n"

    send_message(text, chat_id=chat_id)


def handle_add_command(chat_id: str, args: list[str]) -> None:
    """/add 명령어 처리"""
    profile_name = get_active_profile_name()
    if not profile_name:
        send_message("활성화된 프로필이 없습니다.", chat_id=chat_id)
        return

    if not args:
        send_message("⚠️ 사용법이 올바르지 않습니다.\n예시: /add 지적재조사", chat_id=chat_id)
        return

    keyword = " ".join(args)
    success = add_profile_keyword(profile_name, keyword)

    if success:
        send_message(f"✅ '<b>{keyword}</b>' 키워드가 성공적으로 추가되었습니다!\n(다음 알림 주기부터 적용됩니다)", chat_id=chat_id)
    else:
        send_message(f"⚠️ '<b>{keyword}</b>' 키워드는 이미 존재합니다.", chat_id=chat_id)


def handle_remove_command(chat_id: str, args: list[str]) -> None:
    """/remove 명령어 처리"""
    profile_name = get_active_profile_name()
    if not profile_name:
        send_message("활성화된 프로필이 없습니다.", chat_id=chat_id)
        return

    if not args:
        send_message("⚠️ 사용법이 올바르지 않습니다.\n예시: /remove 확정측량", chat_id=chat_id)
        return

    keyword = " ".join(args)
    success = remove_profile_keyword(profile_name, keyword)

    if success:
        send_message(f"🗑️ '<b>{keyword}</b>' 키워드가 성공적으로 삭제되었습니다!", chat_id=chat_id)
    else:
        send_message(f"⚠️ '<b>{keyword}</b>' 키워드를 찾을 수 없습니다.", chat_id=chat_id)


def handle_search_command(chat_id: str, args: list[str]) -> None:
    """/search 명령어 처리: 즉각(일회성) 검색"""
    profiles, _ = load_profiles()
    if not profiles:
        send_message("활성화된 프로필이 없습니다.", chat_id=chat_id)
        return

    if not args:
        send_message("⚠️ 사용법이 올바르지 않습니다.\n예시: /search 지적재조사", chat_id=chat_id)
        return

    keyword = " ".join(args)
    profile = profiles[0]

    # 임시 프로필 생성 (키워드 덮어쓰기)
    import copy
    temp_profile = copy.deepcopy(profile)
    temp_profile.keywords.or_keywords = [keyword]

    send_message(f"🔎 '<b>{keyword}</b>' 키워드로 최근 24시간 내 공고를 검색 중입니다... (최대 1~2분 소요)", chat_id=chat_id)

    bid_messages = []
    prebid_messages = []

    try:
        from src.api.bid_client import fetch_bid_notices_multi_keywords
        from src.api.prebid_client import fetch_prebid_notices
        from src.core.filter import filter_bid_notices, filter_prebid_notices
        from src.core.formatter import format_bid_notice, format_prebid_notice
        from src.telegram_bot import send_bid_notifications

        # 1. 입찰공고
        for bid_type in temp_profile.bid_types:
            dmnd_cd = temp_profile.demand_agencies.by_code[0] if temp_profile.demand_agencies.by_code else ""
            raw_notices = fetch_bid_notices_multi_keywords(
                bid_type=bid_type,
                keywords=[keyword],
                dmnd_instt_cd=dmnd_cd,
                buffer_hours=24,
                max_results=50,
            )
            filtered = filter_bid_notices(raw_notices, temp_profile)
            for notice in filtered:
                msg = format_bid_notice(notice, f"검색: {keyword}")
                bid_messages.append({"text": msg})

        # 2. 사전규격
        if temp_profile.include_prebid:
            for bid_type in temp_profile.bid_types:
                raw_prebids = fetch_prebid_notices(
                    bid_type=bid_type,
                    buffer_hours=24,
                    max_results=50,
                )
                filtered_prebids = filter_prebid_notices(raw_prebids, temp_profile)
                for prebid in filtered_prebids:
                    msg = format_prebid_notice(prebid, f"검색: {keyword}")
                    prebid_messages.append({"text": msg})

        all_messages = bid_messages + prebid_messages
        if all_messages:
            send_bid_notifications(all_messages)
            summary_text = f"✅ <b>검색 완료</b>: 입찰공고 {len(bid_messages)}건, 사전규격 {len(prebid_messages)}건이 발견되었습니다."
            send_message(summary_text, chat_id=chat_id)
        else:
            send_message(f"🤷‍♂️ '<b>{keyword}</b>' 관련하여 최근 24시간 내 올라온 신규 공고가 0건입니다.", chat_id=chat_id)

    except Exception as e:
        logger.error("검색 중 오류 발생: %s", e)
        send_message(f"⚠️ 검색 중 지정된 조건에 맞는 결과를 가져오지 못했거나 오류가 발생했습니다. ({str(e)})", chat_id=chat_id)


def process_updates() -> None:
    """밀린 텔레그램 업데이트를 수신하고 명령어를 처리합니다."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        logger.error("TELEGRAM_BOT_TOKEN 환경변수가 없습니다.")
        return

    state = load_state()
    offset = state.get("telegram_offset", 0)

    url = f"https://api.telegram.org/bot{token}/getUpdates"
    params = {"offset": offset, "timeout": 5, "allowed_updates": ["message"]}

    try:
        response = requests.get(url, params=params, timeout=10)
        data = response.json()
        
        if not data.get("ok"):
            logger.error("업데이트 조회 실패: %s", data.get("description"))
            return

        updates = data.get("result", [])
        if not updates:
            logger.info("수신된 새로운 텔레그램 명령어가 없습니다.")
            return

        logger.info("%d개의 새로운 업데이트를 발견했습니다.", len(updates))
        
        max_update_id = offset

        for update in updates:
            update_id = update.get("update_id")
            if update_id and update_id >= max_update_id:
                max_update_id = update_id + 1

            message = update.get("message")
            if not message:
                continue

            text = message.get("text", "").strip()
            chat_id = str(message.get("chat", {}).get("id"))
            
            if not text or not text.startswith("/"):
                continue

            parts = text.split()
            command = parts[0].lower()
            args = parts[1:]

            logger.info("명령어 수신: %s (args: %s)", command, args)

            if command == "/start" or command == "/help":
                send_message(
                    "안녕하세요! 나라장터 하이브리드 알림 조수입니다. 🤖\n\n"
                    "아래 명령어를 통해 검색 키워드를 언제든지 실시간으로 관리하실 수 있습니다!\n"
                    "(입력 후 최대 30분 이내에 처리 완료 메시지가 도착합니다.)\n\n"
                    "🔍 /list - 현재 등록된 키워드 목록 보기\n"
                    "➕ /add [키워드] - 새 키워드 추가 (예: /add 공간정보)\n"
                    "➖ /remove [키워드] - 키워드 삭제 (예: /remove 공간정보)\n"
                    "🔎 /search [키워드] - (1회성) 지금 즉시 24시간 내 공고 검색", 
                    chat_id=chat_id
                )
            elif command == "/list":
                handle_list_command(chat_id)
            elif command == "/add":
                handle_add_command(chat_id, args)
            elif command == "/remove":
                handle_remove_command(chat_id, args)
            elif command == "/search":
                handle_search_command(chat_id, args)
            else:
                send_message(f"알 수 없는 명령어입니다: {command}", chat_id=chat_id)

        # 상태 오프셋 저장
        state["telegram_offset"] = max_update_id
        save_state(state)
        logger.info("업데이트 처리 완료 및 오프셋 업데이트: %d", max_update_id)

    except requests.RequestException as e:
        logger.error("텔레그램 API 호출 실패: %s", e)


if __name__ == "__main__":
    logger.info("=" * 50)
    logger.info("텔레그램 명령어 수집(GetUpdates) 시작")
    logger.info("=" * 50)
    process_updates()
