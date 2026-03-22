"""
텔레그램 업데이트 핸들러 (단발성 실행)

전용 웹서버 호스팅 없이 GitHub Actions 스케줄링 안에서
사용자가 남긴 텔레그램 명령어를 수거(getUpdates API)하여
프로필 설정 파일(profiles.yaml)을 수정하는 역할을 수행합니다.
"""

from __future__ import annotations

import argparse
import logging
import os
from pathlib import Path

import requests

from src.storage.admin_manager import (
    add_admin,
    get_admins,
    is_admin,
    is_super_admin,
    remove_admin,
)
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


# ──────────────────────────────────────────────
# 권한 체크 헬퍼
# ──────────────────────────────────────────────

def _require_admin(chat_id: str, mode: str) -> bool:
    """관리자 권한을 확인합니다. 권한이 없으면 안내 메시지를 전송하고 False를 반환합니다."""
    if is_admin(chat_id):
        return True
    send_message(
        "🔒 이 명령어는 <b>등록된 관리자</b>만 사용할 수 있습니다.",
        chat_id=chat_id,
        mode=mode,
    )
    return False


def _require_super_admin(chat_id: str, mode: str) -> bool:
    """슈퍼관리자 권한을 확인합니다. 권한이 없으면 안내 메시지를 전송하고 False를 반환합니다."""
    if is_super_admin(chat_id):
        return True
    send_message(
        "🔒 이 명령어는 <b>슈퍼관리자</b>만 사용할 수 있습니다.",
        chat_id=chat_id,
        mode=mode,
    )
    return False


# ──────────────────────────────────────────────
# 관리자 관리 명령어 핸들러
# ──────────────────────────────────────────────

def handle_admins_command(chat_id: str, mode: str) -> None:
    """/admins 명령어 처리 — 관리자 목록 조회 (슈퍼관리자 전용)"""
    if not _require_super_admin(chat_id, mode):
        return

    admins = get_admins()
    if not admins:
        send_message(
            "📋 <b>등록된 관리자가 없습니다.</b>\n"
            "<code>/admin_add [chat_id] [이름]</code> 으로 추가하세요.",
            chat_id=chat_id,
            mode=mode,
        )
        return

    lines = ["📋 <b>관리자 목록</b>", "━━━━━━━━━━━━━━", ""]
    for i, admin in enumerate(admins, 1):
        added_date = admin.get("added_at", "")[:10]  # YYYY-MM-DD
        lines.append(f"{i}. <b>{admin['name']}</b> (ID: <code>{admin['chat_id']}</code>)")
        lines.append(f"   등록일: {added_date}")
        lines.append("")
    send_message("\n".join(lines), chat_id=chat_id, mode=mode)


def handle_admin_add_command(chat_id: str, args: list[str], mode: str) -> None:
    """/admin_add [chat_id] [이름] 명령어 처리 (슈퍼관리자 전용)"""
    if not _require_super_admin(chat_id, mode):
        return

    if len(args) < 2:
        send_message(
            "⚠️ 사용법이 올바르지 않습니다.\n"
            "예시: <code>/admin_add 123456789 홍길동</code>",
            chat_id=chat_id,
            mode=mode,
        )
        return

    target_id = args[0]
    name = " ".join(args[1:])

    if is_super_admin(target_id):
        send_message(
            "⚠️ 슈퍼관리자는 이미 최고 권한을 가지고 있습니다.",
            chat_id=chat_id,
            mode=mode,
        )
        return

    success = add_admin(target_id, name)
    if success:
        send_message(
            f"✅ '<b>{name}</b>' (<code>{target_id}</code>)이 관리자로 추가되었습니다.",
            chat_id=chat_id,
            mode=mode,
        )
    else:
        send_message(
            f"⚠️ '<code>{target_id}</code>'는 이미 등록된 관리자입니다.",
            chat_id=chat_id,
            mode=mode,
        )


def handle_admin_remove_command(chat_id: str, args: list[str], mode: str) -> None:
    """/admin_remove [chat_id] 명령어 처리 (슈퍼관리자 전용)"""
    if not _require_super_admin(chat_id, mode):
        return

    if not args:
        send_message(
            "⚠️ 사용법이 올바르지 않습니다.\n"
            "예시: <code>/admin_remove 123456789</code>",
            chat_id=chat_id,
            mode=mode,
        )
        return

    target_id = args[0]

    if is_super_admin(target_id):
        send_message(
            "⚠️ 슈퍼관리자는 삭제할 수 없습니다.",
            chat_id=chat_id,
            mode=mode,
        )
        return

    success = remove_admin(target_id)
    if success:
        send_message(
            f"🗑️ 관리자 (<code>{target_id}</code>)가 삭제되었습니다.",
            chat_id=chat_id,
            mode=mode,
        )
    else:
        send_message(
            f"⚠️ '<code>{target_id}</code>'는 등록된 관리자가 아닙니다.",
            chat_id=chat_id,
            mode=mode,
        )


