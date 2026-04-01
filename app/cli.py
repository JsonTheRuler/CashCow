"""Cash Cow CLI -- command-line interface for the autonomous pipeline.

Usage:
    python -m app.cli scan        Fetch and score all markets
    python -m app.cli generate N  Generate video for market #N
    python -m app.cli yields      Show top DeFi yields
    python -m app.cli signals     Show TradingAgents signals
    python -m app.cli demo        Run demo mode
    python -m app.cli status      Show system health
    python -m app.cli run         Start the full autonomous pipeline loop
"""

from __future__ import annotations

import random
import sys
import time
from typing import Optional

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from app.demo import (
    MOCK_DEFI,
    MOCK_MARKETS,
    MOCK_SIGNALS,
    _fmt_volume,
    _score_market,
    run_demo,
    Market,
)
from app.prompts import TEMPLATES

console = Console()

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _ranked_markets() -> list[Market]:
    """Score and rank all mock markets."""
    random.seed(42)
    scored = [
        Market(
            question=m.question,
            yes_pct=m.yes_pct,
            volume=m.volume,
            category=m.category,
            end_date=m.end_date,
            score=_score_market(m),
        )
        for m in MOCK_MARKETS
    ]
    return sorted(scored, key=lambda x: x.score, reverse=True)


def _pick_template(market: Market) -> str:
    """Select the best template for a market based on its attributes."""
    if market.score > 70:
        return "hot_take"
    if market.yes_pct > 75 or market.yes_pct < 25:
        return "breaking_news"
    if abs(market.yes_pct - 50) < 15:
        return "deep_analysis"
    return "countdown"


# ---------------------------------------------------------------------------
# CLI group
# ---------------------------------------------------------------------------


@click.group()
@click.version_option(version="0.1.0", prog_name="cashcow")
def cli() -> None:
    """Cash Cow -- autonomous market intelligence to viral content."""
    pass


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


@cli.command()
def scan() -> None:
    """Fetch and score all markets, print ranked list."""
    console.print()
    console.print("[bold cyan]Scanning prediction markets...[/]")
    console.print()

    ranked = _ranked_markets()

    table = Table(title="Ranked Markets", border_style="bright_yellow")
    table.add_column("#", style="dim", width=3)
    table.add_column("Question", style="white", max_width=50)
    table.add_column("YES %", justify="right", style="green")
    table.add_column("Volume", justify="right", style="cyan")
    table.add_column("Category", style="magenta")
    table.add_column("Score", justify="right", style="bold yellow")
    table.add_column("Template", style="dim")

    for i, m in enumerate(ranked, 1):
        table.add_row(
            str(i),
            m.question,
            f"{m.yes_pct:.0f}%",
            _fmt_volume(m.volume),
            m.category,
            f"{m.score:.1f}",
            _pick_template(m),
        )

    console.print(table)
    console.print()


@cli.command()
@click.argument("n", type=int)
def generate(n: int) -> None:
    """Generate video script for market #N (1-indexed from scan results)."""
    ranked = _ranked_markets()

    if n < 1 or n > len(ranked):
        console.print(f"[bold red]Error:[/] Market #{n} not found. Valid range: 1-{len(ranked)}")
        raise SystemExit(1)

    market = ranked[n - 1]
    template_name = _pick_template(market)

    console.print()
    console.print(Panel(
        f"[bold]{market.question}[/]\n"
        f"YES: {market.yes_pct:.0f}%  |  Volume: {_fmt_volume(market.volume)}  |  "
        f"Score: {market.score:.1f}",
        title=f"Market #{n}",
        border_style="bright_yellow",
    ))
    console.print()

    # Build template kwargs based on which template we picked
    template_fn = TEMPLATES[template_name]
    kwargs: dict = {"question": market.question, "yes_pct": market.yes_pct}

    if template_name == "breaking_news":
        kwargs["volume"] = market.volume
        kwargs["description"] = "This market is seeing unprecedented volume."
    elif template_name == "deep_analysis":
        kwargs["no_pct"] = 100 - market.yes_pct
        kwargs["volume"] = market.volume
        kwargs["forecast_trend"] = "steadily bullish over the past 7 days"
    elif template_name == "hot_take":
        kwargs["volume"] = market.volume
    elif template_name == "countdown":
        kwargs["end_date"] = market.end_date
        kwargs["volume"] = market.volume
    elif template_name == "explainer":
        kwargs["description"] = "This is one of the most-watched markets right now."

    script = template_fn(**kwargs)

    console.print(f"[bold]Template:[/] {template_name}")
    console.print(f"[bold]Word count:[/] {len(script.split())}")
    console.print()
    console.print(Panel(script, title="Generated Script", border_style="bright_green"))
    console.print()
    console.print("[dim]In production, this script would be sent to MoneyPrinterTurbo for video rendering.[/]")
    console.print()


