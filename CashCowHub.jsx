import { useState, useEffect, useCallback } from "react";
import { TrendingUp, TrendingDown, Activity, DollarSign, Video, Zap, Shield, Layers, Eye, Radio, BarChart3, Brain, Newspaper, Users, Play, ChevronRight, ExternalLink } from "lucide-react";

const API = "https://gamma-api.polymarket.com";
const DEFI = "https://api.llama.fi";

const APPS = [
  {
    id: "scanner", title: "Market scanner", subtitle: "Live Polymarket intelligence",
    icon: Activity, color: "#10b981", gradient: "from-emerald-900/40 to-emerald-950/20",
    desc: "Score and rank trending prediction markets by volume, decisiveness, momentum, and social divergence. Powered by scorer.py + sentiment.py.",
    functions: ["fetch_and_score()", "top_markets()", "score_single()", "social_boost()", "get_social_score()"],
    port: 8502, path: "/?tab=markets", status: "live",
    preview: null,
  },
  {
    id: "video", title: "Video factory", subtitle: "Polymarket to TikTok pipeline",
    icon: Video, color: "#a855f7", gradient: "from-purple-900/40 to-purple-950/20",
    desc: "Generate short-form videos from trending markets. 22 Grok viral hooks, auto-scripting, Edge TTS voiceover, Pexels footage, MoviePy assembly.",
    functions: ["run_bridge()", "submit_video()", "generate_script()", "breaking_news()", "hot_take()", "countdown()"],
    port: 8080, path: "/", status: "needs_mpt",
    preview: null,
  },
  {
    id: "signals", title: "Trading signals", subtitle: "Multi-agent LLM analysis",
    icon: Zap, color: "#f59e0b", gradient: "from-amber-900/40 to-amber-950/20",
    desc: "Run TradingAgents framework with fundamental, sentiment, technical analysts + risk manager. Returns Buy/Hold/Sell with confidence scores.",
    functions: ["get_signal()", "get_crypto_signal()", "TradingAgentsGraph.propagate()"],
    port: 8502, path: "/?tab=signals", status: "needs_key",
    preview: null,
  },
  {
    id: "defi", title: "DeFi yield tracker", subtitle: "Cross-chain yield intelligence",
    icon: DollarSign, color: "#3b82f6", gradient: "from-blue-900/40 to-blue-950/20",
    desc: "Track 13,000+ yield pools across 535 protocols on 119 chains. Filter stablecoins, rank by quality score, monitor chain health.",
    functions: ["get_top_yield_pools()", "get_chain_tvls()", "get_stablecoin_pools()", "get_defi_summary()"],
    port: 8502, path: "/?tab=yields", status: "live",
    preview: null,
  },
  {
    id: "social", title: "Social intelligence", subtitle: "X/Twitter sentiment divergence",
    icon: Eye, color: "#ec4899", gradient: "from-pink-900/40 to-pink-950/20",
    desc: "Grok-powered sentiment analysis. Detect when X buzz diverges from market odds. 22 viral hook templates. Divergence scoring 1-10.",
    functions: ["get_top_divergences()", "social_boost()", "enrich_market_with_sentiment()", "get_social_score()"],
    port: 8502, path: "/?tab=markets", status: "static",
    preview: null,
  },
  {
    id: "content", title: "Content studio", subtitle: "YouTube, TikTok, Twitter, email",
    icon: Newspaper, color: "#f97316", gradient: "from-orange-900/40 to-orange-950/20",
    desc: "Full MoneyPrinterV2 content engine. YouTube Shorts generation + upload, Twitter bot, Amazon affiliate marketing, local business outreach, PostBridge cross-posting.",
    functions: ["YouTube.generate()", "Twitter.post()", "AFM.scrape()", "Outreach.send()", "PostBridge.crosspost()"],
    port: 8501, path: "/", status: "needs_config",
    preview: null,
  },
  {
    id: "forecast", title: "Market forecaster", subtitle: "TimesFM neural predictions",
    icon: TrendingUp, color: "#06b6d4", gradient: "from-cyan-900/40 to-cyan-950/20",
    desc: "Google TimesFM 2.5 200M foundation model for price trajectory forecasting. CLOB price history ingestion, quantile confidence bands, linear fallback.",
    functions: ["forecast_market()", "linear_forecast()", "fetch_clob_price_history()", "full_analytics()", "volume_momentum()"],
    port: 8090, path: "/api/v1/forecast/{id}", status: "fallback",
    preview: null,
  },
  {
    id: "orchestrator", title: "Orchestrator", subtitle: "Autonomous AI brain",
    icon: Brain, color: "#8b5cf6", gradient: "from-violet-900/40 to-violet-950/20",
    desc: "Gemini-powered AI Plan-Interpreter. Builds system snapshots, generates action plans (GENERATE_VIDEO, LOG_DEFI, SKIP), executes autonomously on 2-minute cycles.",
    functions: ["run_once()", "run_loop()", "build_snapshot()", "call_gemini_interpreter()", "execute_plan()"],
    port: 8502, path: "/?tab=orchestrator", status: "needs_key",
    preview: null,
  },
];

