# TRS Email Validator

Free, hosted email list validator with optional Odoo CRM integration.

## 🚀 Deploy to Vercel (one time)

1. Fork or push this repo to your GitHub account
2. Go to [vercel.com](https://vercel.com) → New Project → Import your GitHub repo
3. Click **Deploy** — no settings needed
4. Your app is live at `https://your-project.vercel.app`

## 📋 How it works

**Browser mode** (no setup, works for anyone with the URL):
- Syntax validation
- Typo detection (gmial.com → gmail.com)
- Disposable domain detection
- Export valid/invalid CSV

**Full mode** (download backend.py from Settings in the app):
- Everything above plus real MX/DNS validation
- Odoo CRM integration — log notes, clear activities, schedule follow-ups
- Supports .csv, .xlsx, .txt file upload

## 🔧 Running the backend locally

```bash
# Download backend.py from the Settings modal in the app, then:
pip install flask flask-cors dnspython openpyxl
python backend.py
# Keep this terminal open while using the app
```

## 📁 Files

- `index.html` — the full app (served by Vercel)
- `backend.py` — local Python backend (downloaded on demand from Settings)
- `vercel.json` — Vercel routing config
