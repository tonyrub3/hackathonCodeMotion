"""Tests for claim decomposition utilities."""

from app.services.parsing.sentence_splitter import split_sentences


def test_split_simple_sentences():
    text = "The sky is blue. Water is wet. Fire is hot."
    result = split_sentences(text)
    assert len(result) == 3


def test_split_handles_abbreviations():
    text = "Dr. Smith said the rate is 2.5%. Mr. Jones agreed."
    result = split_sentences(text)
    assert len(result) == 2


def test_split_empty_text():
    assert split_sentences("") == []


def test_split_single_sentence():
    text = "Inflation in Italy rose to 2 percent."
    result = split_sentences(text)
    assert len(result) == 1
    assert "Inflation" in result[0]
