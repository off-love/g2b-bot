"""
입찰공고정보서비스 API 클라이언트 (data.go.kr/15000766)

나라장터 입찰공고를 업종별(물품/용역/공사/외자)로 조회합니다.
키워드(bidNtceNm) 및 수요기관(dmndInsttCd)으로 API 레벨 필터링을 지원합니다.
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any

import requests

from src.core.models import BidNotice, BidType
from src.utils.time_utils import get_query_range

logger = logging.getLogger(__name__)

BASE_URL = "https://apis.data.go.kr/1230000/ad/BidPublicInfoService"


def _get_api_key() -> str:
    """API 인증키 조회"""
    key = os.environ.get("G2B_API_KEY", "")
    if not key:
        raise ValueError(
            "G2B_API_KEY 환경변수가 설정되지 않았습니다. "
            "공공데이터포털에서 '나라장터 입찰공고정보서비스' API 키를 발급받으세요."
        )
    return key


def _build_operation_name(bid_type: BidType) -> str:
    """업종별 API 오퍼레이션 이름 생성

    예: BidType.SERVICE → 'getBidPblancListInfoServc'
    """
    return f"getBidPblancListInfo{bid_type.api_suffix}"


def _parse_price(value: Any) -> int:
    """가격 문자열/숫자를 int로 안전하게 변환"""
    if value is None:
        return 0
    try:
        # '150000000' 또는 '150,000,000' 형태 지원
        return int(str(value).replace(",", "").strip() or "0")
    except (ValueError, TypeError):
        return 0


def _safe_str(value: Any) -> str:
    """None 또는 다른 타입을 빈 문자열로 안전 변환"""
    if value is None:
        return ""
    return str(value).strip()


def _parse_bid_notice(item: dict[str, Any], bid_type: BidType) -> BidNotice:
    """API 응답 항목을 BidNotice 데이터 객체로 변환"""
    return BidNotice(
        bid_ntce_no=_safe_str(item.get("bidNtceNo")),
        bid_ntce_ord=_safe_str(item.get("bidNtceOrd", "00")),
        bid_ntce_nm=_safe_str(item.get("bidNtceNm")),
        ntce_instt_nm=_safe_str(item.get("ntceInsttNm")),
        dmnd_instt_nm=_safe_str(
            item.get("dmndInsttNm") or item.get("dminsttNm")
        ),
        presmpt_prce=_parse_price(item.get("presmptPrce")),
        bid_ntce_dt=_safe_str(item.get("bidNtceDt")),
        bid_clse_dt=_safe_str(item.get("bidClseDt")),
        openg_dt=_safe_str(item.get("opengDt")),
        bid_ntce_dtl_url=_safe_str(item.get("bidNtceDtlUrl")),
        prtcpt_psbl_rgn_nm=_safe_str(item.get("prtcptPsblRgnNm")),
        bid_type=bid_type,
        ntce_div_nm=_safe_str(item.get("ntceDivNm")),
        bid_methd_nm=_safe_str(item.get("bidMethdNm")),
        cntrct_methd_nm=_safe_str(item.get("cntrctMthdNm")),
        sucsfbid_methd_nm=_safe_str(item.get("sucsfbidMthdNm")),
        ntce_instt_cd=_safe_str(item.get("ntceInsttCd")),
        dmnd_instt_cd=_safe_str(
            item.get("dmndInsttCd") or item.get("dminsttCd")
        ),
        asign_bdgt_amt=_parse_price(item.get("asignBdgtAmt")),
        bid_begin_dt=_safe_str(item.get("bidBeginDt")),
        rbid_permsn_yn=_safe_str(item.get("rbidPermsnYn")),
    )


def _fetch_page(
    bid_type: BidType,
    page_no: int = 1,
    num_of_rows: int = 999,
    inqry_bgn_dt: str = "",
    inqry_end_dt: str = "",
    bid_ntce_nm: str = "",
    dmnd_instt_cd: str = "",
) -> dict[str, Any]:
    """API 한 페이지 호출

    Returns:
        API 응답 JSON (dict)

    Raises:
        requests.RequestException: HTTP 오류 시
        ValueError: 응답 파싱 오류 시
    """
    operation = _build_operation_name(bid_type)
    url = f"{BASE_URL}/{operation}"

    params: dict[str, Any] = {
        "ServiceKey": _get_api_key(),
        "type": "json",
        "pageNo": str(page_no),
        "numOfRows": str(num_of_rows),
        "inqryDiv": "1",  # 공고일시 기준
    }

    if inqry_bgn_dt:
        params["inqryBgnDt"] = inqry_bgn_dt
    if inqry_end_dt:
        params["inqryEndDt"] = inqry_end_dt
    if bid_ntce_nm:
        params["bidNtceNm"] = bid_ntce_nm
    if dmnd_instt_cd:
        params["dmndInsttCd"] = dmnd_instt_cd

    logger.info(
        "API 호출: %s (키워드=%s, 기관=%s, 기간=%s~%s, page=%d)",
        operation, bid_ntce_nm or "전체", dmnd_instt_cd or "전체",
        inqry_bgn_dt, inqry_end_dt, page_no,
    )

    response = requests.get(url, params=params, timeout=30)
    response.raise_for_status()

    data = response.json()
    return data


def _extract_items(response_data: dict[str, Any]) -> tuple[list[dict], int]:
    """API 응답에서 아이템 목록과 전체 건수를 추출

    나라장터 API 응답 구조:
    {
      "response": {
        "body": {
          "items": [...],
          "totalCount": N
        },
        "header": {
          "resultCode": "00",
          "resultMsg": "NORMAL SERVICE."
        }
      }
    }
    """
    response = response_data.get("response", {})
    header = response.get("header", {})
    result_code = str(header.get("resultCode", ""))

    if result_code != "00":
        result_msg = header.get("resultMsg", "알 수 없는 오류")
        logger.warning("API 오류 응답: code=%s, msg=%s", result_code, result_msg)
        return [], 0

    body = response.get("body", {})
    total_count = int(body.get("totalCount", 0))

    if total_count == 0:
        return [], 0

    items = body.get("items", [])

    # items가 dict 형태일 수 있음 (단일 결과)
    if isinstance(items, dict):
        items = [items]

    return items, total_count


def fetch_bid_notices(
    bid_type: BidType,
    keyword: str = "",
    dmnd_instt_cd: str = "",
    buffer_hours: int = 1,
    max_results: int = 999,
) -> list[BidNotice]:
    """입찰공고 목록을 조회합니다.

    Args:
        bid_type: 입찰 유형 (용역/물품/공사/외자)
        keyword: 공고명 키워드 (bidNtceNm 파라미터)
        dmnd_instt_cd: 수요기관 코드 (API 레벨 필터)
        buffer_hours: 조회 범위 (최근 N시간)
        max_results: 최대 결과 수

    Returns:
        BidNotice 리스트
    """
    bgn_dt, end_dt = get_query_range(buffer_hours)
    all_notices: list[BidNotice] = []
    page_no = 1

    while True:
        try:
            data = _fetch_page(
                bid_type=bid_type,
                page_no=page_no,
                num_of_rows=min(max_results, 999),
                inqry_bgn_dt=bgn_dt,
                inqry_end_dt=end_dt,
                bid_ntce_nm=keyword,
                dmnd_instt_cd=dmnd_instt_cd,
            )

            items, total_count = _extract_items(data)

            if not items:
                break

            for item in items:
                notice = _parse_bid_notice(item, bid_type)
                all_notices.append(notice)

            logger.info(
                "  → %d건 조회 (페이지 %d, 전체 %d건)",
                len(items), page_no, total_count,
            )

            # 다음 페이지가 있는지 확인
            if len(all_notices) >= total_count or len(all_notices) >= max_results:
                break

            page_no += 1
            time.sleep(0.3)  # API 부하 방지

        except requests.RequestException as e:
            logger.error("API 호출 실패 (page=%d): %s", page_no, e)
            break
        except (ValueError, KeyError) as e:
            logger.error("API 응답 파싱 오류 (page=%d): %s", page_no, e)
            break

    logger.info(
        "조회 완료: %s %s → %d건",
        bid_type.display_name, keyword or "(전체)", len(all_notices),
    )
    return all_notices


def fetch_bid_notices_multi_keywords(
    bid_type: BidType,
    keywords: list[str],
    dmnd_instt_cd: str = "",
    buffer_hours: int = 1,
    max_results: int = 999,
) -> list[BidNotice]:
    """여러 키워드로 OR 조건 조회 후 결과를 합칩니다.

    각 키워드로 개별 API 호출 → 결과 합침 → 중복 제거 (bidNtceNo+bidNtceOrd 기준)

    Args:
        bid_type: 입찰 유형
        keywords: OR 조건 키워드 목록
        dmnd_instt_cd: 수요기관 코드
        buffer_hours: 조회 범위
        max_results: 키워드당 최대 결과 수

    Returns:
        중복 제거된 BidNotice 리스트
    """
    if not keywords:
        # 키워드 없으면 전체 조회
        return fetch_bid_notices(
            bid_type=bid_type,
            dmnd_instt_cd=dmnd_instt_cd,
            buffer_hours=buffer_hours,
            max_results=max_results,
        )

    seen_keys: set[str] = set()
    merged: list[BidNotice] = []

    for keyword in keywords:
        notices = fetch_bid_notices(
            bid_type=bid_type,
            keyword=keyword,
            dmnd_instt_cd=dmnd_instt_cd,
            buffer_hours=buffer_hours,
            max_results=max_results,
        )
        for notice in notices:
            if notice.unique_key not in seen_keys:
                seen_keys.add(notice.unique_key)
                merged.append(notice)

        time.sleep(0.3)  # 키워드 간 간격

    logger.info(
        "OR 조건 통합: %s 키워드 %d개 → 중복 제거 후 %d건",
        bid_type.display_name, len(keywords), len(merged),
    )
    return merged
