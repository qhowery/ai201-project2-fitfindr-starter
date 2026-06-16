"""Tests for FitFindr tools — run with: pytest tests/"""

from unittest.mock import patch

import pytest

from tools import (
    EMPTY_OUTFIT_ERROR,
    create_fit_card,
    search_listings,
    suggest_outfit,
)
from utils.data_loader import get_empty_wardrobe, get_example_wardrobe, load_listings


# ── search_listings ───────────────────────────────────────────────────────────

def test_search_returns_results():
    results = search_listings("vintage graphic tee", size=None, max_price=50)
    assert isinstance(results, list)
    assert len(results) > 0
    assert "id" in results[0]
    assert "title" in results[0]
    assert "price" in results[0]


def test_search_empty_results():
    results = search_listings("designer ballgown", size="XXS", max_price=5)
    assert results == []


def test_search_price_filter():
    results = search_listings("jacket", size=None, max_price=10)
    assert all(item["price"] <= 10 for item in results)


def test_search_size_filter():
    results = search_listings("tee", size="M", max_price=50)
    assert all("m" in item["size"].lower() for item in results)


def test_search_top_result_for_graphic_tee():
    results = search_listings("vintage graphic tee", size=None, max_price=30)
    assert len(results) > 0
    assert results[0]["id"] == "lst_006"


# ── suggest_outfit ────────────────────────────────────────────────────────────

SAMPLE_ITEM = next(item for item in load_listings() if item["id"] == "lst_006")

MOCK_OUTFIT_RESPONSE = (
    "Pair the Graphic Tee with your baggy straight-leg jeans and chunky white sneakers "
    "for a relaxed streetwear look."
)


@patch("tools._call_llm", return_value=MOCK_OUTFIT_RESPONSE)
def test_suggest_outfit_with_wardrobe(mock_llm):
    result = suggest_outfit(SAMPLE_ITEM, get_example_wardrobe())
    assert isinstance(result, str)
    assert len(result.strip()) > 0
    mock_llm.assert_called_once()


@patch("tools._call_llm", return_value=MOCK_OUTFIT_RESPONSE)
def test_suggest_outfit_empty_wardrobe(mock_llm):
    """Empty wardrobe should return general advice, not raise or return empty string."""
    result = suggest_outfit(SAMPLE_ITEM, get_empty_wardrobe())
    assert isinstance(result, str)
    assert len(result.strip()) > 0
    mock_llm.assert_called_once()
    prompt = mock_llm.call_args[0][0]
    assert "has not added their wardrobe" in prompt


@patch("tools._call_llm", return_value="")
def test_suggest_outfit_llm_empty_fallback(mock_llm):
    """If LLM returns empty, tool still returns a non-empty fallback string."""
    result = suggest_outfit(SAMPLE_ITEM, get_empty_wardrobe())
    assert isinstance(result, str)
    assert len(result.strip()) > 0


# ── create_fit_card ───────────────────────────────────────────────────────────

def test_create_fit_card_empty_outfit():
    result = create_fit_card("", SAMPLE_ITEM)
    assert result == EMPTY_OUTFIT_ERROR


def test_create_fit_card_whitespace_outfit():
    result = create_fit_card("   ", SAMPLE_ITEM)
    assert result == EMPTY_OUTFIT_ERROR


@patch("tools._call_llm", return_value="scored this tee on depop for $24 and it slaps 🤍")
def test_create_fit_card_success(mock_llm):
    outfit = "Pair with baggy jeans and chunky sneakers."
    result = create_fit_card(outfit, SAMPLE_ITEM)
    assert isinstance(result, str)
    assert len(result.strip()) > 0
    assert result != EMPTY_OUTFIT_ERROR
    mock_llm.assert_called_once()
    assert mock_llm.call_args[1]["temperature"] == pytest.approx(0.9)


@patch("tools._call_llm")
def test_create_fit_card_uses_high_temperature(mock_llm):
    mock_llm.return_value = "caption one"
    create_fit_card("some outfit", SAMPLE_ITEM)
    assert mock_llm.call_args[1]["temperature"] >= 0.8
