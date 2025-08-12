from __future__ import annotations

from typing import Any, List, Optional

from pydantic import BaseModel


class AgentRequest(BaseModel):
    user_query: str
    history: Optional[List[Any]] = None


