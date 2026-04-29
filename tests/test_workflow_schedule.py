"""
GitHub Actions 스케줄 설정 테스트
"""

from pathlib import Path

import yaml


WORKFLOW_PATH = Path(__file__).parent.parent / ".github" / "workflows" / "check_notices.yml"


def test_notice_check_schedule_is_weekday_30m_weekend_2h():
    with open(WORKFLOW_PATH, encoding="utf-8") as f:
        data = yaml.safe_load(f)

    # PyYAML 1.1 parser treats the unquoted key "on" as True.
    on_section = data.get("on") or data.get(True)
    crons = [item["cron"] for item in on_section["schedule"]]

    assert crons == [
        "7 15-23 * * 0",
        "37 15-23 * * 0",
        "7 * * * 1-4",
        "37 * * * 1-4",
        "7 0-14 * * 5",
        "37 0-14 * * 5",
        "7 16,18,20,22 * * 5",
        "7 0,2,4,6,8,10,12,14,16,18,20,22 * * 6",
        "7 0,2,4,6,8,10,12,14 * * 0",
    ]
