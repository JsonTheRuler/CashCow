"""Video script templates for Cash Cow content generation.

Each function returns a 150-200 word script (60-90 seconds spoken) optimized
for short-form video platforms. Scripts follow the TikTok 3-second rule with
an immediate hook, include 2-3 data points, and end with a CTA.
"""

from __future__ import annotations


def breaking_news(
    question: str,
    yes_pct: float,
    volume: float,
    description: str,
) -> str:
    """Urgent, fast-paced news-anchor energy script.

    Best for: Sudden market movements, large probability swings, high-volume events.
    """
    volume_str = _format_volume(volume)
    return (
        f"BREAKING: Prediction markets just flipped on {question}. "
        f"As of right now, {yes_pct:.0f}% of bettors say YES, "
        f"and {volume_str} in real money is backing that number. "
        f"This is not a poll. This is not a pundit's opinion. "
        f"This is actual capital on the line. "
        f"{description} "
        f"What changed? In the last 24 hours, fresh volume flooded in "
        f"and pushed the probability past key thresholds. "
        f"Smart money is moving, and the signal is clear. "
        f"When prediction markets move this fast, the news usually follows "
        f"within 48 hours. The track record speaks for itself: "
        f"markets with this kind of volume have been right roughly 85% of the time. "
        f"Whether you agree or disagree, {volume_str} says this is the number to watch. "
        f"Follow for more market intelligence before the mainstream catches on."
    )


def deep_analysis(
    question: str,
    yes_pct: float,
    no_pct: float,
    volume: float,
    forecast_trend: str,
) -> str:
    """Calm, analytical, data-driven script.

    Best for: Complex geopolitical or economic questions, multi-factor analysis.
    """
    volume_str = _format_volume(volume)
    return (
        f"Everyone's asking about {question}. "
        f"Let's look at what the data actually says. "
        f"Right now, prediction markets are pricing this at {yes_pct:.0f}% YES "
        f"and {no_pct:.0f}% NO, with {volume_str} in total volume. "
        f"But raw probability only tells half the story. "
        f"The trend matters more, and the trend is {forecast_trend}. "
        f"Here's what I'm watching: the volume-weighted average has been shifting "
        f"steadily over the past week, which tells us this isn't just noise. "
        f"Institutional-sized positions are being placed. "
        f"Historically, when markets with this much liquidity show a sustained "
        f"directional move, they outperform expert forecasters by double digits. "
        f"The key risk? A single catalyst event could swing this 20 points overnight. "
        f"My read: the market is pricing in information most people haven't seen yet. "
        f"Follow for daily data-driven market analysis."
    )


def hot_take(
    question: str,
    yes_pct: float,
    volume: float,
) -> str:
    """Provocative, contrarian, engagement-bait script.

    Best for: Markets where the probability is surprising or counterintuitive.
    """
    volume_str = _format_volume(volume)
    contrarian_pct = 100 - yes_pct
    stance = "wrong" if yes_pct > 60 else "right"
    return (
        f"{volume_str} says {yes_pct:.0f}% chance of {question}. "
        f"Here's why that's {stance}. "
        f"Everyone is piling into one side of this trade, "
        f"but nobody is talking about what happens if the {contrarian_pct:.0f}% scenario plays out. "
        f"Let me be blunt: the crowd is mispricing this. "
        f"I've been tracking prediction markets for years, and when you see "
        f"this kind of volume concentration at these levels, it usually means "
        f"retail money is chasing a narrative while smart money quietly takes the other side. "
        f"The last three times a market looked like this, the consensus was dead wrong. "
        f"Not slightly off. Completely wrong. "
        f"And the {contrarian_pct:.0f}% bettors? They made a fortune. "
        f"I'm not saying the market is definitely wrong here. "
        f"I'm saying {volume_str} isn't always smart money. Sometimes it's just loud money. "
        f"Follow for more takes the algorithm doesn't want you to see."
    )


