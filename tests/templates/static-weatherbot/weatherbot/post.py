"""Post the current weather to ./posts/<UTC date>.txt. Run me on a schedule."""
from __future__ import annotations

import json
import os
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


def post_weather(city: str = "Paris") -> Path:
    out_dir = Path("posts")
    out_dir.mkdir(exist_ok=True)
    out_path = out_dir / f"{datetime.now(timezone.utc).strftime('%Y-%m-%d')}.txt"
    key = os.environ.get("OPENWEATHER_API_KEY", "")
    if not key:
        out_path.write_text("[no api key set]\n")
        return out_path
    url = f"https://api.openweathermap.org/data/2.5/weather?q={city}&appid={key}&units=metric"
    try:
        with urllib.request.urlopen(url, timeout=15) as r:
            data = json.loads(r.read())
        line = f"{datetime.now(timezone.utc).isoformat(timespec='seconds')}Z {city}: {data['weather'][0]['description']} {data['main']['temp']}C\n"
    except Exception as e:
        line = f"[error] {e}\n"
    out_path.write_text(line)
    return out_path


if __name__ == "__main__":
    print(post_weather(os.environ.get("CITY", "Paris")))
