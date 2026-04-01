# Cash Cow Hub (React)

Standalone landing and section browser; same **gold / pasture green** branding as the Streamlit dashboard.

```bash
cd hub
npm install
npm run dev
```

Opens **http://127.0.0.1:3000**. For production static files: `npm run build` → `dist/`.

The Streamlit app embeds this URL via **iframe** (`CASH_COW_HUB_URL`, default `http://127.0.0.1:3000`) on the **Hub** page.
