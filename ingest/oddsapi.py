"""
The Odds API (v4) client + mapping onto our Match fields.

Mirrors the mapping proved in prototype/fetch_odds.py. With no ODDS_API_KEY,
falls back to the bundled sample so the pipeline runs fully offline.
"""
import datetime
import json
from pathlib import Path

import requests
from django.conf import settings

API_BASE = "https://api.the-odds-api.com/v4"
SAMPLE = Path(__file__).parent / "sample_response.json"
PREFERRED_BOOKS = ("pinnacle", "draftkings", "fanduel")


def load_sample():
    return json.loads(SAMPLE.read_text())


def fetch_odds(sport_key):
    if not settings.ODDS_API_KEY:
        return load_sample()
    resp = requests.get(
        f"{API_BASE}/sports/{sport_key}/odds",
        params={
            "apiKey": settings.ODDS_API_KEY,
            "regions": settings.ODDS_API_REGION,
            "markets": settings.ODDS_API_MARKETS,
            "oddsFormat": "american",
            "dateFormat": "iso",
        },
        timeout=20,
    )
    resp.raise_for_status()
    return resp.json()


def fetch_scores(sport_key, days_from=1):
    """Recently completed games. Offline returns [] (use seed_demo instead)."""
    if not settings.ODDS_API_KEY:
        return []
    resp = requests.get(
        f"{API_BASE}/sports/{sport_key}/scores",
        params={"apiKey": settings.ODDS_API_KEY, "daysFrom": days_from,
                "dateFormat": "iso"},
        timeout=20,
    )
    resp.raise_for_status()
    return resp.json()


def parse_iso(s):
    return datetime.datetime.fromisoformat(s.replace("Z", "+00:00"))


def _book(event):
    books = {b["key"]: b for b in event.get("bookmakers", [])}
    for k in PREFERRED_BOOKS:
        if k in books:
            return books[k]
    bks = event.get("bookmakers")
    return bks[0] if bks else None


def _market(book, key):
    for m in book.get("markets", []):
        if m["key"] == key:
            return {o["name"]: o for o in m["outcomes"]}
    return {}


def map_event(event):
    """One Odds API event -> kwargs for catalog.Match (minus sport FK)."""
    home, away = event["home_team"], event["away_team"]
    book = _book(event)
    h2h = _market(book, "h2h") if book else {}
    spreads = _market(book, "spreads") if book else {}
    totals = _market(book, "totals") if book else {}
    over, under = totals.get("Over", {}), totals.get("Under", {})

    return {
        "sport_key": event["sport_key"],
        "external_id": event["id"],
        "home": home,
        "away": away,
        "commence_time": parse_iso(event["commence_time"]),
        "over_under": over.get("point"),
        "over_extra": over.get("price"),
        "under_extra": under.get("price"),
        "home_rl": spreads.get(home, {}).get("point"),
        "away_rl": spreads.get(away, {}).get("point"),
        "home_rl_extra": spreads.get(home, {}).get("price"),
        "away_rl_extra": spreads.get(away, {}).get("price"),
        "home_ml": h2h.get(home, {}).get("price"),
        "away_ml": h2h.get(away, {}).get("price"),
        "line_book": book["title"] if book else "",
    }


def map_score(event):
    """One Odds API scores event -> (external_id, home_score, away_score, completed)."""
    scores = {s["name"]: int(s["score"]) for s in (event.get("scores") or [])
              if s.get("score") is not None}
    return {
        "external_id": event["id"],
        "home_score": scores.get(event["home_team"]),
        "away_score": scores.get(event["away_team"]),
        "completed": bool(event.get("completed")),
    }
