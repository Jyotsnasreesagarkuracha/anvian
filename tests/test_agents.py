import pytest
from agents import process_query

def test_reverse_string():
    result = process_query("Write a Python function to reverse a string.")
    assert "def reverse_string" in result

def test_ambiguous_query():
    result = process_query("Write a function.")
    assert "clarify" in result.lower() or "more details" in result.lower()