from __future__ import annotations

from datetime import datetime, timezone

from sz.interfaces import schedule


def test_schedule_matches_special_tokens() -> None:
    sunday_midnight = datetime(2026, 4, 19, 0, 0, tzinfo=timezone.utc)
    assert schedule.matches("@tick", sunday_midnight)
    assert schedule.matches("@hourly", sunday_midnight)
    assert schedule.matches("@daily", sunday_midnight)
    assert schedule.matches("@weekly", sunday_midnight)


def test_schedule_matches_five_field_cron() -> None:
    moment = datetime(2026, 4, 15, 12, 30, tzinfo=timezone.utc)
    assert schedule.matches("30 12 * * 3", moment)
    assert schedule.matches("*/15 12 * * *", moment)
    assert not schedule.matches("0 12 * * *", moment)
