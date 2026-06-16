"""
agent.py

The FitFindr planning loop. Orchestrates the three tools in response to a
natural language user query, passing state between them via a session dict.

Complete tools.py and test each tool in isolation before implementing this file.

Usage (once implemented):
    from agent import run_agent
    from utils.data_loader import get_example_wardrobe

    result = run_agent(
        query="vintage graphic tee under $30, size M",
        wardrobe=get_example_wardrobe(),
    )
    print(result["fit_card"])
    print(result["error"])   # None on success
"""

import re

from tools import EMPTY_OUTFIT_ERROR, create_fit_card, search_listings, suggest_outfit

_FILLER_PATTERNS = [
    r"\bi(?:'m| am) looking for\b",
    r"\blooking for\b",
    r"\bi want\b",
    r"\bwhat(?:'s| is) out there\b",
    r"\bhow would i style it\b",
]


def _parse_query(query: str) -> dict:
    """Extract description, size, and max_price from a natural language query."""
    text = query.strip()
    max_price = None
    size = None

    price_match = re.search(
        r"under\s+\$?\s*(\d+(?:\.\d{1,2})?)", text, re.IGNORECASE
    )
    if not price_match:
        price_match = re.search(
            r"under\s+(\d+(?:\.\d{1,2})?)\s+dollars?", text, re.IGNORECASE
        )
    if price_match:
        max_price = float(price_match.group(1))

    size_match = re.search(
        r"(?:in\s+)?size\s+([\w/]+)", text, re.IGNORECASE
    )
    if size_match:
        size = size_match.group(1)

    description = text
    description = re.sub(
        r"under\s+\$?\s*\d+(?:\.\d{1,2})?", "", description, flags=re.IGNORECASE
    )
    description = re.sub(
        r"under\s+\d+(?:\.\d{1,2})?\s+dollars?", "", description, flags=re.IGNORECASE
    )
    description = re.sub(
        r"(?:in\s+)?size\s+[\w/]+", "", description, flags=re.IGNORECASE
    )
    for pattern in _FILLER_PATTERNS:
        description = re.sub(pattern, "", description, flags=re.IGNORECASE)
    description = re.sub(r"\s+", " ", description).strip(" .,!?-")

    # Keep the item search phrase before wardrobe/style context sentences.
    if "." in description:
        description = description.split(".")[0].strip(" .,!?-")

    description = re.sub(r"^(?:a|an|the)\s+", "", description, flags=re.IGNORECASE)

    return {"description": description, "size": size, "max_price": max_price}


# ── session state ─────────────────────────────────────────────────────────────

def _new_session(query: str, wardrobe: dict) -> dict:
    """
    Initialize and return a fresh session dict for one user interaction.

    The session dict is the single source of truth for everything that happens
    during a run — it stores the original query, parsed parameters, tool results,
    and any error that caused early termination.

    You may add fields to this dict as needed for your implementation.
    """
    return {
        "query": query,              # original user query
        "parsed": {},                # extracted description / size / max_price
        "search_results": [],        # list of matching listing dicts
        "selected_item": None,       # top result, passed into suggest_outfit
        "wardrobe": wardrobe,        # user's wardrobe dict
        "outfit_suggestion": None,   # string returned by suggest_outfit
        "fit_card": None,            # string returned by create_fit_card
        "wardrobe_note": None,       # set when wardrobe is empty
        "error": None,               # set if the interaction ended early
    }


# ── planning loop ─────────────────────────────────────────────────────────────

