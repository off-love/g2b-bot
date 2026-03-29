"""
텔레그램 콜백 핸들링 봇 (Phase 2 & 3)

사용자가 버튼을 클릭(Callback Query)하거나 특정 명령어를 입력할 때 이를 처리하는
Long-polling 기반 봇입니다. 24시간 알림은 main.py(GitHub Actions)가 지속 담당하며,
이 스크립트는 로컬 혹은 서버에 띄워두고 사용자와 상호작용할 때 사용됩니다.
"""

from __future__ import annotations

import logging
import os

from telegram import Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
)

from src.storage.bookmark_manager import (
    add_bookmark_from_bid,
    clear_expired_bookmarks,
    get_user_bookmarks,
    load_bookmarks,
    remove_bookmark,
)

# 로깅 설정
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/start 명령어 처리"""
    await update.message.reply_text(
        "안녕하세요! 나라장터 알림 봇입니다. 🤖\n\n"
        "현재 30분에 한 번씩 자동 스크래핑을 위해 GitHub Actions가 돌아가고 있습니다.\n"
        "추가적으로 다음과 같은 명령어를 사용할 수 있습니다:\n"
        "/bookmarks - 저장된 북마크 목록 보기\n"
        "/help - 도움말 보기"
    )


async def bookmarks_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/bookmarks 명령어 처리"""
    # 임시: 로컬 JSON에서 모든 북마크 읽어오기
    # 단일 유저용 봇이므로 파일의 모든 북마크를 읽습니다.
    items = load_bookmarks()
    if not items:
        await update.message.reply_text("저장된 북마크가 없습니다. 📌")
        return

    lines = ["📌 <b>내 북마크 목록</b>", "━━━━━━━━━━━━━━━━━", ""]
    for i, item in enumerate(items, 1):
        lines.append(f"{i}. <b>{item.name}</b>")
        lines.append(f"  🏢 {item.org}")
        lines.append(f"  ⏰ 마감: {item.close_date}")
        lines.append(f"  🔗 <a href='{item.url}'>링크</a>")
        lines.append("")

    text = "\n".join(lines)
    await update.message.reply_html(text, disable_web_page_preview=True)


async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """인라인 리플라이 키보드의 버튼 클릭 처리"""
    query = update.callback_query
    await query.answer()

    data = query.data
    logger.info("콜백 데이터 수신: %s", data)

    # data 형식: bm_bid_{unique_key}
    if data.startswith("bm_"):
        parts = data.split("_", 2)
        if len(parts) == 3:
            _, notice_type, unique_key = parts
            
            # TODO: 현재 state.json의 데이터가 메모리에 없으므로,
            # 완벽한 봇 구현(Phase 3) 전까지 북마크 인라인 버튼 동작 여부만 알림
            await query.edit_message_reply_markup(reply_markup=None)
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text="📌 북마크 기능은 Phase 3 봇 서버 구축 후 완벽 지원 예정입니다!\n"
                     f"(요청 데이터: {notice_type} - {unique_key})"
            )


def main() -> None:
    """봇 실행"""
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        logger.error("TELEGRAM_BOT_TOKEN 환경변수가 없습니다.")
        return

    application = Application.builder().token(token).build()

    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("bookmarks", bookmarks_command))
    application.add_handler(CallbackQueryHandler(button_callback))

    logger.info("텔레그램 봇 서버 시작 중... (Ctrl+C 로 종료)")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
