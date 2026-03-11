"""
필터링 엔진 유닛 테스트
"""

import pytest

from src.core.filter import filter_bid_notices, filter_prebid_notices
from src.core.models import (
    AlertProfile,
    BidNotice,
    BidType,
    DemandAgencyConfig,
    KeywordConfig,
    PreBidNotice,
    PriceRange,
)


def _make_bid(
    name: str = "테스트 공고",
    dmnd_nm: str = "테스트기관",
    region: str = "서울",
    price: int = 100_000_000,
    bid_type: BidType = BidType.SERVICE,
) -> BidNotice:
    """테스트용 BidNotice 생성"""
    return BidNotice(
        bid_ntce_no="T-001",
        bid_ntce_ord="00",
        bid_ntce_nm=name,
        ntce_instt_nm="공고기관",
        dmnd_instt_nm=dmnd_nm,
        presmpt_prce=price,
        bid_ntce_dt="2026/03/11 14:00:00",
        bid_clse_dt="2026/03/25 10:00:00",
        openg_dt="2026/03/25 11:00:00",
        bid_ntce_dtl_url="https://example.com",
        prtcpt_psbl_rgn_nm=region,
        bid_type=bid_type,
    )


def _make_profile(**kwargs) -> AlertProfile:
    """테스트용 AlertProfile 생성"""
    defaults = {
        "name": "테스트 프로필",
        "bid_types": [BidType.SERVICE],
        "keywords": KeywordConfig(),
        "demand_agencies": DemandAgencyConfig(),
        "regions": [],
        "price_range": PriceRange(),
    }
    defaults.update(kwargs)
    return AlertProfile(**defaults)


class TestKeywordFilter:
    """키워드 필터링 테스트"""

    def test_no_keywords_passes_all(self):
        """키워드 미설정 시 모든 공고 통과"""
        profile = _make_profile()
        notices = [_make_bid(name="지적측량 용역")]
        result = filter_bid_notices(notices, profile)
        assert len(result) == 1

    def test_exclude_keyword(self):
        """제외 키워드 포함 시 제외"""
        profile = _make_profile(
            keywords=KeywordConfig(exclude=["취소공고"])
        )
        notices = [
            _make_bid(name="지적측량 업무 위탁용역"),
            _make_bid(name="지적측량 취소공고"),
        ]
        result = filter_bid_notices(notices, profile)
        assert len(result) == 1
        assert result[0].bid_ntce_nm == "지적측량 업무 위탁용역"

    def test_and_keywords(self):
        """AND 키워드: 모두 포함해야 통과"""
        profile = _make_profile(
            keywords=KeywordConfig(and_keywords=["지적", "측량"])
        )
        notices = [
            _make_bid(name="지적측량 업무"),
            _make_bid(name="지적 확정측량"),
            _make_bid(name="건설공사"),
        ]
        result = filter_bid_notices(notices, profile)
        assert len(result) == 2

    def test_exclude_case_insensitive(self):
        """대소문자 무관 제외"""
        profile = _make_profile(
            keywords=KeywordConfig(exclude=["CANCEL"])
        )
        notices = [_make_bid(name="Test Cancel Notice")]
        result = filter_bid_notices(notices, profile)
        assert len(result) == 0


class TestDemandAgencyFilter:
    """수요기관 필터 테스트"""

    def test_no_agency_passes_all(self):
        """수요기관 미설정 시 전체 통과"""
        profile = _make_profile()
        notices = [_make_bid(dmnd_nm="아무기관")]
        result = filter_bid_notices(notices, profile)
        assert len(result) == 1

    def test_agency_by_name_partial_match(self):
        """수요기관명 부분 일치"""
        profile = _make_profile(
            demand_agencies=DemandAgencyConfig(by_name=["서울대학교"])
        )
        notices = [
            _make_bid(dmnd_nm="서울대학교 산학협력단"),
            _make_bid(dmnd_nm="한국국토정보공사"),
        ]
        result = filter_bid_notices(notices, profile)
        assert len(result) == 1
        assert "서울대학교" in result[0].dmnd_instt_nm