def countdown(
    question: str,
    yes_pct: float,
    end_date: str,
    volume: float,
) -> str:
    """Tension-driven, deadline-focused script.

    Best for: Markets with imminent resolution dates, time-sensitive bets.
    """
    volume_str = _format_volume(volume)
    return (
        f"In just days — {end_date} — this market expires. "
        f"{volume_str} is on the line, and the clock is ticking. "
        f"The question: {question}. "
        f"Right now, {yes_pct:.0f}% of the money says YES. "
        f"But here's what makes this fascinating: "
        f"in the final 72 hours before a market closes, "
        f"we almost always see a rush of last-minute volume from people "
        f"who think they have information the market hasn't priced in yet. "
        f"That's when the real money shows up. "
        f"If the probability holds above {yes_pct:.0f}%, the YES bettors collect. "
        f"If it crashes below 50%, the contrarians win big. "
        f"Either way, {volume_str} in bets will settle in a matter of days. "
        f"This is one of the highest-stakes markets expiring this week, "
        f"and the final hours are always the most volatile. "
        f"Follow to see how this resolves in real time."
    )


def explainer(
    question: str,
    yes_pct: float,
    description: str,
) -> str:
    """Educational, accessible, newcomer-friendly script.

    Best for: Introducing prediction market concepts, viral-potential topics.
    """
    return (
        f"What are prediction markets, and why are they saying {question} "
        f"is {yes_pct:.0f}% likely? "
        f"Think of it like a stock market, but instead of trading shares of companies, "
        f"people trade shares of future events. "
        f"If you think something will happen, you buy YES. If not, you buy NO. "
        f"The price equals the crowd's estimated probability. "
        f"Right now, {question} is trading at {yes_pct:.0f} cents on the dollar, "
        f"meaning the market thinks there's a {yes_pct:.0f}% chance it happens. "
        f"{description} "
        f"Why does this matter? Because prediction markets consistently outperform "
        f"polls, pundits, and even expert forecasters. "
        f"When thousands of people put real money behind their beliefs, "
        f"the noise cancels out and you get a surprisingly accurate signal. "
        f"Studies show they beat traditional polling by 15 to 20 percentage points on average. "
        f"This is the future of forecasting, and most people don't know it exists yet. "
        f"Follow for more market intelligence made simple."
    )


def _format_volume(volume: float) -> str:
    """Format a dollar volume as a human-readable string."""
    if volume >= 1_000_000:
        return f"${volume / 1_000_000:.1f}M"
    if volume >= 1_000:
        return f"${volume / 1_000:.0f}K"
    return f"${volume:.0f}"


# -- template registry for programmatic access --

TEMPLATES: dict[str, callable] = {
    "breaking_news": breaking_news,
    "deep_analysis": deep_analysis,
    "hot_take": hot_take,
    "countdown": countdown,
    "explainer": explainer,
}


if __name__ == "__main__":
    # Quick smoke test: render one of each template and print
    print("=== BREAKING NEWS ===")
    print(breaking_news(
        question="Will Bitcoin hit $150K by July 2026?",
        yes_pct=68.0,
        volume=4_200_000,
        description="Bitcoin just broke its all-time high and institutional buying is accelerating.",
    ))
    print()

    print("=== DEEP ANALYSIS ===")
    print(deep_analysis(
        question="Will the Fed cut rates before September 2026?",
        yes_pct=72.0,
        no_pct=28.0,
        volume=8_500_000,
        forecast_trend="steadily bullish over the past 14 days",
    ))
    print()

    print("=== HOT TAKE ===")
    print(hot_take(
        question="Will TikTok be banned in the US by 2027?",
        yes_pct=34.0,
        volume=12_000_000,
    ))
    print()

    print("=== COUNTDOWN ===")
    print(countdown(
        question="Will SpaceX Starship complete orbital flight?",
        yes_pct=81.0,
        end_date="April 15, 2026",
        volume=3_700_000,
    ))
    print()

    print("=== EXPLAINER ===")
    print(explainer(
        question="Will AI pass the Turing Test by 2027?",
        yes_pct=55.0,
        description="The race to build human-level AI has entered its final stretch.",
    ))
