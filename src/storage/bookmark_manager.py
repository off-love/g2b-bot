"""
북마크 관리자

data/bookmarks.json 파일에 북마크를 저장/조회/삭제합니다.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from src.core.models import BidNotice, BookmarkItem
from src.utils.time_utils import now_iso

logger = logging.getLogger(__name__)

DEFAULT_BOOKMARKS_PATH = Path(__file__).parent.parent.parent / "data" / "bookmarks.json"


def _ensure_file(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"items": []}, f, ensure_ascii=False, indent=2)


def load_bookmarks(path: Path | None = None) -> list[BookmarkItem]:
    """북마크 목록 로드"""
    if path is None:
        path = DEFAULT_BOOKMARKS_PATH
    _ensure_file(path)
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    items = []
    for item in data.get("items", []):
        items.append(BookmarkItem(
            bid_no=item.get("bid_no", ""),
            name=item.get("name", ""),
            org=item.get("org", ""),
            demand_org=item.get("demand_org", ""),
            price=int(item.get("price", 0)),
            close_date=item.get("close_date", ""),
            url=item.get("url", ""),
            saved_at=item.get("saved_at", ""),
            profile=item.get("profile", ""),
            notice_type=item.get("notice_type", "bid"),
            notes=item.get("notes", ""),
        ))
    return items


def save_bookmarks(items: list[BookmarkItem], path: Path | None = None) -> None:
    """북마크 목록 저장"""
    if path is None:
        path = DEFAULT_BOOKMARKS_PATH
    path.parent.mkdir(parents=True, exist_ok=True)

    data = {"items": []}
    for item in items:
        data["items"].append({
            "bid_no": item.bid_no,
            "name": item.name,
            "org": item.org,
            "demand_org": item.demand_org,
            "price": item.price,
            "close_date": item.close_date,
            "url": item.url,
            "saved_at": item.saved_at,
            "profile": item.profile,
            "notice_type": item.notice_type,
            "notes": item.notes,
        })

    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def add_bookmark_from_bid(notice: BidNotice, profile_name: str) -> BookmarkItem:
    """입찰공고를 북마크에 추가"""
    items = load_bookmarks()

    # 중복 체크
    for item in items:
        if item.bid_no == notice.unique_key:
            logger.info("이미 북마크에 존재: %s", notice.unique_key)
            return item

    bookmark = BookmarkItem(
        bid_no=notice.unique_key,
        name=notice.bid_ntce_nm,
        org=notice.ntce_instt_nm,
        demand_org=notice.dmnd_instt_nm,
        price=notice.presmpt_prce,
        close_date=notice.bid_clse_dt,
        url=notice.bid_ntce_dtl_url,
        saved_at=now_iso(),
        profile=profile_name,
        notice_type="bid",
    )

    items.append(bookmark)
    save_bookmarks(items)
    logger.info("북마크 추가: %s", notice.bid_ntce_nm)
    return bookmark



def remove_bookmark(bid_no: str) -> bool:
    """북마크 삭제"""
    items = load_bookmarks()
    original_count = len(items)
    items = [item for item in items if item.bid_no != bid_no]

    if len(items) < original_count:
        save_bookmarks(items)
        logger.info("북마크 삭제: %s", bid_no)
        return True
    return False
