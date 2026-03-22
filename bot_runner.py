"""
상시 구동형 봇 실행 스크립트 (Persistent Bot Runner)

GitHub Actions 대신 전용 서버(VPS 등)에서 24시간 구동할 때 사용합니다.
- 텔레그램 명령어 수집: 10초마다 (실시간 응답 가능)
- 입찰공고 체크: 30분마다 (또는 설정된 주기)
"""

import logging
import time
import os
import sys
from datetime import datetime, timedelta

from src.update_handler import process_updates
from src.main import main as run_bid_check
from src.storage.profile_manager import load_profiles

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%G-%m-%d %H:%M:%S",
)
logger = logging.getLogger("BotRunner")

def bot_loop():
    logger.info("=" * 50)
    logger.info("나라장터 상시 구동 봇 시작")
    logger.info("=" * 50)
    
    _, settings = load_profiles()
    check_interval = settings.check_interval_minutes * 60  # 초 단위 변환
    update_interval = 10  # 텔레그램 명령어 확인 주기 (10초)
    
    last_bid_check = datetime.now() - timedelta(seconds=check_interval)
    
    try:
        while True:
            now = datetime.now()
            
            # 1. 텔레그램 명령어 처리 (자주 확인)
            try:
                process_updates(mode="bid")
            except Exception as e:
                logger.error(f"명령어 처리 중 오류: {e}")
            
            # 2. 입찰공고 체크 (주기적 확인)
            if (now - last_bid_check).total_seconds() >= check_interval:
                logger.info("주기적 입찰공고 체크 시작...")
                try:
                    run_bid_check()
                    last_bid_check = now
                except Exception as e:
                    logger.error(f"입찰공고 체크 중 오류: {e}")
            
            # 짧은 대기 후 반복
            time.sleep(update_interval)
            
    except KeyboardInterrupt:
        logger.info("봇이 사용자에 의해 중단되었습니다.")
    except Exception as e:
        logger.critical(f"봇 실행 중 치명적 오류 발생: {e}")
        sys.exit(1)

if __name__ == "__main__":
    bot_loop()
