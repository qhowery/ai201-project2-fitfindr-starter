"""Milestone 5 — deliberate failure mode tests. Run with: pytest tests/test_failure_modes.py -v"""

from unittest.mock import patch

from agent import run_agent
from app import handle_query
from tools import EMPTY_OUTFIT_ERROR, create_fit_card, search_listings, suggest_outfit
from utils.data_loader import get_empty_wardrobe, get_example_wardrobe, load_listings


# ── Tool-level failure modes ──────────────────────────────────────────────────

def test_search_listings_returns_empty_list_not_exception():
    results = search_listings("designer ballgown", size="XXS", max_price=5)
    assert results == []
    assert isinstance(results, list)


def test_create_fit_card_empty_outfit_returns_error_string():
    item = search_listings("vintage graphic tee", max_price=50)[0]
    result = create_fit_card("", item)
    assert result == EMPTY_OUTFIT_ERROR
    assert "Cannot create a fit card" in result


@patch("tools._call_llm", return_value="Pair with wide-leg denim and chunky sneakers.")
def test_suggest_outfit_empty_wardrobe_returns_advice(mock_llm):
    item = search_listings("vintage graphic tee", max_price=50)[0]
    result = suggest_outfit(item, get_empty_wardrobe())
    assert isinstance(result, str)
    assert len(result.strip()) > 0
    prompt = mock_llm.call_args[0][0]
    assert "has not added their wardrobe" in prompt


# ── Agent-level failure modes ─────────────────────────────────────────────────

def test_agent_no_results_actionable_message():
    session = run_agent(
        query="designer ballgown size XXS under $5",
        wardrobe=get_example_wardrobe(),
    )
    assert session["error"] is not None
    assert session["fit_card"] is None
    assert session["outfit_suggestion"] is None
    assert "designer ballgown" in session["error"]
    assert "Try broadening your search" in session["error"]
    assert "drop the size filter" in session["error"]


@patch("agent.create_fit_card", return_value="caption")
@patch("agent.suggest_outfit", return_value="General styling advice for the tee.")
def test_agent_empty_wardrobe_completes_with_note(mock_suggest, mock_fit_card):
    session = run_agent(
        query="vintage graphic tee under $30",
        wardrobe=get_empty_wardrobe(),
    )
    assert session["error"] is None
    assert session["wardrobe_note"] is not None
    assert "general styling advice" in session["wardrobe_note"].lower()
    assert session["fit_card"] == "caption"
    mock_suggest.assert_called_once()
    mock_fit_card.assert_called_once()


@patch("agent.create_fit_card", return_value=EMPTY_OUTFIT_ERROR)
@patch("agent.suggest_outfit", return_value="Pair with baggy jeans.")
def test_agent_create_fit_card_empty_outfit_error(mock_suggest, mock_fit_card):
    session = run_agent(
        query="vintage graphic tee under $30",
        wardrobe=get_example_wardrobe(),
    )
    assert session["error"] is not None
    assert "Couldn't generate your fit card" in session["error"]
    assert "Pair with baggy jeans" in session["error"]
    assert session["fit_card"] is None


def test_handle_query_surfaces_no_results_error():
    listing, outfit, fit_card = handle_query(
        "designer ballgown size XXS under $5",
        "Example wardrobe",
    )
    assert "Try broadening your search" in listing
    assert outfit == ""
    assert fit_card == ""


@patch("agent.create_fit_card", return_value="my caption")
@patch("agent.suggest_outfit", return_value="General advice here.")
def test_handle_query_empty_wardrobe_shows_note(mock_suggest, mock_fit_card):
    listing, outfit, fit_card = handle_query(
        "vintage graphic tee under $30",
        "Empty wardrobe (new user)",
    )
    assert "Graphic Tee" in listing
    assert "general styling advice" in outfit.lower()
    assert "General advice here" in outfit
    assert fit_card == "my caption"
