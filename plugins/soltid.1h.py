#!/usr/bin/env -S /opt/homebrew/bin/uv run --script --quiet
# /// script
# requires-python = ">=3.12"
# ///
# <swiftbar.title>Soltid</swiftbar.title>
# <swiftbar.author>nikteg</swiftbar.author>
# <swiftbar.author.github>nikteg</swiftbar.author.github>
# <swiftbar.desc>How long you can stay in the sun before burning</swiftbar.desc>
# <swiftbar.dependencies>uv</swiftbar.dependencies>
"""How long you can stay in the sun before burning.

Shows
    Menu bar: safe time from the current hour, or ✅ when the UV index is low
    enough that the rest of the day is safe.
    Dropdown: the agency's summary, then safe time for each remaining hour
    with the shadow-length rule of thumb for that hour.

Configure
    Edit the call at the bottom of this file.
      latitude, longitude  Defaults are Gothenburg.
      skin_type            Fitzpatrick scale 1-6, as on the agency's own form.
                           1 burns fastest, 6 slowest.

Source
    Strålsäkerhetsmyndigheten's public suntime API.

Refresh
    Hourly, from the ``1h`` in this file's name. Rename to change it.
"""

from dataclasses import dataclass
from datetime import datetime

from swiftbar_lib.http import post_json
from swiftbar_lib.output import show
from swiftbar_lib.ui import Item, Title

URL = "https://www.stralsakerhetsmyndigheten.se/api/v1/suntime/calculate"


@dataclass(frozen=True)
class SafeTime:
    #: Short form for the menu bar: ✅ when the rest of the day is safe.
    icon: str
    #: The same figure spelled out, with the shadow-length rule of thumb.
    described: str


@dataclass(frozen=True)
class Forecast:
    headline: str
    hours: list[SafeTime]


def _format(result: dict, *, icon: bool, description: bool) -> str:
    if result.get("restOfDay"):
        suntime = "✅" if icon else "Resten av dagen"
    else:
        hours = result.get("safeTimeHours", 0)
        minutes = result.get("safeTimeMinutes", 0)
        suntime = f"{hours}h {minutes}m"

    suffix = result.get("shadowDescription", "") if description else ""

    return " ".join(part for part in (suntime, suffix) if part)


def forecast(latitude: float, longitude: float, skin_type: int) -> Forecast:
    """``skin_type`` is the Fitzpatrick scale 1-6, as on the agency's own form."""
    now = datetime.now()
    body = post_json(
        URL,
        {
            "skintypeId": str(skin_type),
            "latitude": latitude,
            "longitude": longitude,
            "dateStr": now.strftime("%Y-%m-%d"),
            "hour": str(now.hour),
        },
    )
    result = body.get("result", {})

    return Forecast(
        headline=result.get("resultDescription", "").split(" den ")[0],
        hours=[
            SafeTime(
                icon=_format(entry, icon=True, description=False),
                described=_format(entry, icon=False, description=True),
            )
            for entry in result.get("safeTimeResults") or []
        ],
    )


if __name__ == "__main__":
    today = forecast(latitude=57.7095511309657, longitude=11.0, skin_type=2)

    show(
        Title(f"☀️ {today.hours[0].icon}") if today.hours else Title("☀️ —"),
        Item(today.headline) if today.headline else None,
        [Item(hour.described) for hour in today.hours]
        or Item("No sun data for right now"),
    )
