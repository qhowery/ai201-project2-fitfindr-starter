"""Tests for the FitFindr planning loop — run with: pytest tests/"""

from unittest.mock import patch

from agent import _parse_query, run_agent
from utils.data_loader import get_empty_wardrobe, get_example_wardrobe


def test_parse_query_extracts_fields():
    parsed = _parse_query("looking for a vintage graphic tee under $30, size M")
    assert parsed["description"] == "vintage graphic tee"
    assert parsed["max_price"] == 30.0
    assert parsed["size"] == "M"


def test_parse_query_empty_description():
    parsed = _parse_query("under $30")
    assert parsed["description"] == ""


@patch("agent.create_fit_card")
@patch("agent.suggest_outfit")
def test_no_results_skips_later_tools(mock_suggest, mock_fit_card):
    session = run_agent(
        query="designer ballgown size XXS under $5",
        wardrobe=get_example_wardrobe(),
    )
    assert session["error"] is not None
    assert session["fit_card"] is None
    assert session["outfit_suggestion"] is None
    assert session["search_results"] == []
    mock_suggest.assert_not_called()
    mock_fit_card.assert_not_called()


@patch("agent.create_fit_card", return_value="caption text")
@patch("agent.suggest_outfit", return_value="Pair with baggy jeans.")
def test_happy_path_state_flow(mock_suggest, mock_fit_card):
    session = run_agent(
        query="vintage graphic tee under $30",
        wardrobe=get_example_wardrobe(),
    )
    assert session["error"] is None
    assert session["selected_item"]["id"] == "lst_006"
    assert len(session["search_results"]) > 0

    mock_suggest.assert_called_once_with(
        new_item=session["selected_item"],
        wardrobe=session["wardrobe"],
    )
    mock_fit_card.assert_called_once_with(
        outfit="Pair with baggy jeans.",
        new_item=session["selected_item"],
    )
    assert session["outfit_suggestion"] == "Pair with baggy jeans."
    assert session["fit_card"] == "caption text"


@patch("agent.create_fit_card", return_value="caption")
@patch("agent.suggest_outfit", return_value="General styling advice.")
def test_empty_wardrobe_sets_note(mock_suggest, mock_fit_card):
    session = run_agent(
        query="vintage graphic tee under $30",
        wardrobe=get_empty_wardrobe(),
    )
    assert session["error"] is None
    assert session["wardrobe_note"] is not None
    mock_suggest.assert_called_once()
    mock_fit_card.assert_called_once()
