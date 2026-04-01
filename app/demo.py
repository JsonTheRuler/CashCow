"""Cash Cow demo mode -- the insurance policy.

Run this if everything else breaks during the hackathon demo.
Produces ~30 seconds of theatrical terminal output showing the full pipeline.

Usage:
    python -m app.demo
"""

from __future__ import annotations

import random
import time
from dataclasses import dataclass

from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
)
from rich.table import Table
from rich.text import Text

console = Console()

# ---------------------------------------------------------------------------
# Mock data -- realistic Polymarket questions & DeFi pools
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Market:
    question: str
    yes_pct: float
    volume: float
    category: str
    end_date: str
    score: float = 0.0


@dataclass(frozen=True)
class DeFiPool:
    protocol: str
    pair: str
    chain: str
    apy: float
    tvl: float


@dataclass(frozen=True)
class TradingSignal:
    asset: str
    direction: str
    confidence: float
    timeframe: str
    entry: float
    target: float
    stop: float


MOCK_MARKETS: list[Market] = [
    Market("Will Bitcoin hit $150K by July 2026?", 68.0, 4_200_000, "Crypto", "2026-07-01"),
    Market("Will the Fed cut rates before Sept 2026?", 72.0, 8_500_000, "Economics", "2026-09-01"),
    Market("Will TikTok be banned in the US by 2027?", 34.0, 12_000_000, "Tech/Policy", "2027-01-01"),
    Market("Will SpaceX Starship complete orbital flight?", 81.0, 3_700_000, "Space", "2026-04-15"),
    Market("Will GPT-5 be released before June 2026?", 62.0, 5_100_000, "AI", "2026-06-01"),
    Market("Will Ethereum flip Bitcoin market cap?", 8.0, 2_800_000, "Crypto", "2026-12-31"),
    Market("Will US enter recession in 2026?", 29.0, 9_400_000, "Economics", "2026-12-31"),
    Market("Will there be a US government shutdown in Q2?", 45.0, 1_600_000, "Politics", "2026-06-30"),
]

MOCK_DEFI: list[DeFiPool] = [
    DeFiPool("Aave", "USDC/ETH", "Ethereum", 12.4, 890_000_000),
    DeFiPool("Uniswap V3", "ETH/USDT", "Ethereum", 18.7, 1_200_000_000),
    DeFiPool("Curve", "3pool", "Ethereum", 5.2, 3_400_000_000),
    DeFiPool("GMX", "GLP", "Arbitrum", 22.1, 540_000_000),
    DeFiPool("Lido", "stETH", "Ethereum", 4.1, 14_000_000_000),
    DeFiPool("Pendle", "PT-eETH", "Ethereum", 31.5, 320_000_000),
    DeFiPool("Aerodrome", "USDC/WETH", "Base", 28.3, 210_000_000),
    DeFiPool("Hyperliquid", "HLP", "Hyperliquid", 19.8, 1_800_000_000),
]

MOCK_SIGNALS: list[TradingSignal] = [
    TradingSignal("BTC", "LONG", 0.82, "4H", 96_500, 102_000, 94_200),
    TradingSignal("ETH", "LONG", 0.74, "1D", 3_850, 4_200, 3_650),
    TradingSignal("SOL", "SHORT", 0.67, "4H", 178.5, 165.0, 185.0),
]


# ---------------------------------------------------------------------------
# Scoring algorithm (deterministic but theatrical)
# ---------------------------------------------------------------------------

def _score_market(market: Market) -> float:
    """Score a market on virality potential (0-100)."""
    volume_score = min(market.volume / 10_000_000, 1.0) * 30
    controversy = (50 - abs(market.yes_pct - 50)) / 50 * 25
    base = 20 + random.random() * 10
    return min(round(volume_score + controversy + base, 1), 100.0)


# ---------------------------------------------------------------------------
# Demo runner
# ---------------------------------------------------------------------------

def _fmt_volume(v: float) -> str:
    if v >= 1_000_000_000:
        return f"${v / 1_000_000_000:.1f}B"
    if v >= 1_000_000:
        return f"${v / 1_000_000:.1f}M"
    return f"${v / 1_000:.0f}K"


