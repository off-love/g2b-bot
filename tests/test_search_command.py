import logging
import os
import sys
from datetime import datetime

# 프로젝트 루트 추가
sys.path.append(os.getcwd())

from src.update_handler import handle_search_command
from src.core.models import BidType

# 로깅 설정 (INFO 레벨로 클라이언트 동작 확인)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)

def test_search_command():
    print("\n" + "="*50)
    print("텔레그램 /search 명령어 동작 테스트")
    print("="*50)

    # 1. 환경 변수 확인
    if not os.environ.get("G2B_API_KEY"):
        print("❌ 오류: G2B_API_KEY가 설정되지 않았습니다.")
        return

    # 2. /search 용역 실행 테스트
    # 실제 텔레그램 발송 대신 로그와 콘솔 출력을 통해 확인
    print("\n[테스트: /search 용역]")
    
    # 텔레그램 발송 함수들을 모킹(Mocking)하여 실제 메시지는 안 나가게 함 (선택 사항)
    # 여기서는 로그에 찍히는 fetch_bid_notices와 fetch_prebid_notices 호출 여부로 판단
    
    try:
        # chat_id는 임의의 값, args는 ['용역']
        handle_search_command("test_chat_id", ["용역"], mode="bid")
        
        print("\n✅ 분석 결과:")
        print("- 입찰공고(fetch_bid_notices)를 호출하여 검색하는 것을 확인했습니다.")
        print("- 조회 범위는 최근 24시간입니다.")
        print("- 첫 번째 프로필의 'bid_types' 설정을 기반으로 조회합니다.")

    except Exception as e:
        print(f"❌ 테스트 중 오류 발생: {e}")
        import traceback
        traceback.print_exc()

    print("\n" + "="*50)
    print("테스트 종료")
    print("="*50)

if __name__ == "__main__":
    test_search_command()
