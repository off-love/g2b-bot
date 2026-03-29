"""
텔레그램 봇 — 메시지 발송

텔레그램 Bot API를 통해 알림 메시지를 전송합니다.
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any

import requests

logger = logging.getLogger(__name__)


def _get_bot_token(mode: str = "bid") -> str:
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    if not token:
        raise ValueError("TELEGRAM_BOT_TOKEN 환경변수가 설정되지 않았습니다.")
    return token


def _get_chat_id(mode: str = "bid") -> str:
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")
    if not chat_id:
        raise ValueError("TELEGRAM_CHAT_ID 환경변수가 설정되지 않았습니다.")
    return chat_id


def send_message(
    text: str,
    parse_mode: str = "HTML",
    disable_web_page_preview: bool = True,
    chat_id: str | None = None,
    reply_markup: dict | None = None,
    mode: str = "bid",
) -> bool:
    """텔레그램 메시지 전송

    Args:
        text: 메시지 내용
        parse_mode: 파싱 모드 (HTML 기본)
        disable_web_page_preview: 링크 미리보기 비활성화
        chat_id: 수신 채팅 ID (None이면 환경변수)
        reply_markup: 텔레그램 reply_markup 객체 (인라인 버튼 등)
        mode: 봇 실행 모드

    Returns:
        전송 성공 여부
    """
    token = _get_bot_token(mode)
    if chat_id is None:
        chat_id = _get_chat_id(mode)

    url = f"https://api.telegram.org/bot{token}/sendMessage"

    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": parse_mode,
        "disable_web_page_preview": disable_web_page_preview,
    }
    if reply_markup is not None:
        payload["reply_markup"] = reply_markup

    try:
        response = requests.post(url, json=payload, timeout=30)
        data = response.json()

        if data.get("ok"):
            logger.info("텔레그램 메시지 전송 성공")
            return True
        else:
            error_desc = data.get("description", "알 수 없는 오류")
            logger.error("텔레그램 전송 실패: %s", error_desc)

            # 메시지가 너무 길 경우 분할 재시도
            if "message is too long" in error_desc.lower():
                return _send_long_message(text, parse_mode, chat_id, mode=mode)

            return False

    except requests.RequestException as e:
        logger.error("텔레그램 API 호출 실패: %s", e)
        return False


def _send_long_message(
    text: str,
    parse_mode: str,
    chat_id: str,
    max_length: int = 4000,
    mode: str = "bid",
) -> bool:
    """긴 메시지를 분할하여 전송"""
    token = _get_bot_token(mode)
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    chunks = _split_text(text, max_length)
    all_ok = True

    for i, chunk in enumerate(chunks):
        payload = {
            "chat_id": chat_id,
            "text": chunk,
            "parse_mode": parse_mode,
            "disable_web_page_preview": True,
        }
        try:
            resp = requests.post(url, json=payload, timeout=30)
            data = resp.json()
            if not data.get("ok"):
                logger.error("분할 전송 실패 (%d/%d): %s", i+1, len(chunks), data.get("description"))
                all_ok = False
        except requests.RequestException as e:
            logger.error("분할 전송 오류 (%d/%d): %s", i+1, len(chunks), e)
            all_ok = False

        if i < len(chunks) - 1:
            time.sleep(0.5)

    return all_ok


def _split_text(text: str, max_length: int) -> list[str]:
    """텍스트를 줄 단위로 분할"""
    lines = text.split("\n")
    chunks: list[str] = []
    current: list[str] = []
    current_len = 0

    for line in lines:
        line_len = len(line) + 1  # +1 for newline
        if current_len + line_len > max_length and current:
            chunks.append("\n".join(current))
            current = []
            current_len = 0
        current.append(line)
        current_len += line_len

    if current:
        chunks.append("\n".join(current))

    return chunks


def send_bid_notifications(
    messages: list[dict[str, Any]] | list[str],
    mode: str = "bid",
    chat_id: str | None = None,
) -> int:
    """여러 알림 메시지를 순차 전송

    Args:
        messages: 포맷팅된 메시지(또는 딕셔너리) 목록
                  딕셔너리일 경우 {"text": "...", "reply_markup": {...}} 형식
        mode: 봇 실행 모드
        chat_id: 수신 채팅 ID (None이면 환경변수 기본값 사용)

    Returns:
        성공적으로 전송한 메시지 수
    """
    success_count = 0
    for i, msg in enumerate(messages):
        if isinstance(msg, dict):
            text = msg.get("text", "")
            reply_markup = msg.get("reply_markup")
            is_success = send_message(text, reply_markup=reply_markup, chat_id=chat_id, mode=mode)
        else:
            is_success = send_message(msg, chat_id=chat_id, mode=mode)
            
        if is_success:
            success_count += 1
            
        if i < len(messages) - 1:
            time.sleep(1)  # 텔레그램 rate limit 방지
    return success_count


def broadcast_message(
    text: str,
    target_chat_ids: set[str],
    reply_markup: dict | None = None,
    mode: str = "bid",
) -> list[str]:
    """하나의 메시지를 다수에게 발송합니다.
    결과로 발송 실패(차단/비활성 등)한 chat_id 목록을 반환합니다.

    Args:
        text: 발송할 주 텍스트 메시지
        target_chat_ids: 중복이 제거된 수신자 chat_id 셋
        reply_markup: (Optional) 텔레그램 인라인 버튼 등
        mode: 실행 모드

    Returns:
        invalid_ids: 발송할 수 없는(차단 등) 수신자의 chat_id 목록
    """
    invalid_ids = set()
    token = _get_bot_token(mode)
    url = f"https://api.telegram.org/bot{token}/sendMessage"

    # 메시지 분할 처리
    chunks = _split_text(text, 4000)

    for chunk in chunks:
        base_payload = {
            "text": chunk,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }
        # 분할된 마지막 조각에만 버튼을 추가하여 중복 방지
        if chunk == chunks[-1] and reply_markup is not None:
            base_payload["reply_markup"] = reply_markup

        for chat_id in target_chat_ids:
            if chat_id in invalid_ids:
                continue

            # 방어적 복사: 각 수신자별 독립 payload
            payload = {**base_payload, "chat_id": chat_id}
            try:
                resp = requests.post(url, json=payload, timeout=30)
                data = resp.json()

                # 429 Rate Limit 대응: retry_after 만큼 대기 후 재시도
                if resp.status_code == 429:
                    retry_after = data.get("parameters", {}).get("retry_after", 5)
                    logger.warning("Rate limit! %d초 대기 후 재시도 [%s]", retry_after, chat_id)
                    time.sleep(retry_after)
                    resp = requests.post(url, json=payload, timeout=30)
                    data = resp.json()

                if not data.get("ok"):
                    desc = data.get("description", "").lower()
                    if any(err in desc for err in ["forbidden", "chat not found", "bot was blocked", "deactivated"]):
                        invalid_ids.add(chat_id)
                        logger.warning("유효하지 않은 사용자 감지(차단/탈퇴): %s", chat_id)
                    else:
                        logger.error("메시지 전송 실패 [%s]: %s", chat_id, desc)
            except requests.RequestException as e:
                logger.error("텔레그램 API 연결 오류 [%s]: %s", chat_id, e)

            # Global Limit 방지를 위해 각 발송 후 0.05초 대기 (초당 20건 페이스)
            time.sleep(0.05)

    return list(invalid_ids)


def broadcast_notifications(
    messages: list[dict[str, Any] | str],
    target_chat_ids: set[str],
    mode: str = "bid",
) -> list[str]:
    """여러 알림 메시지 목록을 다수에게 순차적으로 발송합니다.

    Args:
        messages: 포맷팅된 메시지(또는 딕셔너리) 목록
        target_chat_ids: 중복이 제거된 수신자 chat_id 셋
        mode: 봇 실행 모드

    Returns:
        invalid_ids: 발송 중 감지된 유효하지 않은 chat_id 목록
    """
    invalid_ids = set()
    current_chat_ids = set(target_chat_ids)

    for i, msg in enumerate(messages):
        if not current_chat_ids:
            break  # 모든 수신자가 유효하지 않으면 조기 종료

        if isinstance(msg, dict):
            text = msg.get("text", "")
            markup = msg.get("reply_markup")
        else:
            text = msg
            markup = None

        failed = broadcast_message(text, current_chat_ids, reply_markup=markup, mode=mode)
        
        for f_id in failed:
            invalid_ids.add(f_id)
            current_chat_ids.discard(f_id)

        if i < len(messages) - 1:
            time.sleep(1)  # 다수 발송 후 다음 메시지 전송까지 1초 휴식

    return list(invalid_ids)