const STATUS_MAP = {
  live: { label: "Live", color: "#10b981", dot: true },
  needs_mpt: { label: "Needs MPT", color: "#f59e0b", dot: false },
  needs_key: { label: "Needs API key", color: "#f59e0b", dot: false },
  needs_config: { label: "Needs config", color: "#f59e0b", dot: false },
  static: { label: "Static data", color: "#3b82f6", dot: false },
  fallback: { label: "Fallback mode", color: "#06b6d4", dot: false },
  offline: { label: "Offline", color: "#ef4444", dot: false },
};

function CowSvg({ pulse }) {
  return (
    <svg viewBox="0 0 200 160" width="200" height="160" style={{ filter: "drop-shadow(0 0 40px rgba(245, 158, 11, 0.15))" }}>
      <ellipse cx="100" cy="120" rx="60" ry="35" fill="#1a1a2e" stroke="#f59e0b" strokeWidth="1.5" opacity="0.6" />
      <ellipse cx="100" cy="80" rx="50" ry="40" fill="#1f1f35" stroke="#f59e0b" strokeWidth="1.5">
        {pulse && <animate attributeName="ry" values="40;42;40" dur="2s" repeatCount="indefinite" />}
      </ellipse>
      <circle cx="80" cy="70" r="6" fill="#0a0a0f" stroke="#f59e0b" strokeWidth="1" />
      <circle cx="120" cy="70" r="6" fill="#0a0a0f" stroke="#f59e0b" strokeWidth="1" />
      <circle cx="82" cy="68" r="2" fill="#f59e0b" opacity="0.8" />
      <circle cx="122" cy="68" r="2" fill="#f59e0b" opacity="0.8" />
      <ellipse cx="100" cy="85" rx="10" ry="6" fill="none" stroke="#f59e0b" strokeWidth="1" opacity="0.5" />
      <line x1="55" y1="55" x2="35" y2="40" stroke="#f59e0b" strokeWidth="2" strokeLinecap="round" />
      <line x1="145" y1="55" x2="165" y2="40" stroke="#f59e0b" strokeWidth="2" strokeLinecap="round" />
      {[75, 90, 105, 120].map((x, i) => (
        <g key={i}>
          <line x1={x} y1="115" x2={x - 3} y2="145" stroke="#f59e0b" strokeWidth="1.5" opacity="0.4" />
          {pulse && (
            <circle cx={x - 3} cy="148" r="2" fill="#10b981" opacity="0.6">
              <animate attributeName="opacity" values="0.6;0;0.6" dur={`${1.5 + i * 0.3}s`} repeatCount="indefinite" />
              <animate attributeName="cy" values="148;155;148" dur={`${1.5 + i * 0.3}s`} repeatCount="indefinite" />
            </circle>
          )}
        </g>
      ))}
      <text x="100" y="100" textAnchor="middle" fill="#f59e0b" fontSize="10" fontWeight="600" opacity="0.7">MOO</text>
    </svg>
  );
}