def handle_list_command(chat_id: str, mode: str) -> None:
    """/list 명령어 처리"""
    profile_name = get_active_profile_name()
    if not profile_name:
        send_message("활성화된 프로필(프로젝트)이 없습니다.", chat_id=chat_id, mode=mode)
        return

    keywords = get_profile_keywords(profile_name)
    if not keywords:
        send_message("현재 <b>등록된 검색 키워드</b>가 없습니다.", chat_id=chat_id)
        return

    text = "🔍 <b>현재 등록된 검색 키워드</b>\n━━━━━━━━━━━━━━\n"
    for i, kw in enumerate(keywords, 1):
        text += f"{i}. <code>{kw}</code>\n"

    send_message(text, chat_id=chat_id, mode=mode)


def handle_add_command(chat_id: str, args: list[str], mode: str) -> None:
    """/add 명령어 처리 (관리자 전용)"""
    if not _require_admin(chat_id, mode):
        return

    profile_name = get_active_profile_name()
    if not profile_name:
        send_message("활성화된 프로필이 없습니다.", chat_id=chat_id, mode=mode)
        return

    if not args:
        send_message("⚠️ 사용법이 올바르지 않습니다.\n예시: /add 지적재조사", chat_id=chat_id, mode=mode)
        return

    keyword = " ".join(args)
    success = add_profile_keyword(profile_name, keyword)

    if success:
        send_message(f"✅ '<b>{keyword}</b>' 키워드가 성공적으로 추가되었습니다!\n(다음 알림 주기부터 적용됩니다)", chat_id=chat_id, mode=mode)
    else:
        send_message(f"⚠️ '<b>{keyword}</b>' 키워드는 이미 존재합니다.", chat_id=chat_id, mode=mode)


def handle_remove_command(chat_id: str, args: list[str], mode: str) -> None:
    """/remove 명령어 처리 (관리자 전용)"""
    if not _require_admin(chat_id, mode):
        return

    profile_name = get_active_profile_name()
    if not profile_name:
        send_message("활성화된 프로필이 없습니다.", chat_id=chat_id, mode=mode)
        return

    if not args:
        send_message("⚠️ 사용법이 올바르지 않습니다.\n예시: /remove 확정측량", chat_id=chat_id, mode=mode)
        return

    keyword = " ".join(args)
    success = remove_profile_keyword(profile_name, keyword)

    if success:
        send_message(f"🗑️ '<b>{keyword}</b>' 키워드가 성공적으로 삭제되었습니다!", chat_id=chat_id, mode=mode)
    else:
        send_message(f"⚠️ '<b>{keyword}</b>' 키워드를 찾을 수 없습니다.", chat_id=chat_id, mode=mode)


def handle_search_command(chat_id: str, args: list[str], mode: str) -> None:
    """/search 명령어 처리: 즉각(일회성) 검색 (관리자 전용)"""
    if not _require_admin(chat_id, mode):
        return

    profiles, _ = load_profiles()
    if not profiles:
        send_message("활성화된 프로필이 없습니다.", chat_id=chat_id, mode=mode)
        return

    if not args:
        send_message("⚠️ 사용법이 올바르지 않습니다.\n예시: /search 지적재조사", chat_id=chat_id, mode=mode)
        return

    keyword = " ".join(args)
    profile = profiles[0]

    # 임시 프로필 생성 (키워드 덮어쓰기)
    import copy
    temp_profile = copy.deepcopy(profile)
    temp_profile.keywords.or_keywords = [keyword]

    send_message(f"🔎 '<b>{keyword}</b>' 키워드로 최근 24시간 내 공고를 검색 중입니다... (최대 1~2분 소요)", chat_id=chat_id, mode=mode)

    from concurrent.futures import ThreadPoolExecutor
    from src.api.bid_client import fetch_bid_notices
    from src.api.prebid_client import fetch_prebid_notices
    from src.core.filter import filter_bid_notices, filter_prebid_notices
    from src.core.formatter import format_bid_notice, format_prebid_notice
    from src.telegram_bot import send_bid_notifications

    def fetch_bids_parallel():
        bids = []
        seen_bid_keys = set()
        for bid_type in temp_profile.bid_types:
            dmnd_cd = temp_profile.demand_agencies.by_code[0] if temp_profile.demand_agencies.by_code else ""
            raw_notices = fetch_bid_notices(
                bid_type=bid_type,
                keyword=keyword,
                dmnd_instt_cd=dmnd_cd,
                buffer_hours=24,
                max_results=50,
            )
            filtered = filter_bid_notices(raw_notices, temp_profile)
            for notice in filtered:
                if notice.unique_key not in seen_bid_keys:
                    seen_bid_keys.add(notice.unique_key)
                    msg = format_bid_notice(notice, f"검색: {keyword}", matched_keyword=keyword)
                    bids.append({"text": msg})
        return bids

    def fetch_prebids_parallel():
        prebids = []
        if not temp_profile.include_prebid:
            return []
        seen_prebid_keys = set()
        for bid_type in temp_profile.bid_types:
            raw_prebids = fetch_prebid_notices(
                bid_type=bid_type,
                keyword=keyword,
                buffer_hours=24,
                max_results=50,
            )
            filtered_prebids = filter_prebid_notices(raw_prebids, temp_profile)
            for prebid in filtered_prebids:
                if prebid.unique_key not in seen_prebid_keys:
                    seen_prebid_keys.add(prebid.unique_key)
                    msg = format_prebid_notice(prebid, f"검색: {keyword}")
                    prebids.append({"text": msg})
        return prebids

    try:
        bid_messages = []
        prebid_messages = []
        if mode == "bid":
            bid_messages = fetch_bids_parallel()
        elif mode == "prebid":
            prebid_messages = fetch_prebids_parallel()

        all_messages = bid_messages + prebid_messages
        if all_messages:
            send_bid_notifications(all_messages, mode=mode)
            type_name = "입찰공고" if mode == "bid" else "사전규격"
            summary_text = f"✅ <b>검색 완료</b>: {type_name} {len(all_messages)}건이 발견되었습니다."
            send_message(summary_text, chat_id=chat_id, mode=mode)
        else:
            send_message(f"🤷‍♂️ '<b>{keyword}</b>' 관련하여 최근 24시간 내 올라온 신규 공고가 0건입니다.", chat_id=chat_id, mode=mode)

    except Exception as e:
        logger.error("검색 중 오류 발생: %s", e)
        send_message(f"⚠️ 검색 중 지정된 조건에 맞는 결과를 가져오지 못했거나 오류가 발생했습니다. ({str(e)})", chat_id=chat_id, mode=mode)


