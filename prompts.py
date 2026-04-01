"""Prompt templates for Cash Cow short-form video generation."""

from __future__ import annotations

from typing import Callable, Dict


TemplateFn = Callable[[str, float, float, float, str], str]


def _clamp_pct(value: float) -> float:
    """Clamp a percentage to the 0-100 range."""
    return max(0.0, min(100.0, float(value)))


def _format_pct(value: float) -> str:
    """Format a percentage for spoken output."""
    clamped = _clamp_pct(value)
    if clamped.is_integer():
        return f"{int(clamped)}"
    return f"{clamped:.1f}"


def _format_volume(volume_24h: float) -> str:
    """Format market volume in a social-video-friendly way."""
    volume = max(0.0, float(volume_24h))
    if volume >= 1_000_000_000:
        return f"${volume / 1_000_000_000:.2f}B"
    if volume >= 1_000_000:
        return f"${volume / 1_000_000:.2f}M"
    if volume >= 1_000:
        return f"${volume / 1_000:.1f}K"
    return f"${volume:.0f}"


def _clean_description(description: str) -> str:
    """Compact a market description into a spoken-script-ready snippet."""
    cleaned = " ".join(description.split()).strip()
    return cleaned[:260].rstrip(" ,.;:") + ("..." if len(cleaned) > 260 else "")


def breaking_news_prompt(
    question: str,
    yes_pct: float,
    no_pct: float,
    volume_24h: float,
    description: str,
) -> str:
    """Return a breaking-news style prompt for MoneyPrinterTurbo."""
    return (
        f"BREAKING: prediction markets just snapped to attention on {question}. "
        f"Right now the market is pricing {_format_pct(yes_pct)}% YES versus {_format_pct(no_pct)}% NO, "
        f"with {_format_volume(volume_24h)} traded in the last 24 hours alone. "
        f"That kind of money flow usually means something changed fast, and the crowd is racing to reprice reality in real time. "
        f"Here is the setup: {_clean_description(description)}. "
        f"In this short, unpack what may have triggered the move, why traders are leaning the way they are, and what would need to happen next for the odds to swing even harder. "
        f"Keep the pacing urgent, sharp, and easy to follow. "
        f"End by asking whether viewers think the market is early, late, or completely wrong."
    )


def deep_analysis_prompt(
    question: str,
    yes_pct: float,
    no_pct: float,
    volume_24h: float,
    description: str,
) -> str:
    """Return a deeper analytical prompt for MoneyPrinterTurbo."""
    return (
        f"Stop scrolling: this market might be telling us more than the headlines are. "
        f"The question is {question}, and traders have it at {_format_pct(yes_pct)}% YES and {_format_pct(no_pct)}% NO, "
        f"backed by {_format_volume(volume_24h)} in 24-hour volume. "
        f"Use this video to break down the market like an analyst, not a hype machine. "
        f"Start with the core thesis behind the current pricing, then walk through the strongest bull case, the strongest bear case, and the hidden assumption most people are missing. "
        f"Use this context from the market description: {_clean_description(description)}. "
        f"Explain why liquidity and probabilities matter, show what a near-even or lopsided market implies about confidence, and finish with a balanced take on whether the current odds look efficient or vulnerable to a sharp repricing."
    )


def hot_take_prompt(
    question: str,
    yes_pct: float,
    no_pct: float,
    volume_24h: float,
    description: str,
) -> str:
    """Return a contrarian hot-take style prompt for MoneyPrinterTurbo."""
    return (
        f"Hot take: the crowd might be getting {question} completely wrong. "
        f"Prediction traders are sitting at {_format_pct(yes_pct)}% YES and {_format_pct(no_pct)}% NO after {_format_volume(volume_24h)} in recent trading, "
        f"and that is exactly why this setup is worth talking about. "
        f"Open with a bold opinion, then back it up fast with logic. "
        f"Use the market brief here: {_clean_description(description)}. "
        f"Build a punchy 60 to 90 second script that explains what everyone seems to believe, why that consensus may be fragile, and what surprise catalyst could embarrass the majority. "
        f"Keep the tone confident, witty, and debate-friendly without sounding reckless. "
        f"Finish by challenging the audience to choose whether they trust the smart money, fade the herd, or stay out entirely."
    )


def explainer_prompt(
    question: str,
    yes_pct: float,
    no_pct: float,
    volume_24h: float,
    description: str,
) -> str:
    """Return an educational explainer prompt for MoneyPrinterTurbo."""
    return (
        f"Confused by this market? Here is the simple version. "
        f"The question is {question}, and traders currently price it at {_format_pct(yes_pct)}% YES versus {_format_pct(no_pct)}% NO, "
        f"with {_format_volume(volume_24h)} traded over the last 24 hours. "
        f"Write a clear explainer that teaches viewers how to interpret those odds, what event the market is actually tracking, and why people are willing to trade on it. "
        f"Use the description as source context: {_clean_description(description)}. "
        f"Define the stakes in plain English, explain what could push the probability higher or lower, and translate market jargon into everyday language. "
        f"Keep the script approachable for someone new to prediction markets while still sounding smart enough for finance and crypto audiences. "
        f"Wrap with one memorable takeaway about what this market says about public expectations right now."
    )


def countdown_prompt(
    question: str,
    yes_pct: float,
    no_pct: float,
    volume_24h: float,
    description: str,
) -> str:
    """Return a countdown-style prompt for MoneyPrinterTurbo."""
    return (
        f"Three reasons this market could explode next: {question}. "
        f"Odds are sitting at {_format_pct(yes_pct)}% YES and {_format_pct(no_pct)}% NO, with {_format_volume(volume_24h)} in 24-hour volume. "
        f"Structure this as a fast countdown for Shorts or TikTok. "
        f"Start with the most surprising hook, then count down the top three forces driving this market right now. "
        f"Use the market description for detail: {_clean_description(description)}. "
        f"Each countdown point should add a fresh angle, such as sentiment, timeline pressure, incentives, or a catalyst traders are watching. "
        f"Keep the language punchy, visual, and easy to voice over. "
        f"End with a final line that makes viewers want to comment their own probability before the market settles."
    )


PROMPT_BUILDERS: Dict[str, TemplateFn] = {
    "breaking_news": breaking_news_prompt,
    "deep_analysis": deep_analysis_prompt,
    "hot_take": hot_take_prompt,
    "explainer": explainer_prompt,
    "countdown": countdown_prompt,
}


def build_video_subject(
    vibe: str,
    question: str,
    yes_pct: float,
    no_pct: float,
    volume_24h: float,
    description: str,
) -> str:
    """Build a MoneyPrinterTurbo ``video_subject`` string for a given vibe."""
    normalized_vibe = vibe.strip().lower().replace(" ", "_")
    try:
        builder = PROMPT_BUILDERS[normalized_vibe]
    except KeyError as exc:
        supported = ", ".join(sorted(PROMPT_BUILDERS))
        raise ValueError(f"Unsupported vibe '{vibe}'. Supported vibes: {supported}.") from exc
    return builder(question, yes_pct, no_pct, volume_24h, description)


if __name__ == "__main__":
    sample_question = "Will Bitcoin reach $200k by the end of the year?"
    sample_description = (
        "A live prediction market tracking whether Bitcoin will trade at or above "
        "$200,000 before year-end, driven by ETF flows, macro policy, and speculative momentum."
    )
    for vibe_name in PROMPT_BUILDERS:
        print(f"\n[{vibe_name}]")
        print(build_video_subject(vibe_name, sample_question, 58.4, 41.6, 3_250_000, sample_description))
