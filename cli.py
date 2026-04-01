#!/usr/bin/env python3
"""Cash Cow hackathon CLI — demo instructions and quick market scan."""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

ROOT = Path(__file__).resolve().parent
app = typer.Typer(no_args_is_help=True, add_completion=False)
console = Console()


@app.command()
def demo(
    serve: bool = typer.Option(
        False,
        "--serve",
        "-s",
        help="Start API (8090) and Streamlit (8502) in background processes (Windows-friendly).",
    ),
) -> None:
    """Print demo quick start; optionally spawn API + dashboard."""
    console.print(
        "\n[bold cyan]Cash Cow — demo[/bold cyan]\n"
        "1. API: [green]python api.py[/green]  → http://127.0.0.1:8090/docs\n"
        "2. UI:  [green]streamlit run dashboard.py --server.port 8502[/green]\n"
        "3. (Optional) MoneyPrinterTurbo on :8080 for video generation\n"
    )
    if not serve:
        return
    api_proc = subprocess.Popen(
        [sys.executable, str(ROOT / "api.py")],
        cwd=str(ROOT),
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0,
    )
    time.sleep(2)
    dash_proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "streamlit",
            "run",
            str(ROOT / "dashboard.py"),
            "--server.port",
            "8502",
        ],
        cwd=str(ROOT),
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0,
    )
    console.print(
        f"[green]Started[/green] api.py (pid {api_proc.pid}), streamlit (pid {dash_proc.pid}). "
        "Stop them from Task Manager or close terminals."
    )


@app.command()
def scan() -> None:
    """Scan Polymarket (scored) and top DeFi stable yields (no API server required)."""
    sys.path.insert(0, str(ROOT))
    import defi_pipeline
    import scorer

    markets = scorer.top_markets(8)
    t = Table(title="Top Polymarket (Cash Cow score)")
    t.add_column("Rank", justify="right")
    t.add_column("Score", justify="right")
    t.add_column("YES%", justify="right")
    t.add_column("Question", max_width=56)
    for m in markets:
        t.add_row(
            str(m.get("rank", "")),
            f"{float(m.get('cash_cow_score') or 0):.0f}",
            f"{float(m.get('yes_pct') or 0):.1f}",
            str(m.get("question", ""))[:56],
        )
    console.print(t)

    y = defi_pipeline.get_top_yield_pools()
    t2 = Table(title="Top stablecoin yields (DeFi Llama)")
    t2.add_column("Chain")
    t2.add_column("Project")
    t2.add_column("Symbol")
    t2.add_column("APY %", justify="right")
    t2.add_column("TVL $", justify="right")
    for p in y[:10]:
        t2.add_row(
            str(p.get("chain", "")),
            str(p.get("project", "")),
            str(p.get("symbol", "")),
            f"{float(p.get('apy') or 0):.2f}",
            f"{float(p.get('tvlUsd') or 0):,.0f}",
        )
    console.print(t2)


if __name__ == "__main__":
    app()
