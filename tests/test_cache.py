import os
import time
from datetime import date
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture(autouse=True)
def env(monkeypatch):
    monkeypatch.setenv("CACHE_TABLE_NAME", "school-assistant-cache")


def test_cache_miss_returns_none():
    mock_table = MagicMock()
    mock_table.get_item.return_value = {}

    with patch("boto3.resource") as mock_resource:
        mock_resource.return_value.Table.return_value = mock_table
        from cache import BriefingCache
        cache = BriefingCache()
        result = cache.get(date(2026, 5, 20))

    assert result is None


def test_cache_hit_returns_briefing():
    mock_table = MagicMock()
    mock_table.get_item.return_value = {
        "Item": {
            "date": "2026-05-20",
            "briefing": "Good morning! Alice has PE today.",
            "ttl": int(time.time()) + 3600,
        }
    }

    with patch("boto3.resource") as mock_resource:
        mock_resource.return_value.Table.return_value = mock_table
        from cache import BriefingCache
        cache = BriefingCache()
        result = cache.get(date(2026, 5, 20))

    assert result == "Good morning! Alice has PE today."


def test_expired_cache_returns_none():
    mock_table = MagicMock()
    mock_table.get_item.return_value = {
        "Item": {
            "date": "2026-05-20",
            "briefing": "stale briefing",
            "ttl": int(time.time()) - 1,
        }
    }

    with patch("boto3.resource") as mock_resource:
        mock_resource.return_value.Table.return_value = mock_table
        from cache import BriefingCache
        cache = BriefingCache()
        result = cache.get(date(2026, 5, 20))

    assert result is None
