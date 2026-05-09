#!/usr/bin/env python3
"""Keyword notification delivery diagnostic.

This script does not send notifications. It prints the exact iOS/Android topics
for a keyword/category and counts matching records in data/state.json.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.core.topic_hasher import keyword_hash
from src.storage.state_manager import DEFAULT_STATE_PATH

CATEGORY_LABELS = {
    "s": "용역",
    "c": "공사",
    "g": "물품",
    "f": "외자",
}


def build_topics(keyword: str, category: str) -> dict[str, str]:
    digest = keyword_hash(keyword)
    return {
        "hash": digest,
        "bid": f"bid_{category}_{digest}",
        "prebid": f"pre_{category}_{digest}",
        "android_bid": f"and_bid_{category}_{digest}",
        "android_prebid": f"and_pre_{category}_{digest}",
    }


def find_records(
    state: dict[str, Any],
    *,
    section: str,
    topic: str,
    date: str | None = None,
) -> list[tuple[str, dict[str, Any]]]:
    matches: list[tuple[str, dict[str, Any]]] = []
    for key, record in state.get(section, {}).items():
        if not isinstance(record, dict):
            continue
        if record.get("topic") != topic and not key.startswith(f"{topic}:"):
            continue
        notified_at = str(record.get("notified_at", ""))
        if date and not notified_at.startswith(date):
            continue
        matches.append((key, record))
    return sorted(matches, key=lambda item: str(item[1].get("notified_at", "")))


def build_report(
    keyword: str,
    category: str,
    state: dict[str, Any],
    *,
    date: str | None = None,
) -> dict[str, Any]:
    topics = build_topics(keyword, category)
    bid_records = find_records(
        state,
        section="notified_bids",
        topic=topics["bid"],
        date=date,
    )
    prebid_records = find_records(
        state,
        section="notified_prebids",
        topic=topics["prebid"],
        date=date,
    )

    return {
        "keyword": keyword,
        "category": category,
        "category_label": CATEGORY_LABELS.get(category, category),
        "date": date,
        "last_check": state.get("last_check", ""),
        "topics": topics,
        "bid_count": len(bid_records),
        "prebid_count": len(prebid_records),
        "total_count": len(bid_records) + len(prebid_records),
        "bid_records": bid_records,
        "prebid_records": prebid_records,
    }


def print_report(report: dict[str, Any]) -> None:
    topics = report["topics"]
    print(f"keyword={report['keyword']}")
    print(f"category={report['category_label']}({report['category']})")
    if report["date"]:
        print(f"date={report['date']}")
    print(f"last_check={report['last_check']}")
    print(f"hash={topics['hash']}")
    print(f"ios_bid_topic={topics['bid']}")
    print(f"ios_prebid_topic={topics['prebid']}")
    print(f"android_bid_topic={topics['android_bid']}")
    print(f"android_prebid_topic={topics['android_prebid']}")
    print(f"bid_count={report['bid_count']}")
    print(f"prebid_count={report['prebid_count']}")
    print(f"total_count={report['total_count']}")

    for label, records in (
        ("bid", report["bid_records"]),
        ("prebid", report["prebid_records"]),
    ):
        for key, record in records:
            print(f"{label}\t{record.get('notified_at', '')}\t{key}")


def load_state(path: Path) -> dict[str, Any]:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("keyword", help="Keyword to diagnose, for example: 측량")
    parser.add_argument(
        "--category",
        choices=sorted(CATEGORY_LABELS),
        default="s",
        help="Bid category topic suffix: s=용역, c=공사, g=물품, f=외자",
    )
    parser.add_argument(
        "--date",
        help="Filter state records by KST date prefix, for example: 2026-05-08",
    )
    parser.add_argument(
        "--state",
        type=Path,
        default=DEFAULT_STATE_PATH,
        help="Path to state.json",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = build_report(
        args.keyword,
        args.category,
        load_state(args.state),
        date=args.date,
    )
    print_report(report)


if __name__ == "__main__":
    main()
