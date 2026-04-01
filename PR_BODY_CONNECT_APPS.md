## Summary

Unifies the **Cash Cow** solution behind one **main landing page** (`hub/src/CashCowHub.jsx`): the React hub on **:3000** links every runnable app and external data source, and Streamlit (**:8502**) embeds that same hub in the **Hub** tab via `st.components.v1.html` + iframe (`CASH_COW_HUB_URL`).

## Connected applications

| Surface | Port / URL | Role |
|--------|------------|------|
| **React Hub** | `:3000` | Main landing; “Connected stack” tiles + deep links |
| **Streamlit** | `:8502` | Ops console (8 nav pages including Hub, Overview, API & docs) |
| **Cash Cow API** | `:8090` | FastAPI — health, dashboard bundle, alpha, copy-click, preview-script |
| **MoneyPrinterTurbo** | `:8080` | Video generation; `bridge.py` submits payloads with Alpha footer |
| **Polymarket / DeFi Llama** | web | External venues surfaced in scorer + DeFi tab |

## How to verify

1. `python api.py` (or uvicorn on 8090)
2. `cd hub && npm install && npm run dev` → open **http://127.0.0.1:3000**
3. `streamlit run dashboard.py --server.port 8502` → **Hub** tab should show the iframe when the dev server is up
4. Optional: MPT on 8080 for end-to-end video path

## Config

- **Dashboard:** `CASH_COW_HUB_URL`, `CASH_COW_HUB_IFRAME_HEIGHT` (`.env.example`)
- **Hub build:** `VITE_CASH_COW_HOST` and optional full URLs (`hub/.env.example`)

## Note

TradingAgents **webapp** (`ta-web`, `webapp/`) remains the upstream browser console for agent runs; this PR focuses on wiring the **hackathon dashboard + API + hub + MPT** story for the main landing narrative.