@cli.command()
def yields() -> None:
    """Show top DeFi yield opportunities."""
    console.print()
    table = Table(title="Top DeFi Yields", border_style="bright_green")
    table.add_column("Protocol", style="bold white")
    table.add_column("Pair", style="cyan")
    table.add_column("Chain", style="magenta")
    table.add_column("APY", justify="right", style="bold green")
    table.add_column("TVL", justify="right", style="yellow")

    sorted_defi = sorted(MOCK_DEFI, key=lambda p: p.apy, reverse=True)
    for pool in sorted_defi:
        table.add_row(
            pool.protocol,
            pool.pair,
            pool.chain,
            f"{pool.apy:.1f}%",
            _fmt_volume(pool.tvl),
        )

    console.print(table)
    console.print()


@cli.command()
def signals() -> None:
    """Show TradingAgents signals."""
    console.print()
    table = Table(title="TradingAgents Signals", border_style="bright_blue")
    table.add_column("Asset", style="bold white")
    table.add_column("Direction", justify="center")
    table.add_column("Confidence", justify="right", style="yellow")
    table.add_column("Timeframe", justify="center", style="dim")
    table.add_column("Entry", justify="right", style="cyan")
    table.add_column("Target", justify="right", style="green")
    table.add_column("Stop", justify="right", style="red")

    for sig in MOCK_SIGNALS:
        direction_style = "bold green" if sig.direction == "LONG" else "bold red"
        table.add_row(
            sig.asset,
            Text(sig.direction, style=direction_style),
            f"{sig.confidence:.0%}",
            sig.timeframe,
            f"${sig.entry:,.1f}",
            f"${sig.target:,.1f}",
            f"${sig.stop:,.1f}",
        )

    console.print(table)
    console.print()


@cli.command()
def demo() -> None:
    """Run the theatrical demo mode."""
    run_demo()


@cli.command()
def status() -> None:
    """Show system health and configuration."""
    console.print()

    table = Table(title="System Status", border_style="bright_cyan")
    table.add_column("Component", style="bold white")
    table.add_column("Status", justify="center")
    table.add_column("Details", style="dim")

    components = [
        ("Polymarket API", "MOCK", "Using hardcoded data (8 markets)"),
        ("DeFi Yields (DeFiLlama)", "MOCK", "Using hardcoded data (8 pools)"),
        ("TradingAgents", "MOCK", "Using hardcoded signals (BTC, ETH, SOL)"),
        ("Scoring Engine", "READY", "Virality scorer v0.1"),
        ("Prompt Templates", "READY", f"{len(TEMPLATES)} templates loaded"),
        ("MoneyPrinterTurbo", "NOT CONNECTED", "Video generation offline"),
        ("Upload Pipeline", "NOT CONNECTED", "TikTok/YouTube/Shorts offline"),
    ]

    for name, stat, details in components:
        if stat == "READY":
            status_text = Text(stat, style="bold green")
        elif stat == "MOCK":
            status_text = Text(stat, style="bold yellow")
        else:
            status_text = Text(stat, style="bold red")
        table.add_row(name, status_text, details)

    console.print(table)
    console.print()


@cli.command(name="run")
@click.option("--interval", default=60, help="Seconds between pipeline cycles.")
@click.option("--max-cycles", default=0, help="Max cycles (0 = infinite).")
def run_pipeline(interval: int, max_cycles: int) -> None:
    """Start the full autonomous pipeline loop."""
    console.print()
    console.print(Panel(
        "[bold]Starting autonomous pipeline[/]\n"
        f"Interval: {interval}s | Max cycles: {'unlimited' if max_cycles == 0 else max_cycles}",
        border_style="bright_yellow",
    ))
    console.print()

    cycle = 0
    try:
        while max_cycles == 0 or cycle < max_cycles:
            cycle += 1
            console.rule(f"[bold cyan]Cycle {cycle}[/]")

            # Scan
            console.print("[dim]Scanning markets...[/]")
            ranked = _ranked_markets()
            top = ranked[0]
            console.print(f"  Top market: {top.question} (score={top.score:.1f})")

            # Generate
            template_name = _pick_template(top)
            console.print(f"  Generating {template_name} script...")
            console.print(f"  [bold green]Script ready[/] -- would render video in production")

            # Signals
            console.print(f"  Trading signals: {len(MOCK_SIGNALS)} active")

            # Yields
            best_yield = max(MOCK_DEFI, key=lambda p: p.apy)
            console.print(f"  Best yield: {best_yield.protocol} {best_yield.pair} @ {best_yield.apy:.1f}% APY")

            console.print(f"  [bold green]Cycle {cycle} complete[/]")
            console.print()

            if max_cycles == 0 or cycle < max_cycles:
                console.print(f"[dim]Next cycle in {interval}s (Ctrl+C to stop)[/]")
                time.sleep(interval)

    except KeyboardInterrupt:
        console.print()
        console.print(f"[bold yellow]Pipeline stopped after {cycle} cycles.[/]")
        console.print()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    cli()
