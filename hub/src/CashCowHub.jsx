import { useState, useMemo } from "react";
import { urls } from "./urls.js";

const SECTIONS = [
  { id: "home", label: "Home" },
  { id: "polymarket", label: "Polymarket" },
  { id: "signals", label: "Signals" },
  { id: "defi", label: "DeFi" },
  { id: "video", label: "Video" },
  { id: "orchestrator", label: "Orchestrator" },
  { id: "alpha", label: "Alpha" },
  { id: "api", label: "API" },
];

export default function CashCowHub() {
  const [active, setActive] = useState("home");

  const panel = useMemo(() => {
    switch (active) {
      case "home":
        return <HomePanel />;
      case "polymarket":
        return <PolymarketPanel />;
      case "signals":
        return <SignalsPanel />;
      case "defi":
        return <DefiPanel />;
      case "video":
        return <VideoPanel />;
      case "orchestrator":
        return <OrchestratorPanel />;
      case "alpha":
        return <AlphaPanel />;
      case "api":
        return <ApiPanel />;
      default:
        return <HomePanel />;
    }
  }, [active]);

  return (
    <div className="hub-root">
      <header className="hub-topbar">
        <div className="hub-brand">
          <div className="hub-cow" aria-hidden>
            🐄
          </div>
          <div className="hub-brand-text">
            <h1>Cash Cow</h1>
            <span>Main landing · all apps · one stack</span>
          </div>
        </div>
        <nav className="hub-nav" aria-label="Hub sections">
          {SECTIONS.map((s) => (
            <button
              key={s.id}
              type="button"
              className={active === s.id ? "active" : ""}
              onClick={() => setActive(s.id)}
            >
              {s.label}
            </button>
          ))}
        </nav>
      </header>

      <main className="hub-main">{panel}</main>
    </div>
  );
}

function ConnectedApps() {
  const tiles = [
    {
      href: urls.hub,
      title: "This hub",
      port: ":3000",
      desc: "React landing you are on; Streamlit embeds it in the Hub tab.",
    },
    {
      href: urls.streamlit,
      title: "Streamlit dashboard",
      port: ":8502",
      desc: "Polymarket, DeFi, signals, video factory, orchestrator, API docs tab.",
    },
    {
      href: urls.apiDocs,
      title: "Cash Cow API",
      port: ":8090",
      desc: "FastAPI — /health, /dashboard, /alpha-signals, /track-copy-click, /preview-script.",
    },
    {
      href: urls.mpt,
      title: "MoneyPrinterTurbo",
      port: ":8080",
      desc: "Short-form video generation; bridge.py submits markets + Cash Cow Alpha descriptions.",
    },
    {
      href: urls.polymarket,
      title: "Polymarket",
      port: "web",
      desc: "External venue; scorer + divergence intel pull from Gamma / your feeds.",
    },
    {
      href: urls.defiLlama,
      title: "DeFi Llama",
      port: "web",
      desc: "Yield source for stable pools surfaced in dashboard DeFi tab.",
    },
  ];

  return (
    <section className="hub-connected" aria-label="Connected applications">
      <h3>Connected stack</h3>
      <p>
        Start <strong style={{ color: "var(--cc-green)" }}>API</strong> first, then{" "}
        <strong style={{ color: "var(--cc-gold)" }}>Streamlit</strong>; run this hub and MPT when you
        need the landing page or clips. Same host: <code style={{ color: "var(--cc-gold)" }}>{urls.host}</code>{" "}
        (override with <code style={{ color: "var(--cc-gold)" }}>VITE_CASH_COW_HOST</code> at build).
      </p>
      <div className="hub-flow" aria-hidden>
        <span>Hub</span> → <em>Streamlit</em> → <span>API</span> → <em>MPT</em> · Polymarket + DeFi Llama
      </div>
      <div className="hub-app-grid">
        {tiles.map((t) => (
          <a key={t.title} className="hub-app-tile" href={t.href} target="_blank" rel="noreferrer">
            <span className="hub-app-port">{t.port}</span>
            <strong>{t.title}</strong>
            <p className="hub-app-desc">{t.desc}</p>
          </a>
        ))}
      </div>
    </section>
  );
}

