"""
나라장터 입찰공고 알림 서비스 - 데이터 모델

입찰공고, 알림 프로필 등 핵심 데이터 구조를 정의합니다.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class BidType(str, Enum):
    """입찰 유형 (업종)"""
    SERVICE = "service"           # 용역
    GOODS = "goods"               # 물품
    CONSTRUCTION = "construction" # 공사
    FOREIGN = "foreign"           # 외자

    @property
    def api_suffix(self) -> str:
        """입찰공고정보서비스 API 오퍼레이션 접미사"""
        mapping = {
            BidType.SERVICE: "Servc",
            BidType.GOODS: "Thng",
            BidType.CONSTRUCTION: "Cnstwk",
            BidType.FOREIGN: "Frgcpt",
        }
        return mapping[self]

    @property
    def display_name(self) -> str:
        """한글 표시명"""
        mapping = {
            BidType.SERVICE: "용역",
            BidType.GOODS: "물품",
            BidType.CONSTRUCTION: "공사",
            BidType.FOREIGN: "외자",
        }
        return mapping[self]


class NoticeType(str, Enum):
    """공고 종류"""
    BID = "bid"          # 입찰공고


@dataclass
class BidNotice:
    """입찰공고 정보"""
    bid_ntce_no: str              # 입찰공고번호
    bid_ntce_ord: str             # 입찰공고차수
    bid_ntce_nm: str              # 입찰공고명
    ntce_instt_nm: str            # 공고기관명
    dmnd_instt_nm: str            # 수요기관명
    presmpt_prce: int             # 추정가격 (원)
    bid_ntce_dt: str              # 공고일시
    bid_clse_dt: str              # 입찰마감일시
    openg_dt: str                 # 개찰일시
    bid_ntce_dtl_url: str         # 공고 상세 URL
    prtcpt_psbl_rgn_nm: str       # 참가가능지역명
    bid_type: BidType             # 입찰 유형
    ntce_div_nm: str = ""         # 공고구분명 (일반/긴급 등)
    bid_methd_nm: str = ""        # 입찰방식명
    cntrct_methd_nm: str = ""     # 계약방법명
    sucsfbid_methd_nm: str = ""   # 낙찰방법명
    ntce_instt_cd: str = ""       # 공고기관코드
    dmnd_instt_cd: str = ""       # 수요기관코드
    asign_bdgt_amt: int = 0       # 배정예산액
    bid_begin_dt: str = ""        # 입찰개시일시
    rbid_permsn_yn: str = ""      # 재입찰허용여부

    @property
    def unique_key(self) -> str:
        """중복 판별용 고유 키 (공고번호 + 차수)"""
        return f"{self.bid_ntce_no}-{self.bid_ntce_ord}"

    @property
    def price_display(self) -> str:
        """가격 표시 포맷 (예: 150,000,000원)"""
        if self.presmpt_prce <= 0:
            return "미정"
        return f"{self.presmpt_prce:,}원"




@dataclass
class KeywordConfig:
    """키워드 검색 설정"""
    or_keywords: list[str] = field(default_factory=list)   # OR 조건
    and_keywords: list[str] = field(default_factory=list)   # AND 조건
    exclude: list[str] = field(default_factory=list)        # 제외 키워드


@dataclass
class DemandAgencyConfig:
    """수요기관 필터 설정"""
    by_code: list[str] = field(default_factory=list)  # 기관코드 (API 레벨)
    by_name: list[str] = field(default_factory=list)  # 기관명 (코드 레벨)


@dataclass
class PriceRange:
    """금액 범위"""
    min_price: int = 0  # 0이면 하한 없음
    max_price: int = 0  # 0이면 상한 없음

    def contains(self, price: int) -> bool:
        """가격이 범위 내에 있는지 판별"""
        if price <= 0:
            # 추정가격이 없는 경우 필터 통과
            return True
        if self.min_price > 0 and price < self.min_price:
            return False
        if self.max_price > 0 and price > self.max_price:
            return False
        return True


@dataclass
class AlertProfile:
    """알림 프로필"""
    name: str                                          # 프로필 이름
    enabled: bool = True                               # 활성 여부
    bid_types: list[BidType] = field(default_factory=list)
    keywords: KeywordConfig = field(default_factory=KeywordConfig)
    demand_agencies: DemandAgencyConfig = field(default_factory=DemandAgencyConfig)
    regions: list[str] = field(default_factory=list)
    price_range: PriceRange = field(default_factory=PriceRange)



@dataclass
class GlobalSettings:
    """전역 설정"""
    check_interval_minutes: int = 30
    query_buffer_hours: int = 1
    max_results_per_page: int = 999
    timezone: str = "Asia/Seoul"


@dataclass
class BookmarkItem:
    """북마크 항목"""
    bid_no: str                   # 공고번호-차수
    name: str                     # 공고명
    org: str                      # 공고기관명
    demand_org: str               # 수요기관명
    price: int                    # 추정가격
    close_date: str               # 마감일시
    url: str                      # 상세 URL
    saved_at: str                 # 저장 시각
    profile: str                  # 매칭된 프로필명
    notice_type: str = "bid"      # 공고 종류
    notes: str = ""               # 사용자 메모


@dataclass
class NotifiedRecord:
    """알림 이력 기록"""
    notified_at: str              # 알림 발송 시각
    profile: str                  # 프로필명
    notice_type: str = "bid"      # 공고 종류
