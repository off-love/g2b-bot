"""
Firebase Cloud Messaging (FCM) 발송 모듈

Firebase Admin SDK를 이용하여 FCM Topic 메시지를 발송합니다.
기존 텔레그램 발송 모듈(telegram_bot.py)을 대체합니다.
"""

from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path

logger = logging.getLogger(__name__)

# Firebase Admin SDK 지연 임포트 (테스트 시 모킹 용이)
_firebase_app = None


def _init_firebase() -> None:
    """Firebase Admin SDK 초기화 (최초 1회)"""
    global _firebase_app

    if _firebase_app is not None:
        return

    try:
        import firebase_admin
        from firebase_admin import credentials

        # 이미 초기화된 경우
        try:
            _firebase_app = firebase_admin.get_app()
            return
        except ValueError:
            pass

        # FIREBASE_CREDENTIALS 환경변수 (GitHub Secrets에 JSON 문자열로 저장)
        cred_json = os.environ.get("FIREBASE_CREDENTIALS", "")
        if cred_json:
            cred_data = json.loads(cred_json)
            cred = credentials.Certificate(cred_data)
        else:
            # 로컬 개발: 파일 경로로 시도
            cred_path = Path(__file__).parent.parent.parent / "firebase-credentials.json"
            if cred_path.exists():
                cred = credentials.Certificate(str(cred_path))
            else:
                raise ValueError(
                    "FIREBASE_CREDENTIALS 환경변수 또는 firebase-credentials.json 파일이 필요합니다."
                )

        _firebase_app = firebase_admin.initialize_app(cred)
        logger.info("Firebase Admin SDK 초기화 완료")

    except Exception as e:
        logger.error("Firebase 초기화 실패: %s", e)
        raise


def send_topic_message(
    topic: str,
    notification_title: str,
    notification_body: str,
    data: dict[str, str] | None = None,
) -> bool:
    """FCM Topic 메시지 발송

    Args:
        topic: FCM Topic 이름 (예: "bid_s_682608e4a04d8e01")
        notification_title: 알림 제목
        notification_body: 알림 본문
        data: 추가 데이터 페이로드 (모든 값은 문자열이어야 함)

    Returns:
        발송 성공 여부
    """
    _init_firebase()

    try:
        from firebase_admin import messaging

        # APNs 페이로드 (iOS)
        apns_config = messaging.APNSConfig(
            headers={
                "apns-push-type": "alert",
                "apns-priority": "10",
            },
            payload=messaging.APNSPayload(
                aps=messaging.Aps(
                    sound="default",
                    mutable_content=True,
                    content_available=True,
                ),
            ),
        )

        message = messaging.Message(
            topic=topic,
            notification=messaging.Notification(
                title=notification_title,
                body=notification_body,
            ),
            data=data or {},
            apns=apns_config,
        )

        response = messaging.send(message)
        logger.info("FCM 발송 성공: topic=%s, response=%s", topic, response)
        return True

    except Exception as e:
        logger.error("FCM 발송 실패: topic=%s, error=%s", topic, e)
        return False


def send_bid_notification(topic: str, payload: dict) -> bool:
    """입찰공고/사전규격 FCM 알림 발송

    Args:
        topic: FCM Topic 이름
        payload: formatter에서 생성한 페이로드 (notification + data)

    Returns:
        발송 성공 여부
    """
    notification = payload.get("notification", {})
    data = payload.get("data", {})

    success = send_topic_message(
        topic=topic,
        notification_title=notification.get("title", ""),
        notification_body=notification.get("body", ""),
        data=data,
    )

    if success:
        time.sleep(0.1)  # FCM 팬아웃 간격 (1,000 concurrent 제한 대비)

    return success


def send_android_data_notification(topic: str, payload: dict) -> bool:
    """Android 앱용 data-only FCM 알림을 발송합니다.

    Android 앱은 data-only 메시지를 직접 받아 로컬 히스토리에 저장한 뒤
    NotificationCompat 알림을 표시합니다. 기존 iOS notification/APNs 경로와
    분리하기 위해 별도 함수로 유지합니다.
    """
    _init_firebase()

    try:
        from firebase_admin import messaging

        notification = payload.get("notification", {})
        data = {
            key: "" if value is None else str(value)
            for key, value in payload.get("data", {}).items()
        }
        data["platform"] = "android"
        data["notificationTitle"] = str(notification.get("title", ""))
        data["notificationBody"] = str(notification.get("body", ""))

        message = messaging.Message(
            topic=topic,
            data=data,
            android=messaging.AndroidConfig(priority="high"),
        )

        response = messaging.send(message)
        logger.info("Android FCM data-only 발송 성공: topic=%s, response=%s", topic, response)
        time.sleep(0.1)
        return True

    except Exception as e:
        logger.error("Android FCM data-only 발송 실패: topic=%s, error=%s", topic, e)
        return False
