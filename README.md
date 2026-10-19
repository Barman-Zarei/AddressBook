# AddressBook V7.9.0

A multi-user contact manager: a **Kivy** mobile/desktop app talking to a **Django REST** backend
(JWT auth) that stores data in **PostgreSQL** (hosted on Render).
The app never holds database credentials, so an APK built from it exposes no secrets.

```
AddressBook-V7/
├── addressbook_backend/   Django + DRF + PostgreSQL  (deploy to Render)
└── addressbook_app/       Kivy client                (desktop now, APK later)
```

## 1. Backend

```bash
cd addressbook_backend
pip install -r requirements.txt
cp .env.example .env        # fill in your Render PostgreSQL values + a secret key
python manage.py migrate
python manage.py runserver
```

Generate a secret key:

```bash
python -c "import secrets; print(secrets.token_urlsafe(50))"
```

### Deploy on Render (Web Service)
- Build command: `pip install -r requirements.txt && python manage.py migrate`
- Start command: `gunicorn addressbook_backend.wsgi`
- Environment variables: everything in `.env.example`
  (`DJANGO_DEBUG=False`, `DJANGO_ALLOWED_HOSTS=<your-service>.onrender.com`)

### API
| Method | Path | Description |
|---|---|---|
| POST | `/api/auth/register/` | create account |
| POST | `/api/auth/login/` | returns `access` + `refresh` tokens |
| POST | `/api/auth/refresh/` | new access token |
| GET | `/api/auth/me/` | current user |
| DELETE | `/api/auth/delete/` | delete account + its contacts |
| GET/POST | `/api/contacts/` | list / create |
| GET/PUT/DELETE | `/api/contacts/{id}/` | read / update / delete |
| GET | `/api/contacts/search/?q=` | search name / phone / email |

## 2. App

```bash
cd addressbook_app
pip install -r requirements.txt
# edit config.py -> API_BASE_URL (local server or your Render URL)
python main.py
```

## 3. Rate limiting

`addressbook_backend/ratelimiter/` is a middleware that runs before everything else.

- **Sliding-window counter**, several windows per rule (e.g. 10/min *and* 60/hour), atomic via the cache.
- **Several identities at once**: client IP (IPv6 collapsed to /64), authenticated user id (read from the JWT), and for login the *username* (stops distributed password guessing across many IPs).
- **Escalating bans**: 5 rejected requests in 10 min -> blocked 1 min, then 2, 4, 8 ... up to 24 h.
- Per-route rules and costs (search costs 2), global flood limit, allow/block lists with CIDR.
- Spoof-proof client IP: only the `X-Forwarded-For` entry added by *your* proxy is trusted (`RATE_LIMIT_TRUSTED_PROXIES`).
- `429` JSON + `Retry-After` and `X-RateLimit-*` headers; the Kivy app already shows the `detail` text.
- Fails open if the cache is down (configurable).

All rules live in `ratelimiter/conf.py`; override any key through `RATE_LIMIT` in `settings.py`.
**Set `REDIS_URL`** in production, otherwise every gunicorn worker keeps its own counters.
Lift a ban: `python manage.py ratelimit_reset --ip 1.2.3.4` (or `--username`, `--user-id`).

## 4. Backups & restore

Logical JSON dumps (users + contacts, gzip, password hashes included), verified after writing.

**Automatic (one Render *Background Worker*, start command `python manage.py backup_scheduler`):**
- a backup **every 30 minutes** (`BACKUP_INTERVAL_MINUTES`);
- optionally a **monthly restore**: on `BACKUP_RESTORE_DAY` (default **27th**) at `BACKUP_RESTORE_TIME` (default **12:00**, project time zone Asia/Tehran) the newest backup is loaded into the database. Configured for **day 27 at 12:00 (Asia/Tehran)**; switch it on with `BACKUP_RESTORE_ENABLED=True`.

How the monthly restore behaves:
- It only *arms* itself the first time it runs; it never restores immediately because this month's date already passed.
- The "done this month" marker is stored next to the backups (not in the DB, which may be a brand-new one), so restarts never repeat or skip it.
- It runs `migrate` first, so an empty new database gets its tables.
- If the DB still has users, a fresh backup is taken first, so nothing is lost. If the DB is empty (new database), nothing is backed up and the newest backup is loaded.
- A failure is retried 3 times (10 min apart), then left for a human. Day 31 means "last day" in shorter months.

Safety nets: a backup of a database **without users is refused** (a new empty DB can never push real backups out), retention keeps every backup of the last 48 h and then one per day for 35 days, and every restore first stores a `prerestore-*` copy and runs in a single transaction (a failure changes nothing).

**Manual:**
```bash
python manage.py backup_db                 # one backup now
python manage.py backup_db --if-due        # only if the last one is older than 30 min (cron: */30 * * * *)
python manage.py restore_db --list
python manage.py restore_db --date 2026-10-01 --dry-run   # newest backup at/before that date
python manage.py restore_db --date "2026-10-01 14:30"     # asks for confirmation
python manage.py restore_db --file addressbook-20261001T060000Z.json.gz --yes
```

**On Render** the local disk is wiped on every deploy, so use S3-compatible storage (Cloudflare R2, Backblaze B2, AWS S3):
`BACKUP_STORAGE=s3`, `BACKUP_S3_BUCKET`, `BACKUP_S3_ENDPOINT_URL`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`.
The worker needs the same `DB_*` variables as the web service - when you switch to a new database, update them on **both** before the restore date.
Run only **one** scheduler instance. Add new models to `BACKUP["MODELS"]` (`backups/conf.py`).

### Without a paid worker: external cron

Render's free plan has no background workers. Instead, an external cron service (e.g. cron-job.org, free) calls a token-protected endpoint every ~10 minutes; each call does one pass of `backup_scheduler` (monthly-restore check, then a backup if one is due) and also keeps the free web service awake.

1. Generate a secret: `python -c "import secrets; print(secrets.token_urlsafe(48))"`
2. On the **web service** set `BACKUP_CRON_TOKEN=<secret>` plus the same `BACKUP_*` / `AWS_*` variables as for a worker (S3 storage, restore day/time). A token shorter than 32 characters disables the endpoint (404).
3. Test: `curl -X POST https://<service>.onrender.com/api/internal/backup-tick/ -H "Authorization: Bearer <secret>"` -> `{"status":"ok","backup":"addressbook-....json.gz",...}`. No/wrong token -> 403.
4. In cron-job.org create a job: that URL, every 10 minutes, request method **POST**, header `Authorization: Bearer <secret>`, failure notifications on.

The work runs inside one web request (cron-job.org gives up after 30 s; gunicorn's default is also 30 s), which is fine for a small address book. The monthly restore then fires on the first call after the configured time. Overlapping calls are refused with `{"status":"busy"}`.

## 5. Tests

```bash
cd addressbook_backend
python manage.py test --settings=addressbook_backend.settings_test
```
