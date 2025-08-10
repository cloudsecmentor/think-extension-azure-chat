from __future__ import annotations

from typing import Any, List, Optional
from uuid import UUID

from pydantic import BaseModel


class ThinkRequest(BaseModel):
    id: Optional[UUID] = None
    history: Optional[List[Any]] = None
    user_query: Optional[str] = None