function StatusBadge({ status }) {
  const s = STATUS_MAP[status] || STATUS_MAP.offline;
  return (
    <div className="flex items-center gap-1.5">
      {s.dot && (
        <span className="relative flex h-2 w-2">
          <span className="absolute inline-flex h-full w-full rounded-full opacity-75 animate-ping" style={{ background: s.color }} />
          <span className="inline-flex h-2 w-2 rounded-full" style={{ background: s.color }} />
        </span>
      )}
      {!s.dot && <span className="w-2 h-2 rounded-full" style={{ background: s.color }} />}
      <span className="text-xs font-medium" style={{ color: s.color }}>{s.label}</span>
    </div>
  );
}

function AppCard({ app, onClick, stats }) {
  const Icon = app.icon;
  const [hovered, setHovered] = useState(false);
  return (
    <div
      onClick={() => onClick(app)}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      className="relative rounded-2xl p-5 cursor-pointer transition-all duration-300"
      style={{
        background: hovered ? "rgba(255,255,255,0.05)" : "rgba(255,255,255,0.02)",
        border: `1px solid ${hovered ? app.color + "40" : "rgba(255,255,255,0.06)"}`,
        transform: hovered ? "translateY(-2px)" : "none",
        boxShadow: hovered ? `0 8px 32px ${app.color}15` : "none",
      }}
    >
      <div className="flex items-start justify-between mb-3">
        <div className="p-2.5 rounded-xl" style={{ background: app.color + "15", border: `1px solid ${app.color}25` }}>
          <Icon size={20} style={{ color: app.color }} />
        </div>
        <StatusBadge status={app.status} />
      </div>
      <h3 className="text-base font-semibold mb-0.5" style={{ color: "#f0f0f5" }}>{app.title}</h3>
      <p className="text-xs mb-3" style={{ color: "rgba(255,255,255,0.4)" }}>{app.subtitle}</p>
      <p className="text-xs leading-relaxed mb-3" style={{ color: "rgba(255,255,255,0.35)" }}>{app.desc}</p>
      {stats && (
        <div className="flex gap-3 mb-3">
          {stats.map((s, i) => (
            <div key={i} className="text-center">
              <div className="text-sm font-bold" style={{ color: app.color, fontFamily: "'SF Mono', monospace" }}>{s.value}</div>
              <div className="text-xs" style={{ color: "rgba(255,255,255,0.25)" }}>{s.label}</div>
            </div>
          ))}
        </div>
      )}
      <div className="flex items-center justify-between pt-3" style={{ borderTop: "1px solid rgba(255,255,255,0.04)" }}>
        <div className="flex flex-wrap gap-1">
          {app.functions.slice(0, 2).map((f, i) => (
            <span key={i} className="px-1.5 py-0.5 rounded text-xs" style={{
              background: "rgba(255,255,255,0.04)", color: "rgba(255,255,255,0.3)",
              fontFamily: "'SF Mono', monospace", fontSize: "10px"
            }}>{f}</span>
          ))}
          {app.functions.length > 2 && (
            <span className="text-xs" style={{ color: "rgba(255,255,255,0.2)" }}>+{app.functions.length - 2}</span>
          )}
        </div>
        <div className="flex items-center gap-1 text-xs" style={{ color: hovered ? app.color : "rgba(255,255,255,0.2)" }}>
          Open <ChevronRight size={12} />
        </div>
      </div>
    </div>
  );
}

