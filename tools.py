"""
tools.py

The three required FitFindr tools. Each tool is a standalone function that
can be called and tested independently before being wired into the agent loop.

Complete and test each tool before moving to agent.py.

Tools:
    search_listings(description, size, max_price)  → list[dict]
    suggest_outfit(new_item, wardrobe)              → str
    create_fit_card(outfit, new_item)               → str
"""

import os
import re

from dotenv import load_dotenv
from groq import Groq

from utils.data_loader import load_listings

load_dotenv()

LLM_MODEL = "llama-3.3-70b-versatile"
FIT_CARD_TEMPERATURE = 0.9
OUTFIT_TEMPERATURE = 0.7

EMPTY_OUTFIT_ERROR = (
    "Cannot create a fit card — outfit suggestion is missing. Run suggest_outfit first."
)


# ── Groq client ───────────────────────────────────────────────────────────────

def _get_groq_client():
    """Initialize and return a Groq client using GROQ_API_KEY from .env."""
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise ValueError(
            "GROQ_API_KEY not set. Add it to a .env file in the project root."
        )
    return Groq(api_key=api_key)


def _call_llm(prompt: str, temperature: float = OUTFIT_TEMPERATURE) -> str:
    """Send a prompt to Groq and return the assistant's text response."""
    client = _get_groq_client()
    response = client.chat.completions.create(
        model=LLM_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=temperature,
    )
    return response.choices[0].message.content.strip()


def _tokenize(text: str) -> list[str]:
    """Split text into lowercase keyword tokens, ignoring very short words."""
    return [word for word in re.findall(r"[a-z0-9]+", text.lower()) if len(word) > 1]


def _score_listing(listing: dict, keywords: list[str]) -> int:
    """Score a listing by keyword matches, weighting title and style tags highest."""
    title = listing.get("title", "").lower()
    description = listing.get("description", "").lower()
    category = listing.get("category", "").lower()
    tags = [tag.lower() for tag in listing.get("style_tags", [])]

    score = 0
    for keyword in keywords:
        if keyword in title:
            score += 3
        elif any(keyword in tag for tag in tags):
            score += 2
        elif keyword in description:
            score += 1
        elif keyword in category:
            score += 1

    phrase = " ".join(keywords)
    if phrase in title:
        score += 4
    for tag in tags:
        if phrase == tag or (len(keywords) > 1 and all(kw in tag for kw in keywords)):
            score += 3

    return score


# ── Tool 1: search_listings ───────────────────────────────────────────────────

def search_listings(
    description: str,
    size: str | None = None,
    max_price: float | None = None,
) -> list[dict]:
    """
    Search the mock listings dataset for items matching the description,
    optional size, and optional price ceiling.

    Args:
        description: Keywords describing what the user is looking for
                     (e.g., "vintage graphic tee").
        size:        Size string to filter by, or None to skip size filtering.
                     Matching is case-insensitive (e.g., "M" matches "S/M").
        max_price:   Maximum price (inclusive), or None to skip price filtering.

    Returns:
        A list of matching listing dicts, sorted by relevance (best match first).
        Returns an empty list if nothing matches — does NOT raise an exception.

    Each listing dict has the following fields:
        id, title, description, category, style_tags (list), size,
        condition, price (float), colors (list), brand, platform
    """
    listings = load_listings()
    keywords = _tokenize(description)

    filtered: list[tuple[int, dict]] = []
    for listing in listings:
        if max_price is not None and listing["price"] > max_price:
            continue
        if size is not None and size.lower() not in listing["size"].lower():
            continue

        score = _score_listing(listing, keywords) if keywords else 1
        if score > 0:
            filtered.append((score, listing))

    filtered.sort(
        key=lambda pair: (
            pair[0],
            sum(1 for kw in keywords if kw in pair[1]["title"].lower()),
        ),
        reverse=True,
    )
    return [listing for _, listing in filtered]


# ── Tool 2: suggest_outfit ────────────────────────────────────────────────────

def suggest_outfit(new_item: dict, wardrobe: dict) -> str:
    """
    Given a thrifted item and the user's wardrobe, suggest 1–2 complete outfits.

    Args:
        new_item: A listing dict (the item the user is considering buying).
        wardrobe: A wardrobe dict with an 'items' key containing a list of
                  wardrobe item dicts. May be empty — handle this gracefully.

    Returns:
        A non-empty string with outfit suggestions.
        If the wardrobe is empty, offer general styling advice for the item
        rather than raising an exception or returning an empty string.
    """
    items = wardrobe.get("items", [])
    title = new_item.get("title", "this item")
    category = new_item.get("category", "clothing")
    style_tags = ", ".join(new_item.get("style_tags", []))
    colors = ", ".join(new_item.get("colors", []))

    if not items:
        prompt = f"""You are a personal stylist. A user found this secondhand item but has not added their wardrobe yet.

Item: {title}
Category: {category}
Colors: {colors}
Style tags: {style_tags}

Suggest 1–2 general outfit ideas for this item. Describe what types of pieces pair well (bottoms, shoes, layers) and the overall vibe. Write 3–8 sentences in plain English. Do not invent specific wardrobe pieces the user owns."""
    else:
        wardrobe_lines = []
        for item in items:
            notes = item.get("notes") or ""
            note_text = f" ({notes})" if notes else ""
            tags = ", ".join(item.get("style_tags", []))
            wardrobe_lines.append(
                f"- {item['name']} [{item['category']}, colors: {', '.join(item.get('colors', []))}, tags: {tags}]{note_text}"
            )
        wardrobe_text = "\n".join(wardrobe_lines)

        prompt = f"""You are a personal stylist. Suggest 1–2 complete outfits using the new thrift find AND specific pieces from the user's wardrobe.

New item: {title}
Category: {category}
Colors: {colors}
Style tags: {style_tags}

User's wardrobe:
{wardrobe_text}

Write 3–8 sentences. Name wardrobe pieces by their exact names from the list above. Explain why the combinations work (color, silhouette, vibe)."""

    result = _call_llm(prompt, temperature=OUTFIT_TEMPERATURE)
    if not result:
        return (
            f"Style {title} with pieces that match its {style_tags} vibe — "
            f"try wide-leg bottoms and sneakers for an easy everyday look."
        )
    return result


# ── Tool 3: create_fit_card ───────────────────────────────────────────────────

def create_fit_card(outfit: str, new_item: dict) -> str:
    """
    Generate a short, shareable outfit caption for the thrifted find.

    Args:
        outfit:   The outfit suggestion string from suggest_outfit().
        new_item: The listing dict for the thrifted item.

    Returns:
        A 2–4 sentence string usable as an Instagram/TikTok caption.
        If outfit is empty or missing, return a descriptive error message
        string — do NOT raise an exception.
    """
    if not outfit or not outfit.strip():
        return EMPTY_OUTFIT_ERROR

    title = new_item.get("title", "this find")
    price = new_item.get("price", 0)
    platform = new_item.get("platform", "depop")

    prompt = f"""Write a casual Instagram/TikTok outfit caption (2–4 sentences) for this thrift find.

Item: {title}
Price: ${price:.2f}
Platform: {platform}
Outfit styling: {outfit}

Guidelines:
- Sound like a real OOTD post, not a product listing
- Mention the item name, price, and platform once each, naturally
- Capture the outfit vibe in specific terms
- Keep it authentic and casual; emojis are okay but don't overdo it"""

    return _call_llm(prompt, temperature=FIT_CARD_TEMPERATURE)
