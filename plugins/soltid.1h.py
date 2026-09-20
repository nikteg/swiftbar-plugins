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

from datetime import datetime

from swiftbar.http import post_json
from swiftbar.output import render
from swiftbar.plugin import guard
from swiftbar.ui import Item, Node, Title, Unavailable

URL = "https://www.stralsakerhetsmyndigheten.se/api/v1/suntime/calculate"


def format_suntime(
    result: dict, *, icon: bool = False, description: bool = False
) -> str:
    if result.get("restOfDay"):
        suntime = "✅" if icon else "Resten av dagen"
    else:
        suntime = "{}h {}m".format(
            result.get("safeTimeHours", 0), result.get("safeTimeMinutes", 0)
        )

    suffix = result.get("shadowDescription", "") if description else ""

    return " ".join(part for part in (suntime, suffix) if part)


def Soltid(latitude: float, longitude: float, skin_type: int) -> Node:
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
    results = result.get("safeTimeResults") or []

    if not results:
        return Unavailable("☀️ —", "No sun data for right now")

    return [
        Title(f"☀️ {format_suntime(results[0], icon=True)}"),
        Item(result.get("resultDescription", "").split(" den ")[0]),
        [Item(format_suntime(entry, description=True)) for entry in results],
    ]


if __name__ == "__main__":
    guard(name="Soltid", icon="☀️")
    print(render(Soltid(latitude=57.7095511309657, longitude=11.0, skin_type=2)))
