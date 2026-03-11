"""
사전규격정보서비스 API 클라이언트

사전규격공개 정보를 업종별로 조회합니다.
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any

import requests

from src.core.models import BidType, PreBidNotice
from src.utils.time_utils import get_query_range

logger = logging.getLogger(__name__)

BASE_URL = "https://apis.data.go.kr/1230000/ad/PubPrcureThngInfoService"


def _get_api_key() -> str:
    """사전규격 API 인증키 (별도 키 또는 공용 키)"""
    key = os.environ.get("G2B_PREBID_API_KEY", "")
    if not key:
        # 입찰공고 API 키와 동일한 키를 사용할 수 있음
        key = os.environ.get("G2B_API_KEY", "")
    if not key:
        raise ValueError(
            "G2B_PREBID_API_KEY 또는 G2B_API_KEY 환경변수가 설정되지 않았습니다."
        )
    return key


def _build_operation_name(bid_type: BidType) -> str:
    """사전규격 API 오퍼레이션 이름"""
    return f"getPublicPrcureThngInfo{bid_type.api_suffix}"


def _safe_str(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _parse_prebid_notice(item: dict[str, Any], bid_type: BidType) -> PreBidNotice:
    """API 응답 항목을 PreBidNotice 객체로 변환"""
    return PreBidNotice(
        prcure_no=_safe_str(
            item.get("bfSpecRgstNo") or item.get("prcureNo") or item.get("bidNtceNo")
        ),
        prcure_nm=_safe_str(
            item.get("prdctClsfcNoNm") or item.get("bidNtceNm") or item.get("prcureNm")
        ),
        ntce_instt_nm=_safe_str(
            item.get("ntceInsttNm") or item.get("rlDmndInsttNm")
        ),
        rcpt_dt=_safe_str(
            item.get("rcptDt") or item.get("rgstDt")
        ),
        opnn_reg_clse_dt=_safe_str(
            item.get("opnnRegClseDt") or item.get("bfSpecOpnnRcptClseDt")
        ),
        dtl_url=_safe_str(
            item.get("dtlUrl") or item.get("bidNtceDtlUrl") or ""
        ),
        bid_type=bid_type,
    )


def fetch_prebid_notices(
    bid_type: BidType,
    buffer_hours: int = 1,
    max_results: int = 999,
) -> list[PreBidNotice]:
    """사전규격 공개 목록 조회

    Args:
        bid_type: 입찰 유형
        buffer_hours: 조회 범위
        max_results: 최대 결과 수

    Returns:
        PreBidNotice 리스트
    """
    bgn_dt, end_dt = get_query_range(buffer_hours)
    operation = _build_operation_name(bid_type)
    url = f"{BASE_URL}/{operation}"

    params = {
        "ServiceKey": _get_api_key(),
        "type": "json",
        "pageNo": "1",
        "numOfRows": str(min(max_results, 999)),
        "inqryBgnDt": bgn_dt,
        "inqryEndDt": end_dt,
    }

    logger.info("사전규격 API 호출: %s (기간=%s~%s)", operation, bgn_dt, end_dt)

    try:
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()
    except requests.RequestException as e:
        logger.error("사전규격 API 호출 실패: %s", e)
        return []
    except ValueError as e:
        logger.error("사전규격 API 응답 파싱 오류: %s", e)
        return []

    # 응답 파싱
    resp = data.get("response", {})
    header = resp.get("header", {})
    if str(header.get("resultCode", "")) != "00":
        logger.warning(
            "사전규격 API 오류: %s", header.get("resultMsg", "알 수 없음")
        )
        return []

    body = resp.get("body", {})
    total_count = int(body.get("totalCount", 0))
    if total_count == 0:
        return []

    items = body.get("items", [])
    if isinstance(items, dict):
        items = [items]

    notices = [_parse_prebid_notice(item, bid_type) for item in items]

    logger.info("사전규격 조회 완료: %s → %d건", bid_type.display_name, len(notices))
    return notices
