"""Safe sun exposure from Strålsäkerhetsmyndigheten's suntime API."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from swiftbar_lib.http import post_json

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
