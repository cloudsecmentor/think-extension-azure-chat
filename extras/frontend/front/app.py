import os
import json
from typing import List, Dict

import requests
import streamlit as st


PAGE_TITLE: str = "Think Chat"
DEFAULT_API_URL: str = os.getenv(
    "THINK_API_URL", "http://host.docker.internal:5000/think"
)
REQUEST_TIMEOUT_SECONDS: int = int(os.getenv("THINK_API_TIMEOUT", "360"))


def render_chat_history(messages: List[Dict[str, str]]) -> None:
    for message in messages:
        role = message.get("role", "User")
        content = message.get("content", "")
        streamlit_role = "user" if role == "User" else "assistant"
        with st.chat_message(streamlit_role):
            label = "User" if role == "User" else "Agent"
            st.markdown(f"**{label}**\n\n{content}")


def build_history_strings(messages: List[Dict[str, str]]) -> List[str]:
    history_strings: List[str] = []
    for message in messages:
        role = message.get("role", "User")
        content = message.get("content", "")
        history_strings.append(f"{role}: {content}")
    return history_strings


def send_to_think_api(api_url: str, history: List[str], user_query: str) -> str:
    response = requests.post(
        api_url,
        json={"history": history, "user_query": user_query},
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    # API returns a plain string body
    return response.text


def main() -> None:
    st.set_page_config(page_title=PAGE_TITLE, page_icon="🧠", layout="centered")
    st.title(PAGE_TITLE)

    if "messages" not in st.session_state:
        st.session_state.messages = []  # type: ignore[attr-defined]

    # Render history first
    render_chat_history(st.session_state.messages)  # type: ignore[arg-type]

    # Chat input
    user_prompt: str | None = st.chat_input("Type your message and press Enter…")
    if user_prompt:
        # Append user message to state and display it
        st.session_state.messages.append({  # type: ignore[attr-defined]
            "role": "User",
            "content": user_prompt,
        })
        with st.chat_message("user"):
            st.markdown(f"**User**\n\n{user_prompt}")

        # Prepare request payload: previous conversation only
        prior_messages: List[Dict[str, str]] = st.session_state.messages[:-1]  # type: ignore[index]
        history_strings = build_history_strings(prior_messages)

        # Call API
        with st.spinner("Waiting for Agent response…"):
            try:
                agent_reply: str = send_to_think_api(
                    DEFAULT_API_URL, history_strings, user_prompt
                )
            except requests.Timeout:
                agent_reply = (
                    "The request to the Agent timed out. Please try again or simplify your query."
                )
            except requests.RequestException as request_error:
                agent_reply = f"Failed to reach Agent: {request_error}"

        # Optionally parse JSON to extract message
        parsed_reply = agent_reply
        try:
            maybe_json = json.loads(agent_reply)
            if isinstance(maybe_json, dict) and isinstance(maybe_json.get("message"), str):
                parsed_reply = maybe_json["message"]
            elif isinstance(maybe_json, str):
                parsed_reply = maybe_json
        except Exception:
            pass

        # Append Agent reply and render
        st.session_state.messages.append({  # type: ignore[attr-defined]
            "role": "Agent",
            "content": parsed_reply,
        })
        with st.chat_message("assistant"):
            st.markdown(f"**Agent**\n\n{parsed_reply}")


if __name__ == "__main__":
    main()