class TestRegionFilter:
    """지역 필터 테스트"""

    def test_no_region_passes_all(self):
        """지역 미설정 시 전체 통과"""
        profile = _make_profile()
        notices = [_make_bid(region="부산")]
        result = filter_bid_notices(notices, profile)
        assert len(result) == 1

    def test_region_match(self):
        """지역 매칭"""
        profile = _make_profile(regions=["서울", "경기"])
        notices = [
            _make_bid(region="서울특별시"),
            _make_bid(region="경기도"),
            _make_bid(region="부산광역시"),
            _make_bid(region=""),  # 지역 정보 없으면 통과
        ]
        result = filter_bid_notices(notices, profile)
        assert len(result) == 3  # 서울, 경기, 빈 값


class TestPriceFilter:
    """금액 범위 필터 테스트"""

    def test_no_price_range_passes_all(self):
        """금액 범위 미설정 시 전체 통과"""
        profile = _make_profile()
        notices = [_make_bid(price=999_999_999)]
        result = filter_bid_notices(notices, profile)
        assert len(result) == 1

    def test_min_price(self):
        """최소 금액 필터"""
        profile = _make_profile(
            price_range=PriceRange(min_price=50_000_000)
        )
        notices = [
            _make_bid(price=100_000_000),  # 통과
            _make_bid(price=10_000_000),   # 미달
            _make_bid(price=0),            # 미정 → 통과
        ]
        result = filter_bid_notices(notices, profile)
        assert len(result) == 2

    def test_max_price(self):
        """최대 금액 필터"""
        profile = _make_profile(
            price_range=PriceRange(max_price=200_000_000)
        )
        notices = [
            _make_bid(price=100_000_000),  # 통과
            _make_bid(price=500_000_000),  # 초과
        ]
        result = filter_bid_notices(notices, profile)
        assert len(result) == 1

    def test_min_max_range(self):
        """최소~최대 범위"""
        profile = _make_profile(
            price_range=PriceRange(min_price=10_000_000, max_price=500_000_000)
        )
        notices = [
            _make_bid(price=150_000_000),   # 범위 내
            _make_bid(price=5_000_000),     # 미달
            _make_bid(price=1_000_000_000), # 초과
        ]
        result = filter_bid_notices(notices, profile)
        assert len(result) == 1


class TestCombinedFilter:
    """복합 필터 테스트"""

    def test_all_filters_combined(self):
        """모든 필터 조합"""
        profile = _make_profile(
            keywords=KeywordConfig(
                and_keywords=["측량"],
                exclude=["취소"],
            ),
            demand_agencies=DemandAgencyConfig(by_name=["국토정보"]),
            regions=["서울"],
            price_range=PriceRange(min_price=50_000_000),
        )
        notices = [
            _make_bid(
                name="지적측량 위탁",
                dmnd_nm="한국국토정보공사",
                region="서울",
                price=100_000_000,
            ),  # 모든 조건 만족 ✅
            _make_bid(
                name="지적측량 취소",
                dmnd_nm="한국국토정보공사",
                region="서울",
                price=100_000_000,
            ),  # 제외 키워드 ❌
            _make_bid(
                name="지적측량 위탁",
                dmnd_nm="서울시청",
                region="서울",
                price=100_000_000,
            ),  # 수요기관 불일치 ❌
        ]
        result = filter_bid_notices(notices, profile)
        assert len(result) == 1
        assert result[0].bid_ntce_nm == "지적측량 위탁"


class TestPreBidFilter:
    """사전규격 필터링 테스트"""

    def test_prebid_keyword_filter(self):
        """사전규격 키워드 OR 필터"""
        profile = _make_profile(
            keywords=KeywordConfig(or_keywords=["지적측량", "확정측량"])
        )
        prebids = [
            PreBidNotice(
                prcure_no="P001", prcure_nm="지적측량 사전규격",
                ntce_instt_nm="기관", rcpt_dt="2026-03-11",
                opnn_reg_clse_dt="2026-03-18", dtl_url="", bid_type=BidType.SERVICE,
            ),
            PreBidNotice(
                prcure_no="P002", prcure_nm="건설공사 사전규격",
                ntce_instt_nm="기관", rcpt_dt="2026-03-11",
                opnn_reg_clse_dt="2026-03-18", dtl_url="", bid_type=BidType.SERVICE,
            ),
        ]
        result = filter_prebid_notices(prebids, profile)
        assert len(result) == 1
        assert "지적측량" in result[0].prcure_nm
