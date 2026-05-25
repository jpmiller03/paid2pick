# Deploying Paid2Pick

Target: a Python PaaS (**Render**) + **Neon** Postgres, with **Cloudflare** in front for
DNS / CDN / WAF and the geo-blocking the legal gate needs. (Railway / Fly.io work the
same way via the `Procfile`.)

## 1. Database — Neon

1. Create a project at neon.tech → copy the **direct** connection string.
2. Ensure it ends with `?sslmode=require`. That's your `DATABASE_URL`.

## 2. App — Render

This repo ships a `render.yaml` blueprint (one free web service + a shared env group).

1. Push `rebuild/` to a Git repo. In Render: **New → Blueprint**, point it at the repo.
2. Fill the `paid2pick-env` group:
   - `DATABASE_URL` — the Neon string
   - `DJANGO_SECRET_KEY` — `python -c "import secrets; print(secrets.token_urlsafe(50))"`
   - `ODDS_API_KEY` — your key (omit to run on the bundled sample)
   - `DJANGO_ALLOWED_HOSTS` — optional; Render's `*.onrender.com` host is allowed
     automatically. Set it once you add a custom domain.
3. Deploy. The **build** runs `migrate` + `collectstatic`; the web service starts under
   gunicorn. Then open the Render **Shell** to create an admin and (optionally) seed demo
   data to look at: `python manage.py createsuperuser` and `python manage.py seed_demo &&
   python manage.py settle`.

**Static files** are served by WhiteNoise from the app (compressed + hashed) — no
separate origin needed; Cloudflare caches them at the edge.

### Scheduled jobs
Two options for running `fetch_odds` / `lock_matches` / `fetch_scores` / `settle` /
`settle_contests` on a schedule:

**A. GitHub Actions (free, recommended)** — shipped at `.github/workflows/cron.yml`.

**B. Render cron** — move the jobs into `render.yaml` as `type: cron` services; requires a **paid** plan.

GitHub Actions setup — `.github/workflows/cron.yml`: A `*/15` tick runs
lock+scores+settle; odds refresh every 3h. To enable:
1. In the GitHub repo: **Settings → Secrets and variables → Actions** → add repo secrets
   `DATABASE_URL` (the Neon string), `DJANGO_SECRET_KEY`, and `ODDS_API_KEY`.
2. The workflow runs automatically on schedule; use **Actions → Scheduled jobs → Run
   workflow** to trigger a run manually (and to test).

   Watch-outs (all noted in the workflow header):
   - Actions minutes are **free/unlimited on public repos**; on a **private** repo the
     `*/15` tick exceeds the free 2,000 min/month — make it public or coarsen the tick.
   - GitHub **auto-disables** scheduled workflows after 60 days of no commits.
   - Timing is best-effort — fine here, because pick lock/reveal is computed live from
     `commence_time`, so a late run never lets someone act on a started game.

See `REBUILD_PLAN.md` §4 for the credit-aware polling cadence.

## 3. Front door — Cloudflare

1. Add the domain to Cloudflare; point an `A`/`CNAME` (proxied, orange cloud) at the
   Render web hostname. Set SSL/TLS to **Full (strict)**.
2. **Cache** the static path (`/static/*`) aggressively; leave app routes dynamic.
3. **R2** (optional): move user avatars / contest banners here instead of local disk
   (replaces the legacy `_upload/`); serve via a custom domain.
4. **Geo-blocking for Phase 4**: when real money turns on, add a WAF rule blocking
   `ip.geoip.subdivision_1_iso_code` / country for DFS-restricted states/regions. This
   is the enforcement half of the legal gate in `REBUILD_PLAN.md` §6 — keep it off while
   the app is free/virtual-coin.

## Notes
- `DEBUG=0` in prod turns on HSTS, secure cookies, and `SECURE_PROXY_SSL_HEADER`
  (so Django trusts the `X-Forwarded-Proto` from the Render/Cloudflare proxies).
- `CSRF_TRUSTED_ORIGINS` is derived from `DJANGO_ALLOWED_HOSTS` automatically.
- Don't host on DreamHost shared (PHP-oriented); a DreamHost VPS could run this but a
  Python PaaS is far less setup.
