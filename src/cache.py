import os
import time
from datetime import date
from typing import Optional

import boto3

TABLE_NAME = os.environ.get("CACHE_TABLE_NAME", "school-assistant-cache")
TTL_SECONDS = 2 * 60 * 60  # 2 hours


class BriefingCache:
    def __init__(self):
        self._table = boto3.resource("dynamodb").Table(TABLE_NAME)

    def get(self, for_date: date) -> Optional[str]:
        response = self._table.get_item(Key={"date": str(for_date)})
        item = response.get("Item")
        if item and int(item.get("ttl", 0)) > int(time.time()):
            return item["briefing"]
        return None

    def put(self, for_date: date, briefing: str) -> None:
        self._table.put_item(Item={
            "date": str(for_date),
            "briefing": briefing,
            "ttl": int(time.time()) + TTL_SECONDS,
        })
