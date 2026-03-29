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
    get_all_admins,
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
from src.storage.subscriber_manager import (
    add_subscriber,
    get_subscriber_count,
    load_subscribers,
    remove_subscriber,
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

def handle_admin_command(chat_id: str, args: list[str], mode: str) -> None:
    """/admin 명령어 처리
    
    사용법:
        /admin users            — 전체 사용자(구독자) 목록 보기 (관리자 이상)
        /admin list             — 현재 관리자 목록 출력 (슈퍼 관리자)
        /admin add <chat_id>    — 관리자 추가 (슈퍼 관리자)
        /admin remove <chat_id> — 관리자 제거 (슈퍼 관리자)
    """
    sub = args[0].lower() if args else "help"

    # 1. 'users' 명령어는 일반 관리자도 사용 가능
    if sub == "users":
        if not _require_admin(chat_id, mode):
            return
        
        subs = sorted(list(load_subscribers(mode)))
        admins = sorted(list(get_all_admins()))
        count = len(set(subs) | set(admins))
        
        lines = [f"👥 <b>전체 사용자 목록 (총 {count}명)</b>\n━━━━━━━━━━━━━━"]
        lines.append("\n👑 <b>관리자 권한 사용자</b>")
        for i, admin_id in enumerate(admins, 1):
            label = " (슈퍼 관리자)" if is_super_admin(admin_id) else ""
            lines.append(f"{i}. <code>{admin_id}</code>{label}")
        
        lines.append("\n👤 <b>일반 알림 구독자</b>")
        if not subs:
            lines.append("- (없음)")
        for i, sub_id in enumerate(subs, 1):
            lines.append(f"{i}. <code>{sub_id}</code>")
            
        send_message("\n".join(lines), chat_id=chat_id, mode=mode)
        return

    # 2. 그 외 명령어는 슈퍼 관리자만 가능
    if not _require_super_admin(chat_id, mode):
        return

    if sub == "list":
        admins = get_all_admins()
        if not admins:
            send_message("현재 등록된 관리자가 없습니다.\n(슈퍼 관리자만 존재합니다)", chat_id=chat_id, mode=mode)
            return

        super_id = os.environ.get("SUPER_ADMIN_CHAT_ID", "").strip()
        lines = ["👑 <b>관리자 목록</b>\n━━━━━━━━━━━━━━"]
        for i, admin_id in enumerate(admins, 1):
            label = " (슈퍼 관리자)" if admin_id == super_id else ""
            lines.append(f"{i}. <code>{admin_id}</code>{label}")
        send_message("\n".join(lines), chat_id=chat_id, mode=mode)

    elif sub == "add":
        if len(args) < 2:
            send_message("⚠️ 사용법: /admin add <chat_id>\n예시: /admin add 123456789", chat_id=chat_id, mode=mode)
            return
        target_id = args[1].strip()
        if add_admin(target_id):
            send_message(f"✅ <code>{target_id}</code> 를 관리자로 추가했습니다.", chat_id=chat_id, mode=mode)
        else:
            send_message(f"⚠️ <code>{target_id}</code> 는 이미 관리자로 등록되어 있습니다.", chat_id=chat_id, mode=mode)

    elif sub == "remove":
        if len(args) < 2:
            send_message("⚠️ 사용법: /admin remove <chat_id>\n예시: /admin remove 123456789", chat_id=chat_id, mode=mode)
            return
        target_id = args[1].strip()
        super_id = os.environ.get("SUPER_ADMIN_CHAT_ID", "").strip()
        if target_id == super_id:
            send_message("⛔ 슈퍼 관리자는 이 방법으로 제거할 수 없습니다.", chat_id=chat_id, mode=mode)
            return
        if remove_admin(target_id):
            send_message(f"🗑️ <code>{target_id}</code> 를 관리자에서 제거했습니다.", chat_id=chat_id, mode=mode)
        else:
            send_message(f"⚠️ <code>{target_id}</code> 는 관리자 목록에 없습니다.", chat_id=chat_id, mode=mode)

    else:
        send_message(
            "👑 <b>/admin 명령어 도움말</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "/admin users — 전체 사용자(구독자) 목록 보기 (관리자+)\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "⚠️ <b>아래는 슈퍼 관리자 전용입니다.</b>\n"
            "/admin list — 관리자 목록 보기\n"
            "/admin add &lt;chat_id&gt; — 관리자 추가\n"
            "/admin remove &lt;chat_id&gt; — 관리자 제거",
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
    from src.core.filter import filter_bid_notices
    from src.core.formatter import format_bid_notice
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

    try:
        bid_messages = fetch_bids_parallel()

        if bid_messages:
            send_bid_notifications(bid_messages, mode=mode)
            summary_text = f"✅ <b>검색 완료</b>: 입찰공고 {len(bid_messages)}건이 발견되었습니다."
            send_message(summary_text, chat_id=chat_id, mode=mode)
        else:
            send_message(f"🤷‍♂️ '<b>{keyword}</b>' 관련하여 최근 24시간 내 올라온 신규 공고가 0건입니다.", chat_id=chat_id, mode=mode)

    except Exception as e:
        logger.error("검색 중 오류 발생: %s", e)
        send_message(f"⚠️ 검색 중 지정된 조건에 맞는 결과를 가져오지 못했거나 오류가 발생했습니다. ({str(e)})", chat_id=chat_id, mode=mode)


def process_updates(mode: str = "bid") -> None:
    """밀린 텔레그램 업데이트를 수신하고 명령어를 처리합니다."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        logger.error("TELEGRAM_BOT_TOKEN 환경변수가 없습니다.")
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
            
            # [추가] 메시지를 보낸 모든 사용자를 자동으로 구독자 목록에 추가
            if chat_id:
                add_subscriber(chat_id, mode=mode)
            
            if not text or not text.startswith("/"):
                continue

            parts = text.split()
            raw_command = parts[0].lower()
            # @botname 접미사 제거 (예: /search@mybotname → /search)
            command = raw_command.split("@")[0]
            args = parts[1:]

            logger.info("명령어 수신: %s (args: %s, chat_id: %s)", command, args, chat_id)

            if command in ("/start", "/help"):
                base = (
                    "안녕하세요! 나라장터 입찰공고 알림 조수입니다. 🤖\n\n"
                    "📋 <b>사용 가능한 명령어</b>\n"
                    "━━━━━━━━━━━━━━━━━━\n"
                    "🔍 /list — 현재 등록된 키워드 목록 보기\n"
                    "🚫 /stop — 알림 발송 중단 (구독 해지)\n"
                )
                if is_admin(chat_id):
                    base += (
                        "\n<b>⚙️ 관리자 명령어</b>\n"
                        "/add &lt;키워드&gt; — 검색 키워드 추가\n"
                        "/remove &lt;키워드&gt; — 검색 키워드 제거\n"
                        "/search &lt;키워드&gt; — 즉시 검색 실행\n"
                    )
                if is_super_admin(chat_id):
                    base += (
                        "\n<b>👑 슈퍼 관리자 명령어</b>\n"
                        "/admin list — 관리자 목록 보기\n"
                        "/admin add &lt;chat_id&gt; — 관리자 추가\n"
                        "/admin remove &lt;chat_id&gt; — 관리자 제거\n"
                    )
                if not is_admin(chat_id):
                    base += "\n💡 키워드 관리 기능은 관리자에게 문의하세요."
                
                send_message(base, chat_id=chat_id, mode=mode)

            elif command == "/list":
                handle_list_command(chat_id, mode)
            elif command == "/add":
                handle_add_command(chat_id, args, mode)
            elif command == "/remove":
                handle_remove_command(chat_id, args, mode)
            elif command == "/search":
                handle_search_command(chat_id, args, mode)
            elif command == "/admin":
                handle_admin_command(chat_id, args, mode)
            elif command == "/stop":
                if remove_subscriber(chat_id, mode=mode):
                    send_message("📴 알림 구독이 해제되었습니다. 다시 알림을 받으시려면 언제든 메시지를 보내주세요.", chat_id=chat_id, mode=mode)
                else:
                    send_message("⚠️ 구독 정보를 찾을 수 없거나 이미 해지되었습니다.", chat_id=chat_id, mode=mode)
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
    logger.info("=" * 50)
    logger.info("텔레그램 명령어 수집(GetUpdates) 시작")
    logger.info("=" * 50)
    process_updates(mode="bid")
