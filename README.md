# bidtalk-worker

입찰톡 운영 알림 워커입니다.
나라장터(G2B) 입찰공고 및 사전규격을 확인하고, 키워드가 매칭되는 공고를 FCM 푸시 알림으로 발송합니다.

## 아키텍처

```
GitHub Actions (주간 30분, 야간 2시간 cron)
    → 나라장터 OpenAPI 업무구분별 묶음 조회
    → 서버 내부 키워드 매칭 + 중복 체크
    → FCM Topic 메시지 발송
    → state.json 업데이트 (Git 자동 커밋)
```

## 프로젝트 구조

```
server/
├── .github/workflows/
│   └── check_notices.yml        # 30분 간격 cron
├── src/
│   ├── main.py                  # 메인 실행 스크립트
│   ├── api/
│   │   ├── bid_client.py        # 입찰공고 API
│   │   └── prebid_client.py     # 사전규격 API
│   ├── core/
│   │   ├── models.py            # 데이터 모델
│   │   ├── filter.py            # 2단계 필터링
│   │   ├── formatter.py         # FCM 페이로드 포맷터
│   │   └── topic_hasher.py      # 키워드→해시 변환 (⚠️ iOS와 동일)
│   ├── fcm/
│   │   └── sender.py            # FCM 발송
│   ├── storage/
│   │   └── state_manager.py     # 중복 방지 (state.json)
│   └── utils/
│       └── time_utils.py        # KST 시간 유틸
├── data/
│   ├── state.json               # 알림 이력 (자동 커밋)
│   └── keywords.json            # 활성 키워드 목록
├── scripts/
│   └── generate_topic_hashes.py # 해시 재생성 유틸
├── tests/
│   └── test_topic_hasher.py     # 해시 일관성 테스트
└── requirements.txt
```

## 환경 변수 (GitHub Secrets)

| 변수명 | 설명 |
|--------|------|
| `G2B_API_KEY` | 공공데이터포털 나라장터 입찰공고정보서비스 API 키 |
| `G2B_PREBID_API_KEY` | 사전규격 API 키 (입찰 키와 동일하면 생략 가능) |
| `FIREBASE_CREDENTIALS` | Firebase Admin SDK 서비스 계정 JSON (문자열) |
| `G2B_MAX_API_PAGES` | 업무구분별 최대 조회 페이지 수 (기본 3) |
| `RUN_PREBID` | `0`이면 사전규격 조회를 건너뜀 |

## 무료 운영 최적화

- 입찰공고는 KST 월~금에 30분마다 실행합니다.
- 토요일과 일요일은 하루 종일 2시간마다 실행합니다.
- 사전규격은 `37분` 실행에서는 건너뛰어 호출량을 줄입니다.
- API는 키워드별로 호출하지 않고 업무구분별로 한 번 조회한 뒤 서버 안에서 모든 키워드를 매칭합니다.
- 조회 범위는 마지막 성공 실행 시각 기준이며, 누락 방지를 위해 30분을 겹쳐 조회합니다.
- 업무구분별 최대 3페이지까지만 조회해 갑작스러운 공고 폭증 시 API 호출량을 제한합니다.

## 로컬 개발

```bash
# 1. 가상환경
python3 -m venv .venv
source .venv/bin/activate

# 2. 의존성 설치
pip install -r requirements.txt

# 3. 환경변수 설정
export G2B_API_KEY="your_api_key"
export FIREBASE_CREDENTIALS='{"type":"service_account",...}'

# 4. 실행
python -m src.main

# 5. 테스트
python tests/test_topic_hasher.py
```

## ⚠️ 중요

- **키워드 해시**: `src/core/topic_hasher.py`와 iOS `TopicHasher.swift`는 동일한 출력을 생성해야 합니다.
- **Public Repo**: GitHub Actions 무료 사용을 위해 Public repository로 운영합니다.
- **Secrets**: 모든 API 키와 인증 정보는 반드시 GitHub Secrets에 저장합니다.

## 면책 조항

본 서비스는 조달청(나라장터)의 공식 서비스가 아닙니다.
공공데이터포털 OpenAPI를 활용한 비공식 서비스이며, 데이터의 정확성은 원본 시스템(나라장터)을 기준으로 합니다.
