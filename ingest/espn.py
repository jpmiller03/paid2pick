"""
ESPN's unofficial site API — team logos + records/standings.

Free, no key. Shapes verified May 2026:
  - list:   site.api.espn.com/apis/site/v2/sports/{path}/teams
            -> sports[0].leagues[0].teams[].team {id, displayName, abbreviation,
               location, logos[].href}
  - detail: .../teams/{id} -> team {record.items[0].summary, standingSummary}
"""
import json
import urllib.request

API = "https://site.api.espn.com/apis/site/v2/sports"

# our Sport.category -> ESPN sport/league path
SPORT_PATHS = {
    1: "baseball/mlb",
    2: "football/nfl",
    3: "basketball/nba",
    4: "football/college-football",
    5: "basketball/mens-college-basketball",
    6: "hockey/nhl",
}


def _get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "paid2pick/1.0"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.load(r)


def team_list(path):
    """All teams for a sport: dicts of espn_id/name/location/abbreviation/logo_url."""
    data = _get(f"{API}/{path}/teams")
    out = []
    for entry in data["sports"][0]["leagues"][0]["teams"]:
        t = entry["team"]
        logos = t.get("logos") or []
        out.append({
            "espn_id": str(t["id"]),
            "name": t.get("displayName", ""),
            "location": t.get("location", ""),
            "abbreviation": t.get("abbreviation", ""),
            "logo_url": logos[0]["href"] if logos else "",
        })
    return out


def team_detail(path, espn_id):
    """(record, standing) for one team, e.g. ('29-24', '3rd in NL West')."""
    t = _get(f"{API}/{path}/teams/{espn_id}")["team"]
    rec = t.get("record") or {}
    items = rec.get("items") or [] if isinstance(rec, dict) else []
    record = items[0].get("summary", "") if items else ""
    return record, t.get("standingSummary", "")
