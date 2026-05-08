"""
데이터 모델 — 입찰공고, 사전규격, 키워드 설정

기존 나라장터_입찰공고/사전규격 프로젝트에서 재활용.
FCM 발송에 필요한 최소 모델만 유지합니다.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class BidType(str, Enum):
    """입찰 유형 (업종)"""

    SERVICE = "service"
    GOODS = "goods"
    CONSTRUCTION = "construction"
    FOREIGN = "foreign"

    @property
    def api_suffix(self) -> str:
        mapping = {
            BidType.SERVICE: "Servc",
            BidType.GOODS: "Thng",
            BidType.CONSTRUCTION: "Cnstwk",
            BidType.FOREIGN: "Frgcpt",
        }
        return mapping[self]

    @property
    def display_name(self) -> str:
        mapping = {
            BidType.SERVICE: "용역",
            BidType.GOODS: "물품",
            BidType.CONSTRUCTION: "공사",
            BidType.FOREIGN: "외자",
        }
        return mapping[self]

    @property
    def topic_category(self) -> str:
        mapping = {
            BidType.SERVICE: "s",
            BidType.GOODS: "g",
            BidType.CONSTRUCTION: "c",
            BidType.FOREIGN: "f",
        }
        return mapping[self]


class NoticeType(str, Enum):
    """공고 종류"""

    BID = "bid"
    PREBID = "prebid"


@dataclass
class BidNotice:
    """입찰공고 정보"""

    bid_ntce_no: str
    bid_ntce_ord: str
    bid_ntce_nm: str
    ntce_instt_nm: str
    dmnd_instt_nm: str
    presmpt_prce: int
    bid_ntce_dt: str
    bid_clse_dt: str
    openg_dt: str
    bid_ntce_dtl_url: str
    prtcpt_psbl_rgn_nm: str
    bid_type: BidType
    ntce_div_nm: str = ""
    bid_methd_nm: str = ""
    cntrct_methd_nm: str = ""
    sucsfbid_methd_nm: str = ""
    ntce_instt_cd: str = ""
    dmnd_instt_cd: str = ""
    asign_bdgt_amt: int = 0
    bid_begin_dt: str = ""
    rbid_permsn_yn: str = ""

    @property
    def unique_key(self) -> str:
        return f"{self.bid_ntce_no}-{self.bid_ntce_ord}"

    @property
    def price_display(self) -> str:
        if self.presmpt_prce <= 0:
            return "미정"
        return f"{self.presmpt_prce:,}원"


@dataclass
class PreBidNotice:
    """사전규격공개 정보"""

    prcure_no: str
    prcure_nm: str
    ntce_instt_nm: str
    rcpt_dt: str
    opnn_reg_clse_dt: str
    asign_bdgt_amt: int
    dtl_url: str
    bid_type: BidType
    prcure_div: str = ""
    rgst_instt_nm: str = ""
    prcure_way: str = ""

    @property
    def unique_key(self) -> str:
        return f"{self.prcure_no}"

    @property
    def price_display(self) -> str:
        if self.asign_bdgt_amt <= 0:
            return "미정"
        return f"{self.asign_bdgt_amt:,}원"


@dataclass
class KeywordConfig:
    """키워드 설정 (keywords.json에서 로드)"""

    original: str
    keyword_hash: str
    exclude: list[str] = field(default_factory=list)
    bid_types: list[str] = field(
        default_factory=lambda: ["service", "goods", "construction"]
    )

    @property
    def bid_type_enums(self) -> list[BidType]:
        mapping = {
            "service": BidType.SERVICE,
            "goods": BidType.GOODS,
            "construction": BidType.CONSTRUCTION,
            "foreign": BidType.FOREIGN,
        }
        return [mapping[bt] for bt in self.bid_types if bt in mapping]

    def get_topic(self, noti_type: str, bid_type: BidType) -> str:
        return f"{noti_type}_{bid_type.topic_category}_{self.keyword_hash}"

    def get_android_topic(self, noti_type: str, bid_type: BidType) -> str:
        """Android 전용 data-only FCM topic.

        기존 iOS topic과 분리하기 위해 `and_` prefix를 붙입니다.
        """
        return f"and_{noti_type}_{bid_type.topic_category}_{self.keyword_hash}"


@dataclass
class NotifiedRecord:
    """알림 이력 기록"""

    notified_at: str
    keyword: str
    notice_type: str = "bid"