function HomePanel() {
  return (
    <>
      <section className="hub-hero">
        <h2>
          One landing page for the whole <em>Cash Cow</em> solution
        </h2>
        <p>
          Use the tiles below to open every app. The Streamlit console on{" "}
          <strong style={{ color: "var(--cc-green)" }}>8502</strong> embeds this UI in its{" "}
          <strong style={{ color: "var(--cc-gold)" }}>Hub</strong> tab so operators never lose context.
        </p>
        <div className="hub-actions">
          <a className="hub-btn hub-btn-primary" href={urls.streamlit} target="_blank" rel="noreferrer">
            Open Streamlit (main console)
          </a>
          <a className="hub-btn hub-btn-secondary" href={urls.apiDocs} target="_blank" rel="noreferrer">
            API docs
          </a>
          <a className="hub-btn hub-btn-secondary" href={urls.mpt} target="_blank" rel="noreferrer">
            MoneyPrinterTurbo
          </a>
        </div>
      </section>

      <ConnectedApps />

      <div className="hub-grid">
        <div className="hub-card">
          <h3>
            <span className="hub-tag hub-tag-green">Live</span> Polymarket
          </h3>
          <p>Scored markets, social divergence strip, and Cash Cow Alpha copy-flow (paper only).</p>
        </div>
        <div className="hub-card">
          <h3>
            <span className="hub-tag">Alpha</span> Signals
          </h3>
          <p>TradingAgents-style mock signals with BUY / SELL / HOLD badges and confidence bars.</p>
        </div>
        <div className="hub-card">
          <h3>
            <span className="hub-tag hub-tag-green">Yield</span> DeFi
          </h3>
          <p>Stablecoin pool APY from DeFi Llama with heat-mapped tables in the dashboard.</p>
        </div>
        <div className="hub-card">
          <h3>
            <span className="hub-tag">Clip</span> Video
          </h3>
          <p>Bridge pipeline to MoneyPrinterTurbo with Cash Cow Alpha descriptions.</p>
        </div>
      </div>
      <p className="hub-disclaimer">
        Educational and research tooling only — not investment advice. Paper-trade divergences before
        real capital; regulatory framing is your responsibility.
      </p>
    </>
  );
}

function PolymarketPanel() {
  return (
    <>
      <h2 className="hub-section-title">Polymarket desk</h2>
      <div className="hub-actions" style={{ marginBottom: "1rem", justifyContent: "flex-start" }}>
        <a className="hub-btn hub-btn-primary" href={urls.streamlit} target="_blank" rel="noreferrer">
          Open in Streamlit
        </a>
        <a className="hub-btn hub-btn-secondary" href={urls.apiDocs} target="_blank" rel="noreferrer">
          API bundle
        </a>
        <a className="hub-btn hub-btn-secondary" href={urls.polymarket} target="_blank" rel="noreferrer">
          Polymarket.com
        </a>
      </div>
      <div className="hub-grid">
        <div className="hub-card">
          <h3>Scoring</h3>
          <p>
            Top markets by cash-cow score with YES% bar, 24h volume, and social Δ from the sentiment
            layer.
          </p>
        </div>
        <div className="hub-card">
          <h3>Divergence</h3>
          <p>Grok-style alerts when X/social hype disagrees with implied odds — Task 4 alignment.</p>
        </div>
        <div className="hub-card">
          <h3>Copy frame</h3>
          <p>
            Copy This Divergence logs clicks to the API for funnel analytics; opens Polymarket deep
            links.
          </p>
        </div>
      </div>
      <ul className="hub-list" style={{ marginTop: "1.25rem" }}>
        <li>
          <strong>Dashboard:</strong> Polymarket tab → preview script + video_description footer.
        </li>
        <li>
          <strong>API:</strong> <code style={{ color: "var(--cc-gold)" }}>/api/v1/dashboard</code> bundles
          markets + alpha.
        </li>
      </ul>
    </>
  );
}

function SignalsPanel() {
  return (
    <>
      <h2 className="hub-section-title">TradingAgents signals</h2>
      <div className="hub-actions" style={{ marginBottom: "1rem", justifyContent: "flex-start" }}>
        <a className="hub-btn hub-btn-primary" href={urls.streamlit} target="_blank" rel="noreferrer">
          Signals tab in Streamlit
        </a>
      </div>
      <div className="hub-card" style={{ maxWidth: 640 }}>
        <h3>Badges</h3>
        <p>
          Green BUY, red SELL, amber HOLD — mirrored in Streamlit metric cards with confidence
          progress toward pasture green.
        </p>
      </div>
      <ul className="hub-list" style={{ marginTop: "1rem" }}>
        <li>
          <strong>Source:</strong> <code style={{ color: "var(--cc-gold)" }}>trading_signal.get_signal</code>{" "}
          + optional <code style={{ color: "var(--cc-gold)" }}>state.json</code> tickers.
        </li>
        <li>
          <strong>Backend:</strong>{" "}
          <a href={urls.apiHealth} target="_blank" rel="noreferrer" style={{ color: "var(--cc-blue)" }}>
            {urls.apiHealth}
          </a>{" "}
          for live dependency dots in the sidebar.
        </li>
      </ul>
    </>
  );
}

