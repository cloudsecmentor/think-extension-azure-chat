import os
import codecs
from dataclasses import dataclass
from typing import Optional


@dataclass
class Inputs:
    content: str
    thread: str
    user: str
    id: Optional[str]


def _strip_quotes(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and (
        (value[0] == '"' and value[-1] == '"') or (value[0] == "'" and value[-1] == "'")
    ):
        return value[1:-1].strip()
    return value


def read_inputs() -> Inputs:
    raw_content = os.getenv("CONTENT", "")
    raw_content = _strip_quotes(raw_content.strip())
    try:
        content = codecs.decode(raw_content, "unicode_escape")
    except Exception:
        content = raw_content

    thread = _strip_quotes(os.getenv("THREAD_ID", "").strip())
    user = _strip_quotes(os.getenv("USER_ID", "").strip())
    id_raw = _strip_quotes(os.getenv("ID", "").strip())
    id_val = id_raw or None

    return Inputs(content=content, thread=thread, user=user, id=id_val)


def validate_inputs(inputs: Inputs) -> None:
    missing = [
        name
        for name, value in [
            ("THREAD_ID", inputs.thread),
            ("USER_ID", inputs.user),
        ]
        if not value
    ]
    if missing:
        raise RuntimeError(
            f"Missing required environment variables: {', '.join(missing)}"
        )