export default function CashCowHub() {
  const [selectedApp, setSelectedApp] = useState(null);
  const [marketCount, setMarketCount] = useState(null);
  const [totalVol, setTotalVol] = useState(null);
  const [yieldCount, setYieldCount] = useState(null);
  const [bestApy, setBestApy] = useState(null);
  const [now, setNow] = useState(new Date());

  useEffect(() => {
    const t = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(t);
  }, []);

  useEffect(() => {
    fetch(`${API}/markets?active=true&limit=20&order=volume24hr&ascending=false`)
      .then(r => r.json()).then(d => {
        setMarketCount(d.length);
        setTotalVol(d.reduce((s, m) => s + parseFloat(m.volume24hr || 0), 0));
      }).catch(() => {});
    fetch(`${DEFI}/pools`).then(r => r.json()).then(d => {
      const pools = (d.data || []).filter(p => p.stablecoin && p.apy > 3 && p.apy < 100 && (p.tvlUsd || 0) > 1e6);
      setYieldCount(pools.length);
      setBestApy(Math.max(...pools.map(p => p.apy)));
    }).catch(() => {});
  }, []);

  const scannerStats = marketCount ? [
    { value: marketCount.toString(), label: "markets" },
    { value: totalVol ? `$${(totalVol / 1e6).toFixed(1)}M` : "...", label: "24h vol" },
  ] : null;

  const defiStats = yieldCount ? [
    { value: yieldCount.toString(), label: "pools" },
    { value: bestApy ? `${bestApy.toFixed(1)}%` : "...", label: "best APY" },
  ] : null;

  const appStats = {
    scanner: scannerStats,
    defi: defiStats,
    social: [{ value: "5", label: "alerts" }, { value: "9/10", label: "top div" }],
    signals: [{ value: "4", label: "tickers" }, { value: "87%", label: "top conf" }],
  };

  return (
    <div className="min-h-screen" style={{ background: "#08080f", color: "#e0e0e5", fontFamily: "'Sora', 'Inter', -apple-system, sans-serif" }}>
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Sora:wght@300;400;500;600;700&display=swap');
        @keyframes float { 0%,100% { transform: translateY(0); } 50% { transform: translateY(-8px); } }
        @keyframes grain { 0% { transform: translate(0,0); } 10% { transform: translate(-2%,-2%); } 20% { transform: translate(2%,2%); }
          30% { transform: translate(-1%,1%); } 40% { transform: translate(1%,-1%); } 50% { transform: translate(-2%,2%); }
          60% { transform: translate(2%,-2%); } 70% { transform: translate(-1%,-1%); } 80% { transform: translate(1%,1%); }
          90% { transform: translate(-2%,0%); } 100% { transform: translate(0,0); } }
      `}</style>

      <div style={{
        position: "fixed", top: 0, left: 0, right: 0, bottom: 0, pointerEvents: "none", opacity: 0.03,
        backgroundImage: "radial-gradient(circle at 25% 25%, #f59e0b 1px, transparent 1px), radial-gradient(circle at 75% 75%, #10b981 1px, transparent 1px)",
        backgroundSize: "80px 80px", animation: "grain 8s steps(10) infinite",
      }} />

      <div className="relative max-w-7xl mx-auto px-6">
        <div className="text-center pt-12 pb-8">
          <div style={{ animation: "float 4s ease-in-out infinite" }}>
            <CowSvg pulse={true} />
          </div>
          <h1 className="text-4xl font-bold mt-4 tracking-tight" style={{
            background: "linear-gradient(135deg, #f59e0b, #10b981)", WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent",
            letterSpacing: "-0.03em",
          }}>Cash Cow</h1>
          <p className="text-sm mt-2" style={{ color: "rgba(255,255,255,0.35)" }}>
            Autonomous market intelligence engine — {now.toLocaleTimeString()}
          </p>

          <div className="flex justify-center gap-6 mt-5">
            {[
              { label: "Markets", value: marketCount ? marketCount.toString() : "...", color: "#10b981" },
              { label: "24h volume", value: totalVol ? `$${(totalVol / 1e6).toFixed(1)}M` : "...", color: "#f59e0b" },
              { label: "Yield pools", value: yieldCount ? yieldCount.toString() : "...", color: "#3b82f6" },
              { label: "Best APY", value: bestApy ? `${bestApy.toFixed(1)}%` : "...", color: "#a855f7" },
            ].map((m, i) => (
              <div key={i} className="text-center px-4">
                <div className="text-lg font-bold" style={{ color: m.color, fontFamily: "'SF Mono', 'Fira Code', monospace" }}>{m.value}</div>
                <div className="text-xs" style={{ color: "rgba(255,255,255,0.3)" }}>{m.label}</div>
              </div>
            ))}
          </div>
        </div>

        <div className="grid gap-4 pb-16" style={{ gridTemplateColumns: "repeat(4, minmax(0, 1fr))" }}>
          {APPS.map(app => (
            <AppCard key={app.id} app={app} onClick={setSelectedApp} stats={appStats[app.id] || null} />
          ))}
        </div>

        {selectedApp && (
          <div className="fixed inset-0 flex items-center justify-center z-50" style={{ background: "rgba(0,0,0,0.7)", backdropFilter: "blur(8px)" }}
            onClick={() => setSelectedApp(null)}>
            <div className="max-w-lg w-full mx-4 rounded-2xl p-6" style={{ background: "#12121f", border: `1px solid ${selectedApp.color}30` }}
              onClick={e => e.stopPropagation()}>
              <div className="flex items-center gap-3 mb-4">
                <div className="p-3 rounded-xl" style={{ background: selectedApp.color + "15" }}>
                  <selectedApp.icon size={24} style={{ color: selectedApp.color }} />
                </div>
                <div>
                  <h2 className="text-xl font-bold" style={{ color: "#f0f0f5" }}>{selectedApp.title}</h2>
                  <p className="text-xs" style={{ color: "rgba(255,255,255,0.4)" }}>{selectedApp.subtitle}</p>
                </div>
              </div>
              <p className="text-sm mb-4" style={{ color: "rgba(255,255,255,0.5)", lineHeight: 1.6 }}>{selectedApp.desc}</p>
              <div className="mb-4">
                <p className="text-xs font-medium mb-2" style={{ color: "rgba(255,255,255,0.3)" }}>Functions</p>
                <div className="flex flex-wrap gap-1.5">
                  {selectedApp.functions.map((f, i) => (
                    <span key={i} className="px-2 py-1 rounded-md text-xs" style={{
                      background: "rgba(255,255,255,0.04)", color: selectedApp.color,
                      fontFamily: "'SF Mono', monospace", fontSize: "11px",
                      border: `1px solid ${selectedApp.color}20`
                    }}>{f}</span>
                  ))}
                </div>
              </div>
              <div className="flex gap-3">
                <button className="flex-1 flex items-center justify-center gap-2 py-2.5 rounded-xl text-sm font-medium transition-all"
                  style={{ background: selectedApp.color + "20", color: selectedApp.color, border: `1px solid ${selectedApp.color}30` }}
                  onClick={() => { window.open(`http://localhost:${selectedApp.port}${selectedApp.path}`, "_blank"); }}>
                  <Play size={14} /> Launch app
                </button>
                <button className="flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl text-sm transition-all"
                  style={{ background: "rgba(255,255,255,0.04)", color: "rgba(255,255,255,0.5)", border: "1px solid rgba(255,255,255,0.08)" }}
                  onClick={() => setSelectedApp(null)}>
                  Close
                </button>
              </div>
            </div>
          </div>
        )}

        <div className="text-center pb-8">
          <p className="text-xs" style={{ color: "rgba(255,255,255,0.15)" }}>
            Cash Cow v0.2 — scorer + bridge + orchestrator + forecaster + defi + signals + analytics + prompts + sentiment + api
          </p>
        </div>
      </div>
    </div>
  );
}