def run_demo() -> None:
    """Execute the full theatrical demo pipeline."""
    random.seed(42)

    console.print()
    console.print(
        Panel(
            Text("CASH COW", style="bold white", justify="center"),
            subtitle="prediction markets x short-form video",
            border_style="bright_yellow",
            padding=(1, 4),
        )
    )
    console.print()
    time.sleep(1.0)

    # -- Phase 1: Fetch markets ------------------------------------------------
    console.rule("[bold cyan]Phase 1: Fetching Prediction Markets[/]")
    console.print()
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("{task.completed}/{task.total}"),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("Scanning Polymarket...", total=len(MOCK_MARKETS))
        for m in MOCK_MARKETS:
            time.sleep(0.4)
            progress.advance(task)
            console.print(f"  [dim]Found:[/] {m.question} ({m.yes_pct}% YES, {_fmt_volume(m.volume)})")
    console.print()
    time.sleep(0.5)

    # -- Phase 2: Score & rank -------------------------------------------------
    console.rule("[bold cyan]Phase 2: Scoring & Ranking Markets[/]")
    console.print()
    scored: list[Market] = []
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("{task.completed}/{task.total}"),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("Running virality scorer...", total=len(MOCK_MARKETS))
        for m in MOCK_MARKETS:
            s = _score_market(m)
            scored.append(Market(
                question=m.question,
                yes_pct=m.yes_pct,
                volume=m.volume,
                category=m.category,
                end_date=m.end_date,
                score=s,
            ))
            time.sleep(0.35)
            progress.advance(task)

    ranked = sorted(scored, key=lambda x: x.score, reverse=True)

    table = Table(title="Ranked Markets", border_style="bright_yellow")
    table.add_column("#", style="dim", width=3)
    table.add_column("Question", style="white", max_width=50)
    table.add_column("YES %", justify="right", style="green")
    table.add_column("Volume", justify="right", style="cyan")
    table.add_column("Category", style="magenta")
    table.add_column("Score", justify="right", style="bold yellow")

    for i, m in enumerate(ranked, 1):
        table.add_row(
            str(i),
            m.question,
            f"{m.yes_pct:.0f}%",
            _fmt_volume(m.volume),
            m.category,
            f"{m.score:.1f}",
        )

    console.print()
    console.print(table)
    console.print()
    time.sleep(1.0)

    # -- Phase 3: Generate video for top market --------------------------------
    top = ranked[0]
    console.rule("[bold cyan]Phase 3: Generating Video[/]")
    console.print()
    console.print(f"  [bold]Target:[/] {top.question}")
    console.print(f"  [bold]Template:[/] hot_take (score={top.score})")
    console.print()

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(bar_width=40),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        stages = [
            ("Generating script with GPT-4o...", 2.0),
            ("Selecting B-roll footage...", 1.5),
            ("Synthesizing voiceover...", 2.5),
            ("Rendering video with MoneyPrinterTurbo...", 3.0),
            ("Adding captions & effects...", 1.5),
        ]
        for desc, duration in stages:
            task = progress.add_task(desc, total=100)
            steps = int(duration / 0.05)
            for _ in range(steps):
                time.sleep(0.05)
                progress.advance(task, 100 / steps)

    console.print()
    console.print("  [bold green]Video generated:[/] output/cashcow_001.mp4 (62s, 1080x1920)")
    console.print()
    time.sleep(0.5)

    # -- Phase 4: TradingAgents signals ----------------------------------------
    console.rule("[bold cyan]Phase 4: TradingAgents Signals[/]")
    console.print()

    signals_table = Table(border_style="bright_blue")
    signals_table.add_column("Asset", style="bold white")
    signals_table.add_column("Direction", justify="center")
    signals_table.add_column("Confidence", justify="right", style="yellow")
    signals_table.add_column("Timeframe", justify="center", style="dim")
    signals_table.add_column("Entry", justify="right", style="cyan")
    signals_table.add_column("Target", justify="right", style="green")
    signals_table.add_column("Stop", justify="right", style="red")

    for sig in MOCK_SIGNALS:
        direction_style = "bold green" if sig.direction == "LONG" else "bold red"
        signals_table.add_row(
            sig.asset,
            Text(sig.direction, style=direction_style),
            f"{sig.confidence:.0%}",
            sig.timeframe,
            f"${sig.entry:,.1f}",
            f"${sig.target:,.1f}",
            f"${sig.stop:,.1f}",
        )

    console.print(signals_table)
    console.print()
    time.sleep(1.0)

    # -- Phase 5: DeFi yields --------------------------------------------------
    console.rule("[bold cyan]Phase 5: Top DeFi Yield Opportunities[/]")
    console.print()

    defi_table = Table(border_style="bright_green")
    defi_table.add_column("Protocol", style="bold white")
    defi_table.add_column("Pair", style="cyan")
    defi_table.add_column("Chain", style="magenta")
    defi_table.add_column("APY", justify="right", style="bold green")
    defi_table.add_column("TVL", justify="right", style="yellow")

    sorted_defi = sorted(MOCK_DEFI, key=lambda p: p.apy, reverse=True)
    for pool in sorted_defi:
        defi_table.add_row(
            pool.protocol,
            pool.pair,
            pool.chain,
            f"{pool.apy:.1f}%",
            _fmt_volume(pool.tvl),
        )

    console.print(defi_table)
    console.print()
    time.sleep(1.0)

    # -- Summary ---------------------------------------------------------------
    console.rule("[bold cyan]Pipeline Complete[/]")
    console.print()

    summary = Table.grid(padding=(0, 2))
    summary.add_column(style="bold")
    summary.add_column()
    summary.add_row("Markets scanned:", f"[cyan]{len(MOCK_MARKETS)}[/]")
    summary.add_row("Top market:", f"[yellow]{top.question}[/]")
    summary.add_row("Top score:", f"[bold yellow]{top.score:.1f}/100[/]")
    summary.add_row("Videos generated:", "[green]1[/]")
    summary.add_row("Trading signals:", f"[blue]{len(MOCK_SIGNALS)}[/]")
    summary.add_row("DeFi pools tracked:", f"[green]{len(MOCK_DEFI)}[/]")
    summary.add_row("Total market volume:", f"[cyan]{_fmt_volume(sum(m.volume for m in MOCK_MARKETS))}[/]")

    console.print(Panel(summary, title="Summary", border_style="bright_yellow"))
    console.print()
    console.print("[bold bright_yellow]Cash Cow[/] [dim]-- autonomous market intelligence -> viral content[/]")
    console.print()


if __name__ == "__main__":
    run_demo()