def process_updates(mode: str) -> None:
    """밀린 텔레그램 업데이트를 수신하고 명령어를 처리합니다."""
    env_var = "PREBID_TELEGRAM_BOT_TOKEN" if mode == "prebid" else "TELEGRAM_BOT_TOKEN"
    token = os.environ.get(env_var)
    if not token:
        logger.error("%s 환경변수가 없습니다.", env_var)
        if mode == "prebid":
            try:
                send_message(f"🚨 [사전규격 봇 설정 오류]\nGitHub Secrets에 <b>{env_var}</b> 가 설정되지 않았습니다.\n토큰을 확인해 주세요!", mode="bid")
            except Exception:
                pass
        return

    state = load_state()
    state_key = f"telegram_offset_{mode}"
    offset = state.get(state_key, 0)

    url = f"https://api.telegram.org/bot{token}/getUpdates"
    params = {"offset": offset, "timeout": 5, "allowed_updates": ["message"]}

    try:
        response = requests.get(url, params=params, timeout=10)
        data = response.json()
        
        if not data.get("ok"):
            logger.error("업데이트 조회 실패: %s", data.get("description"))
            if mode == "prebid":
                try:
                    send_message(f"🚨 [사전규격 봇 연결 오류]\n텔레그램 업데이트 조회 실패:\n<code>{data.get('description')}</code>\n토큰이 잘못되었거나 봇이 삭제되었을 수 있습니다.", mode="bid")
                except Exception:
                    pass
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
                type_name = "사전규격" if mode == "prebid" else "입찰공고"
                send_message(
                    f"안녕하세요! 나라장터 {type_name} 알림 조수입니다. 🤖\n\n"
                    "아래 명령어를 통해 검색 키워드를 언제든지 실시간으로 관리하실 수 있습니다!\n"
                    "(입력 후 1시간 내외에 처리 완료 메시지가 도착합니다.)\n\n"
                    "🔍 /list - 현재 등록된 키워드 목록 보기", 
                    chat_id=chat_id,
                    mode=mode
                )
            elif command == "/list":
                handle_list_command(chat_id, mode)
            elif command == "/add":
                handle_add_command(chat_id, args, mode)
            elif command == "/remove":
                handle_remove_command(chat_id, args, mode)
            elif command == "/search":
                handle_search_command(chat_id, args, mode)
            elif command == "/admins":
                handle_admins_command(chat_id, mode)
            elif command == "/admin_add":
                handle_admin_add_command(chat_id, args, mode)
            elif command == "/admin_remove":
                handle_admin_remove_command(chat_id, args, mode)
            else:
                send_message(f"알 수 없는 명령어입니다: {command}", chat_id=chat_id, mode=mode)

        # 상태 오프셋 저장
        state_key = f"telegram_offset_{mode}"
        state[state_key] = max_update_id
        save_state(state)
        logger.info("업데이트 처리 완료 및 오프셋 업데이트: %s=%d", state_key, max_update_id)

    except requests.RequestException as e:
        logger.error("텔레그램 API 호출 실패: %s", e)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="텔레그램 명령어 수집")
    parser.add_argument("--mode", type=str, choices=["bid", "prebid"], default="bid", help="스크립트 실행 모드 (bid 또는 prebid)")
    args = parser.parse_args()
    
    mode = args.mode

    logger.info("=" * 50)
    logger.info("텔레그램 명령어 수집(GetUpdates) 시작 (모드: %s)", mode.upper())
    logger.info("=" * 50)
    process_updates(mode)
