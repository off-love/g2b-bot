"""
API 클라이언트 호출량 제한 테스트
"""

from src.api import bid_client, prebid_client
from src.core.models import BidType


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


def _api_payload(item, total_count=3):
    return {
        "response": {
            "header": {"resultCode": "00"},
            "body": {
                "totalCount": total_count,
                "items": [item],
            },
        }
    }


def test_fetch_bid_notices_stops_at_max_pages(monkeypatch):
    calls = []

    def fake_get(url, params, timeout):
        calls.append(params["pageNo"])
        page_no = params["pageNo"]
        return FakeResponse(
            _api_payload(
                {
                    "bidNtceNo": f"R26BK{page_no}",
                    "bidNtceOrd": "000",
                    "bidNtceNm": f"지적측량 용역 {page_no}",
                    "ntceInsttNm": "서울특별시",
                    "dmndInsttNm": "서울특별시",
                    "bidNtceDt": "2026-04-20 11:17:19",
                }
            )
        )

    monkeypatch.setattr(bid_client, "_get_api_key", lambda: "test-key")
    monkeypatch.setattr(bid_client.requests, "get", fake_get)
    monkeypatch.setattr(bid_client.time, "sleep", lambda seconds: None)

    notices = bid_client.fetch_bid_notices(
        BidType.SERVICE,
        keyword="",
        max_results=999 * 3,
        max_pages=2,
        inqry_bgn_dt="202604201100",
        inqry_end_dt="202604201200",
    )

    assert calls == ["1", "2"]
    assert [notice.unique_key for notice in notices] == ["R26BK1-000", "R26BK2-000"]


def test_fetch_prebid_notices_stops_at_max_pages(monkeypatch):
    calls = []

    def fake_get(url, params, timeout):
        calls.append(params["pageNo"])
        page_no = params["pageNo"]
        return FakeResponse(
            _api_payload(
                {
                    "bfSpecRgstNo": f"P20260420{page_no}",
                    "prcureNm": f"지적측량 사전규격 {page_no}",
                    "orderInsttNm": "서울특별시",
                    "rgstDt": "2026-04-20 11:17:19",
                }
            )
        )

    monkeypatch.setattr(prebid_client, "_get_api_key", lambda: "test-key")
    monkeypatch.setattr(prebid_client.requests, "get", fake_get)
    monkeypatch.setattr(prebid_client.time, "sleep", lambda seconds: None)

    notices = prebid_client.fetch_prebid_notices(
        BidType.SERVICE,
        keyword="",
        max_results=999 * 3,
        max_pages=2,
        inqry_bgn_dt="202604201100",
        inqry_end_dt="202604201200",
    )

    assert calls == ["1", "2"]
    assert [notice.unique_key for notice in notices] == ["P202604201", "P202604202"]
