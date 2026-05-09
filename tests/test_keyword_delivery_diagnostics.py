from scripts.diagnose_keyword_delivery import build_report, build_topics


def test_build_topics_matches_ios_contract_for_keyword():
    topics = build_topics("측량", "s")

    assert topics == {
        "hash": "5f66b02e337d9504",
        "bid": "bid_s_5f66b02e337d9504",
        "prebid": "pre_s_5f66b02e337d9504",
        "android_bid": "and_bid_s_5f66b02e337d9504",
        "android_prebid": "and_pre_s_5f66b02e337d9504",
    }


def test_build_report_counts_exact_topic_records_for_date():
    state = {
        "last_check": "2026-05-08T20:56:35.711222+09:00",
        "notified_bids": {
            "bid_s_5f66b02e337d9504:R26BK01510475-000": {
                "notified_at": "2026-05-08T12:43:41.839107+09:00",
                "keyword": "측량",
                "notice_type": "bid",
                "topic": "bid_s_5f66b02e337d9504",
            },
            "bid_s_5f66b02e337d9504:R26BK01511093-000": {
                "notified_at": "2026-05-08T15:05:26.473147+09:00",
                "keyword": "측량",
                "notice_type": "bid",
                "topic": "bid_s_5f66b02e337d9504",
            },
            "bid_g_5f66b02e337d9504:R26BK01508103-000": {
                "notified_at": "2026-05-08T10:00:00+09:00",
                "keyword": "측량",
                "notice_type": "bid",
                "topic": "bid_g_5f66b02e337d9504",
            },
        },
        "notified_prebids": {
            "pre_s_5f66b02e337d9504:R26BD00224791": {
                "notified_at": "2026-05-08T16:55:54.309486+09:00",
                "keyword": "측량",
                "notice_type": "prebid",
                "topic": "pre_s_5f66b02e337d9504",
            },
            "pre_s_5f66b02e337d9504:R26BD00220000": {
                "notified_at": "2026-05-07T16:55:54.309486+09:00",
                "keyword": "측량",
                "notice_type": "prebid",
                "topic": "pre_s_5f66b02e337d9504",
            },
        },
    }

    report = build_report("측량", "s", state, date="2026-05-08")

    assert report["last_check"] == "2026-05-08T20:56:35.711222+09:00"
    assert report["bid_count"] == 2
    assert report["prebid_count"] == 1
    assert report["total_count"] == 3
    assert [key for key, _ in report["bid_records"]] == [
        "bid_s_5f66b02e337d9504:R26BK01510475-000",
        "bid_s_5f66b02e337d9504:R26BK01511093-000",
    ]