def run_agent(query: str, wardrobe: dict) -> dict:
    """
    Main agent entry point. Runs the FitFindr planning loop for a single
    user interaction and returns the completed session dict.

    Args:
        query:    Natural language user request
                  (e.g., "vintage graphic tee under $30, size M")
        wardrobe: User's wardrobe dict — use get_example_wardrobe() or
                  get_empty_wardrobe() from utils/data_loader.py

    Returns:
        The session dict after the interaction completes. Check session["error"]
        first — if it is not None, the interaction ended early and the other
        output fields (outfit_suggestion, fit_card) will be None.
    """
    session = _new_session(query, wardrobe)

    # Step 1 — Parse query
    session["parsed"] = _parse_query(query)
    description = session["parsed"]["description"]
    if not description:
        session["error"] = (
            "Tell me what you're looking for — e.g., 'vintage graphic tee under $30'."
        )
        return session

    # Step 2 — search_listings
    session["search_results"] = search_listings(
        description=description,
        size=session["parsed"]["size"],
        max_price=session["parsed"]["max_price"],
    )
    if not session["search_results"]:
        price_clause = (
            f" under ${session['parsed']['max_price']:.0f}"
            if session["parsed"]["max_price"] is not None
            else ""
        )
        session["error"] = (
            f"I couldn't find any listings matching '{description}'{price_clause}. "
            "Try broadening your search — drop the size filter, increase your budget, "
            "or search for a different style."
        )
        return session

    session["selected_item"] = session["search_results"][0]

    # Step 3 — suggest_outfit
    try:
        session["outfit_suggestion"] = suggest_outfit(
            new_item=session["selected_item"],
            wardrobe=session["wardrobe"],
        )
    except Exception:
        item = session["selected_item"]
        session["outfit_suggestion"] = None
        session["error"] = (
            f"I found **{item['title']}** (${item['price']} on {item['platform']}), "
            "but couldn't generate outfit suggestions right now. Please try again."
        )
        return session

    if not session["outfit_suggestion"] or not session["outfit_suggestion"].strip():
        item = session["selected_item"]
        session["outfit_suggestion"] = None
        session["error"] = (
            f"I found **{item['title']}** (${item['price']} on {item['platform']}), "
            "but couldn't generate outfit suggestions right now. Please try again."
        )
        return session

    if not session["wardrobe"].get("items"):
        session["wardrobe_note"] = (
            "I don't have your wardrobe yet, so this is general styling advice."
        )

    # Step 4 — create_fit_card
    if not session["outfit_suggestion"].strip():
        session["error"] = "Outfit suggestion was missing — can't create a fit card."
        return session

    try:
        fit_card = create_fit_card(
            outfit=session["outfit_suggestion"],
            new_item=session["selected_item"],
        )
    except Exception:
        session["error"] = (
            f"I couldn't generate a fit card right now, but here's your outfit idea: "
            f"{session['outfit_suggestion']}"
        )
        return session

    if not fit_card or not fit_card.strip():
        session["error"] = (
            f"I couldn't generate a fit card right now, but here's your outfit idea: "
            f"{session['outfit_suggestion']}"
        )
        return session

    if fit_card.startswith("Cannot create a fit card"):
        session["error"] = (
            f"Couldn't generate your fit card, but here's how to style it: "
            f"{session['outfit_suggestion']}"
        )
        return session

    session["fit_card"] = fit_card
    return session


# ── CLI test ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    from utils.data_loader import get_example_wardrobe

    print("=== Happy path: graphic tee ===\n")
    session = run_agent(
        query="looking for a vintage graphic tee under $30",
        wardrobe=get_example_wardrobe(),
    )
    if session["error"]:
        print(f"Error: {session['error']}")
    else:
        print(f"Found: {session['selected_item']['title']}")
        print(f"selected_item id: {session['selected_item']['id']}")
        print(f"\nOutfit: {session['outfit_suggestion']}")
        print(f"\nFit card: {session['fit_card']}")

    print("\n\n=== No-results path ===\n")
    session2 = run_agent(
        query="designer ballgown size XXS under $5",
        wardrobe=get_example_wardrobe(),
    )
    print(f"Error message: {session2['error']}")
    print(f"fit_card is None: {session2['fit_card'] is None}")
    print(f"outfit_suggestion is None: {session2['outfit_suggestion'] is None}")
