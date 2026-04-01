/**
 * Single source for inter-app links on the landing hub.
 * Override at build time: VITE_CASH_COW_HOST=your.host npm run build
 */
const host = import.meta.env.VITE_CASH_COW_HOST || "127.0.0.1";

const p = (port) => `http://${host}:${port}`;

export const urls = {
  host,
  /** Main ops UI — Polymarket, DeFi, signals, video, orchestrator, Hub iframe */
  streamlit: import.meta.env.VITE_STREAMLIT_URL || p(8502),
  /** Unified FastAPI — dashboard JSON, alpha, health, preview-script */
  api: import.meta.env.VITE_API_URL || p(8090),
  apiDocs: import.meta.env.VITE_API_DOCS_URL || `${p(8090)}/docs`,
  apiHealth: import.meta.env.VITE_API_HEALTH_URL || `${p(8090)}/api/v1/health`,
  /** MoneyPrinterTurbo — short-form video generation */
  mpt: import.meta.env.VITE_MPT_URL || p(8080),
  /** This React hub (dev: 3000) */
  hub: typeof window !== "undefined" ? window.location.origin : p(3000),
  polymarket: "https://polymarket.com",
  defiLlama: "https://defillama.com",
};
