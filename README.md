# 🏛️ 나라장터 입찰공고 알림 텔레그램봇

나라장터(G2B) 입찰공고를 놓치지 않고 즉시 확인할 수 있는 텔레그램 기반 알림 서비스입니다.

## ✨ 주요 기능

- **🔔 자동 알림**: 30분마다 새 입찰공고를 체크하여 텔레그램으로 알림
- **🔍 키워드 검색**: OR/AND/제외 조건의 유연한 키워드 설정
- **🏢 수요기관 필터**: 특정 기관의 공고만 선별
- **📍 지역 필터**: 참가가능지역 기준 필터링
- **💰 금액 범위**: 최소~최대 추정가격 범위 설정
- **📌 북마크**: 관심 공고 저장 및 관리
- **📤 공유**: 포워딩용 텍스트 생성
- **📡 다중 수신**: 슈퍼관리자/관리자/구독자 전체에게 브로드캐스트
- **🆓 완전 무료**: GitHub Actions + 공공API (서버 비용 없음)

## 🏗️ 아키텍처

```
GitHub Actions (30분 cron)
  → 프로필별 나라장터 API 호출 (키워드 × 업종)
    → 코드 레벨 필터링 (수요기관/지역/금액)
      → 중복 체크 (state.json)
        → 텔레그램 브로드캐스트 알림 발송
```

## 📋 사전 준비

### 1. 공공데이터포털 API 키 발급
- [data.go.kr](https://data.go.kr) 회원가입/로그인
- **[나라장터 입찰공고정보서비스](https://www.data.go.kr/data/15000766/openapi.do)** 활용 신청

### 2. 텔레그램 봇 생성
1. `@BotFather` → `/newbot` → 봇 토큰 발급
2. 봇과 대화 시작
3. `https://api.telegram.org/bot{TOKEN}/getUpdates` 에서 Chat ID 확인

### 3. GitHub Secrets 등록
| Secret 이름 | 설명 |
|-------------|------|
| `G2B_API_KEY` | 입찰공고정보서비스 인증키 |
| `TELEGRAM_BOT_TOKEN` | 텔레그램 봇 토큰 |
| `TELEGRAM_CHAT_ID` | 수신 채팅 ID |
| `SUPER_ADMIN_CHAT_ID` | 슈퍼관리자 Chat ID |

## ⚙️ 알림 프로필 설정

`config/profiles.yaml` 파일을 편집하세요:

```yaml
profiles:
  - name: "지적측량 용역"
    bid_types: [service]
    keywords:
      or: ["지적측량", "확정측량", "지적재조사"]
      exclude: ["취소공고"]
```

## 🚀 실행

### 로컬 테스트
```bash
pip install -r requirements.txt

export G2B_API_KEY="your-api-key"
export TELEGRAM_BOT_TOKEN="your-bot-token"
export TELEGRAM_CHAT_ID="your-chat-id"
export SUPER_ADMIN_CHAT_ID="your-super-admin-chat-id"

python -m src.main
```

### GitHub Actions
- 자동: 매 30분마다 실행
- 수동: Actions 탭 → "나라장터 입찰공고 체크" → Run workflow

## 📁 프로젝트 구조

```
├── .github/workflows/check_bids.yml   # 스케줄러
├── src/
│   ├── main.py                        # 메인 실행
│   ├── telegram_bot.py                # 텔레그램 발송 (브로드캐스트)
│   ├── update_handler.py              # 명령어 처리
│   ├── bot.py                         # 봇 서버 (Phase 3)
│   ├── api/
│   │   └── bid_client.py              # 입찰공고 API
│   ├── core/
│   │   ├── models.py                  # 데이터 모델
│   │   ├── filter.py                  # 필터링 엔진
│   │   └── formatter.py              # 메시지 포맷
│   ├── storage/
│   │   ├── state_manager.py           # 중복 방지
│   │   ├── profile_manager.py         # 프로필 관리
│   │   ├── admin_manager.py           # 관리자 관리
│   │   ├── subscriber_manager.py      # 구독자 관리
│   │   └── bookmark_manager.py        # 북마크
│   └── utils/time_utils.py            # 시간 유틸
├── config/profiles.yaml               # 알림 프로필
├── data/
│   ├── state.json                     # 알림 이력
│   ├── subscribers_bid.json           # 구독자 목록
│   ├── admins.json                    # 관리자 목록
│   └── bookmarks.json                 # 북마크
└── tests/                             # 유닛 테스트
```
