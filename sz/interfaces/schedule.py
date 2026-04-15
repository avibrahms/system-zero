"""UTC-anchored cron helpers for module scheduling."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sz.core import manifest, paths

_MONTH_MIN = 1
_MONTH_MAX = 12
_DOW_MIN = 0
_DOW_MAX = 7


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _cron_weekday(moment: datetime) -> int:
    return (moment.weekday() + 1) % 7


def _expand_part(part: str, minimum: int, maximum: int, *, allow_sunday_7: bool = False) -> set[int]:
    values: set[int] = set()
    if part == "*":
        return set(range(minimum, maximum + 1))

    if "/" in part:
        base, step_text = part.split("/", 1)
        step = int(step_text)
        source = _expand_part(base or "*", minimum, maximum, allow_sunday_7=allow_sunday_7)
        ordered = sorted(source)
        if not ordered:
            return set()
        start = ordered[0]
        return {value for value in ordered if (value - start) % step == 0}

    if "," in part:
        for chunk in part.split(","):
            values.update(_expand_part(chunk, minimum, maximum, allow_sunday_7=allow_sunday_7))
        return values

    if "-" in part:
        start_text, end_text = part.split("-", 1)
        start = int(start_text)
        end = int(end_text)
        if allow_sunday_7 and end == 7 and start <= 6:
            return set(range(start, 7)) | {0}
        if allow_sunday_7 and start == 7:
            start = 0
        if allow_sunday_7 and end == 7:
            end = 0
        if end < start:
            raise ValueError(f"Invalid cron range {part!r}.")
        return set(range(start, end + 1))

    value = int(part)
    if allow_sunday_7 and value == 7:
        value = 0
    if value < minimum or value > maximum:
        raise ValueError(f"Cron value {value} outside {minimum}-{maximum}.")
    return {value}


def matches(expression: str, when: datetime | None = None) -> bool:
    moment = (when or _utc_now()).astimezone(timezone.utc)
    if expression == "@tick":
        return True
    if expression == "@hourly":
        return moment.minute == 0
    if expression == "@daily":
        return moment.hour == 0 and moment.minute == 0
    if expression == "@weekly":
        return _cron_weekday(moment) == 0 and moment.hour == 0 and moment.minute == 0

    minute, hour, day, month, weekday = expression.split()
    minute_values = _expand_part(minute, 0, 59)
    hour_values = _expand_part(hour, 0, 23)
    day_values = _expand_part(day, 1, 31)
    month_values = _expand_part(month, _MONTH_MIN, _MONTH_MAX)
    weekday_values = _expand_part(weekday, _DOW_MIN, _DOW_MAX, allow_sunday_7=True)
    weekday_value = _cron_weekday(moment)

    return (
        moment.minute in minute_values
        and moment.hour in hour_values
        and moment.day in day_values
        and moment.month in month_values
        and weekday_value in weekday_values
    )


def module_triggers(root: Path) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    sz_dir = paths.s0_dir(root)
    if not sz_dir.exists():
        return entries
    for module_dir in sorted(path for path in sz_dir.iterdir() if path.is_dir()):
        manifest_path = module_dir / "module.yaml"
        if not manifest_path.exists():
            continue
        data = manifest.load(manifest_path)
        for trigger in data.get("triggers", []):
            entries.append({"module_id": data["id"], "trigger": trigger})
    return entries
