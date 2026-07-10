# Shanaya — MKOV Travel Assistant

AI-powered travel chatbot for Uniglobe MKOV Travel, embedded on
[uniglobemkov.in](https://uniglobemkov.in) via WordPress.

- **Backend:** FastAPI + Google Gemini (`gemini-3.1-flash-lite`)
- **Database:** Turso (libSQL) — permanent, survives all restarts
- **Hosting:** Render (free tier)
- **Frontend:** Vanilla JS widget embedded via iframe

---

## Live URLs

| What | URL |
|---|---|
| Backend | `https://shanaya-bot-umkov.onrender.com` |
| Widget (test directly) | `https://shanaya-bot-umkov.onrender.com/widget` |
| API docs | `https://shanaya-bot-umkov.onrender.com/docs` |
| Health check | `https://shanaya-bot-umkov.onrender.com/health` |
| Leads (JSON) | `https://shanaya-bot-umkov.onrender.com/leads` |
| Leads (CSV download) | `https://shanaya-bot-umkov.onrender.com/leads/export` |

All protected endpoints need header: `X-API-Key: mkov-dev-key-2026`

---

## 🚨 TROUBLESHOOTING — READ THIS FIRST

### Problem: Widget doesn't appear on the website at all

**Check in order:**

1. **Is the footer script actually pasted in WordPress?**
   Go to WPCode plugin → Footer Scripts → confirm the script from
   `wordpress-footer-FINAL.html` is there and active.

2. **Open browser console (F12) and look for errors**
   - `Failed to load resource: 404` on `/widget` → backend URL is wrong
     in the footer script or `static/widget.html` is missing from repo
   - `CORS error` → check `ALLOWED_ORIGINS` in `config.py` includes `"*"`
   - No errors, no button visible → footer script wasn't saved/published

3. **Visit the backend directly**
   Open `https://shanaya-bot-umkov.onrender.com/health` in browser.
   - Shows `{"status":"ok"}` → backend is fine, problem is in WordPress/frontend
   - Times out / spinner forever → Render service is down, see below
   - `Application Error` → check Render logs (see below)

---

### Problem: "I'm having a technical issue" / connection errors

**Cause 1 — Render free tier spin-down**
Free tier sleeps after 15 minutes of no traffic. First message after
sleep takes ~50 seconds to wake up, which can time out.

**Fix:** Set up [UptimeRobot](https://uptimerobot.com) (free) to ping
`https://shanaya-bot-umkov.onrender.com/health` every 5 minutes. Keeps
the service permanently awake.

**Cause 2 — GEMINI_API_KEY missing or invalid**
Check Render → your service → Environment → confirm `GEMINI_API_KEY`
is set and not expired. Test the key directly at
[aistudio.google.com](https://aistudio.google.com).

**Cause 3 — Wrong URL in widget.html or footer script**
If you ever change Render accounts or the URL changes, you must update
it in **two places**, not one:
- `wordpress-footer-FINAL.html` → the `RENDER` variable
- `static/widget.html` → the `API` constant near the top of the script

Missing either one causes silent failures.

---

### Problem: Leads showing `"total": 0` even though people have chatted

**Cause — Render wiped the local SQLite file**
Render's free tier filesystem is not guaranteed to persist — restarts,
redeploys, and even routine maintenance can wipe local files. If the
project is still using local SQLite instead of Turso, this is expected
and will keep happening.

**Fix:** Confirm `database.py` is using Turso (`libsql`), not local
`sqlite3.connect()`. Check Render env vars have:
```
TURSO_DATABASE_URL = libsql://shanaya-db-xxxx.turso.io
TURSO_AUTH_TOKEN   = ...
```
If these are missing, the app will crash on startup with a clear error
in the logs — check Render logs to confirm.

---

### Problem: Widget opens automatically on every page / new tab

This was a known bug, already fixed in `wordpress-footer-FINAL.html`.
If it comes back, check:
- The footer script matches the latest version (uses `localStorage`,
  not `sessionStorage`, and does NOT auto-restore open state on load)
- No old/duplicate footer script is still active in WPCode

---

### Problem: User has to re-enter name and phone every visit

Identity is stored in the browser's `localStorage` under keys
`shanaya_name`, `shanaya_phone`, `shanaya_id`. This persists per
browser/device, not per person — if they switch browsers or clear
site data, they'll be asked again. This is expected behaviour, not
a bug.

---

### Problem: Shanaya gives wrong tour package or visa links

All links live in `config.py` inside `SYSTEM_PROMPT`. If MKOV changes
a URL on the website, update it there and redeploy — Shanaya has no
way to know a link changed otherwise.

---

### Problem: Google Flights / cheapest flight search not working

Check `SERPAPI_KEY` is set in Render environment variables. Free tier
SerpApi gives 100 searches/month — if that's exhausted, flight search
will silently fall back to the internal portal scraper, or fail
gracefully with "search not configured."

---

## How to check Render logs

1. Go to [render.com](https://render.com) → log in
2. Click on the `shanaya-bot-umkov` service
3. Click **Logs** tab on the left
4. Look for lines starting with `[ERROR]` or `[CHAT]` — these show
   exactly what happened on the last few messages

---

## How to redeploy after making changes

1. Push your changed files to GitHub (`main` branch)
2. Render auto-deploys within ~1-2 minutes
3. Watch the **Logs** tab to confirm `✓ Shanaya AI Engine loaded` appears
4. Test at `/health` before assuming it's live

---

## Environment variables checklist (Render → Environment tab)

| Variable | Required? | Notes |
|---|---|---|
| `GEMINI_API_KEY` | ✅ Yes | App won't start without this |
| `DEFAULT_API_KEY` | ✅ Yes | Defaults to `mkov-dev-key-2026` if unset |
| `TURSO_DATABASE_URL` | ✅ Yes | App won't start without this |
| `TURSO_AUTH_TOKEN` | ✅ Yes | App won't start without this |
| `SERPAPI_KEY` | Optional | Flight search disabled if missing |
| `FLIGHT_PORTAL_USERNAME` | Optional | Internal portal fallback disabled if missing |
| `FLIGHT_PORTAL_PASSWORD` | Optional | Internal portal fallback disabled if missing |

---

## File structure

```
Shanaya_v1.0.0/
├── main.py               ← FastAPI routes
├── ai_engine.py          ← Gemini logic + identity gate
├── config.py             ← System prompt, links, settings
├── database.py           ← Turso database connection
├── memory.py             ← Conversation history
├── auth.py               ← API key verification
├── actions.py            ← Booking/hold/cancel logic
├── google_flights.py     ← Google Flights via SerpApi
├── flight_scraper.py     ← Internal portal fallback
├── lead_extractor.py     ← Lead data helpers
├── requirements.txt
├── Dockerfile
├── Procfile
└── static/
    ├── widget.html       ← The chatbot UI itself
    └── Shanaya-avatar.jpg
```

---

## Who to contact

The developer of this software via the email 992501210103@mail.jiit.ac.in.
