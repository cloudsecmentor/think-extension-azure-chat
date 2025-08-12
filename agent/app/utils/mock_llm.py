from __future__ import annotations

import asyncio
from typing import Any, List, Optional


async def generate_mock_reply(
    user_query: str,
    history: Optional[List[Any]] = None,
    delay_seconds: float = 5.0,
) -> str:
    """Simulate a long-running LLM call with a deterministic reply."""
    await asyncio.sleep(delay_seconds)
    return (
        f"Response to '{user_query}' is that SITMD is a short hand for Super Intelligent Teleport Master Data."
    )


