# Pull request: Cash Cow Alpha + sidebar navigation

## Summary

Delivers **divergence-triggered “Cash Cow Alpha Signal”** flows (educational / paper framing), **copy-click analytics** on the API, **video description** branding via `generate_script` and `bridge`, and a **Streamlit sidebar** built with **streamlit-option-menu** and **streamlit-autorefresh** so navigation and live metrics do not depend on top tabs.

## Install

Use the **same Python** you use for `streamlit run` (see `where python` / `py -0` if imports fail):

```bash
cd CashCow
python -m pip install -r requirements.txt
```

## How to test

1. **API:** `python api.py` or `uvicorn api:app --host 0.0.0.0 --port 8090`
2. **Dashboard:** `streamlit run dashboard.py --server.port 8502`
3. Confirm sidebar **Navigate** menu switches views; page **auto-refreshes ~20s** (health + copy-click total).
4. **Polymarket** tab: **Copy This Divergence** buttons POST to `/api/v1/track-copy-click`; optional `GET /api/v1/alpha-signals`.
5. **OpenAPI:** http://127.0.0.1:8090/docs

## Base branch

This branch was created from the then-current `docs/intel-strategy-memo`. When opening the PR on GitHub, set the base to **`main`** (or your team default) if you want production integration; otherwise merge as-is into the doc branch.

## Checklist

- [x] `requirements.txt` lists dashboard + API stack including sidebar packages
- [x] `.gitignore` excludes local `logs/copy_trade_clicks.jsonl` and `logs/last_plan.json`
- [x] `.env.example` documents Cash Cow Alpha / X follow env vars

## Risk / follow-ups

- **Auto-refresh** reruns the full app every 20s; lengthen interval or gate behind a toggle if it disrupts long forms.
- **Regulatory:** copy-trade UI remains framed as educational signals; Whop / performance fee not implemented here.
