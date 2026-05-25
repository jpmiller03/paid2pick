# Paid2Pick — rebuild (Phases 1–4)

Django rebuild of the 2012 PHP app. Built so far (`../REBUILD_PLAN.md`):

- **Phase 1** — accounts, catalog + ingest, picks, the pure scoring engine,
  settlement, the HotStreakers leaderboard, a wallet ledger, the games listing.
- **Phase 2 — marketplace** — sell/buy picks for virtual coins: the
  hidden-until-paid reveal, an **atomic** coin transfer (buyer → seller 70% /
  platform 30%), the Buy Picks browse (shoppable by reputation), a My Picks page,
  HTMX make-a-pick, picker profiles, and login/register (coins on signup).
- **Phase 3 — contests** — coin entry fees, per-entry contest picks, deterministic
  scoring (total accustat), ranked standings, and winner payouts from the prize pool
  (ties split). The DFS-law-sensitive feature.
- **Phase 4 prep — payments seam** — a `Deposit` that credits the wallet via a
  `DEPOSIT` ledger entry on confirmation; a provider abstraction (working
  `FakeProvider` for offline, documented Stripe stub) + idempotent webhook. Real
  money is purely additive and stays behind the legal gate.

Design references live at the repo root: `SCORING_SPEC.md`, `MARKETPLACE_SPEC.md`,
`CONTESTS_SPEC.md`, `REBUILD_PLAN.md`.

## Quick start

```bash
cd rebuild
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt

python manage.py migrate
python manage.py seed_demo        # sports, demo users, open games, a finished game
python manage.py settle           # grade the finished game, build the leaderboard
python manage.py runserver        # http://127.0.0.1:8000/
```

Create an admin login with `python manage.py createsuperuser` → `/admin/`.

## Tests

The scoring engine is pure Python (no Django) and is the irreplaceable IP:

```bash
python -m unittest discover -s scoring     # 12 tests: every bet type + push cases
python manage.py test                      # 29 Django tests (marketplace atomic transfer
                                           #   & rollback, contest scoring/payout,
                                           #   payments deposit + webhook idempotency)
```

## Key pages

| URL | What |
|---|---|
| `/` | games listing (HTMX make-a-pick) + HotStreakers leaderboard |
| `/picks/` | Buy Picks — hidden picks, sortable by win% / accustat / date |
| `/picks/<id>/buy/` | purchase (POST; atomic coin transfer) |
| `/purchases/` | My Picks — unlocked picks + results |
| `/contests/`, `/contests/<id>/` | contests list + detail (enter, pick, standings) |
| `/accounts/u/<id>/` | picker profile — stats + their (paywalled) picks |
| `/wallet/add/` | add coins (Phase-4 deposit seam; fake provider offline) |
| `/accounts/login/`, `/accounts/register/` | auth (register grants coins) |
| `/admin/` | full backoffice |

## Layout

```
scoring/            PURE engine: grade() + accustat() + enums + tests  (no Django)
catalog/            Sport, Match (lines + scores + lifecycle)
accounts/           custom User, PickerStats, picker profiles
picks/              Pick + Purchase, services (make/settle/recompute/purchase), HTMX make-pick
contests/           Contest/Entry/Pick + services (enter, pick, settle+payout)
wallet/             Wallet + append-only LedgerEntry  ("free now, paid later" seam)
payments/           Deposit + provider abstraction + idempotent webhook (Phase 4 seam)
ingest/             The Odds API client + scheduled commands + seed_demo
web/                games listing, context processor (nav balance), Cabin Sketch CSS
paid2pick/          project settings/urls
```

## Scheduled commands (replace the legacy cron scripts)

| Command | Replaces | Does |
|---|---|---|
| `fetch_odds` | odds.php | upsert matches + lines from The Odds API (or bundled sample) |
| `lock_matches` | lock.php | OPEN → LOCKED within `LOCK_LEAD_MINUTES` of kickoff |
| `fetch_scores` | scores.php | pull finals, mark FINAL (needs `ODDS_API_KEY`) |
| `settle` | stats.php | grade picks vs their snapshot, award accustat, rebuild stats |
| `settle_contests` | — | score + pay out contests past their end time |

Run them on cron / the host scheduler. See `REBUILD_PLAN.md` §4 for the credit-aware
polling strategy.

## Config (env vars)

- `ODDS_API_KEY` — The Odds API key. **Unset → ingest uses `ingest/sample_response.json`** so everything runs offline.
- `P2P_PICK_PRICE` (100), `P2P_PLATFORM_CUT` (0.30), `P2P_SIGNUP_GRANT` (1000) — coin economics.
- `P2P_LOCK_LEAD_MINUTES` (30) — when picks lock / auto-reveal.
- `P2P_PAYMENTS_PROVIDER` (`fake`) — `stripe` for real money (needs `STRIPE_SECRET_KEY`,
  `STRIPE_WEBHOOK_SECRET`, and the legal gate). `P2P_COINS_PER_CENT` (1).
- Dev uses SQLite; set Postgres + swap in `psycopg` for production.

## Notable fidelity / fixes baked in

- **PUSH is first-class** — exact totals / spread pushes / tie games are voided, not
  scored as losses (the legacy bug). `seed_demo` includes a push to show it.
- **Picks grade against the line they locked in** (`Pick.line_point` / `odds_price`),
  not the match's moving line.
- **Stats are derived**, fully recomputed at settlement — never hand-incremented.