function DefiPanel() {
  return (
    <>
      <h2 className="hub-section-title">DeFi yields</h2>
      <div className="hub-actions" style={{ marginBottom: "1rem", justifyContent: "flex-start" }}>
        <a className="hub-btn hub-btn-primary" href={urls.streamlit} target="_blank" rel="noreferrer">
          DeFi tab in Streamlit
        </a>
        <a className="hub-btn hub-btn-secondary" href={urls.defiLlama} target="_blank" rel="noreferrer">
          DeFi Llama
        </a>
      </div>
      <div className="hub-grid">
        <div className="hub-card">
          <h3>Pools</h3>
          <p>Tracked count, average APY, aggregate TVL — same summary header as Streamlit.</p>
        </div>
        <div className="hub-card">
          <h3>Tables</h3>
          <p>Pandas styler tints APY from cool tones toward rich green as rates climb.</p>
        </div>
      </div>
    </>
  );
}

function VideoPanel() {
  return (
    <>
      <h2 className="hub-section-title">Video factory</h2>
      <div className="hub-actions" style={{ marginBottom: "1rem", justifyContent: "flex-start" }}>
        <a className="hub-btn hub-btn-primary" href={urls.streamlit} target="_blank" rel="noreferrer">
          Video factory tab
        </a>
        <a className="hub-btn hub-btn-secondary" href={urls.mpt} target="_blank" rel="noreferrer">
          MoneyPrinterTurbo
        </a>
      </div>
      <div className="hub-card" style={{ maxWidth: 720 }}>
        <h3>MoneyPrinterTurbo</h3>
        <p>
          Submit top market with vibe presets; run bridge for batch paths. Payloads include{" "}
          <strong style={{ color: "var(--cc-green)" }}>video_description</strong> with Cash Cow Alpha
          footer and X follow intent.
        </p>
      </div>
    </>
  );
}

function OrchestratorPanel() {
  return (
    <>
      <h2 className="hub-section-title">Orchestrator</h2>
      <div className="hub-actions" style={{ marginBottom: "1rem", justifyContent: "flex-start" }}>
        <a className="hub-btn hub-btn-primary" href={urls.streamlit} target="_blank" rel="noreferrer">
          Orchestrator tab
        </a>
      </div>
      <div className="hub-card" style={{ maxWidth: 720 }}>
        <h3>Pipeline</h3>
        <p>
          One-shot cycles, last plan JSON, and tail of <code style={{ color: "var(--cc-gold)" }}>pipeline.log</code>{" "}
          in a monospace block with dark chrome.
        </p>
      </div>
    </>
  );
}

function AlphaPanel() {
  return (
    <>
      <h2 className="hub-section-title">Cash Cow Alpha Signal</h2>
      <div className="hub-actions" style={{ marginBottom: "1rem", justifyContent: "flex-start" }}>
        <a className="hub-btn hub-btn-primary" href={urls.streamlit} target="_blank" rel="noreferrer">
          Polymarket + Alpha in Streamlit
        </a>
        <a className="hub-btn hub-btn-secondary" href={`${urls.api.replace(/\/$/, "")}/api/v1/alpha-signals`} target="_blank" rel="noreferrer">
          GET /alpha-signals (JSON)
        </a>
      </div>
      <div className="hub-card" style={{ maxWidth: 720 }}>
        <h3>
          <span className="hub-tag">Signal</span> Divergence copy-watchlist
        </h3>
        <p>
          Thresholded divergence index + intel alerts; soft tier when markets are quiet. Sidebar
          tracks aggregate copy-div clicks; follow No Limits (configurable) on X from env.
        </p>
      </div>
      <p className="hub-disclaimer">
        Not financial advice. Whop / performance-fee monetization are roadmap items, not shipped in
        this hub.
      </p>
    </>
  );
}

function ApiPanel() {
  return (
    <>
      <h2 className="hub-section-title">API & integrations</h2>
      <div className="hub-actions" style={{ marginBottom: "1rem", justifyContent: "flex-start" }}>
        <a className="hub-btn hub-btn-primary" href={urls.apiDocs} target="_blank" rel="noreferrer">
          Swagger UI
        </a>
        <a className="hub-btn hub-btn-secondary" href={urls.apiHealth} target="_blank" rel="noreferrer">
          Health JSON
        </a>
      </div>
      <ul className="hub-list">
        <li>
          <strong>GET</strong> /api/v1/health — service dependency map
        </li>
        <li>
          <strong>GET</strong> /api/v1/dashboard — markets, DeFi, signals, alpha bundle
        </li>
        <li>
          <strong>GET</strong> /api/v1/alpha-signals — Cash Cow Alpha rows + click total
        </li>
        <li>
          <strong>POST</strong> /api/v1/track-copy-click — funnel analytics (JSON body)
        </li>
        <li>
          <strong>POST</strong> /api/v1/preview-script — MoneyPrinterTurbo subject bundle
        </li>
      </ul>
      <ConnectedApps />
    </>
  );
}
