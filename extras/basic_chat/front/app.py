import os
import json
from typing import List, Dict

from dotenv import load_dotenv
from azure.identity import ClientSecretCredential, DefaultAzureCredential
from openai import AzureOpenAI
import streamlit as st

# New imports for persistence
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path


PAGE_TITLE: str = "Think Chat"


# ----------------------
# Persistence utilities
# ----------------------

def get_db_path() -> str:
    db_path = os.getenv("CHAT_DB_PATH", "/data/chat.db")
    # Ensure parent directory exists
    Path(os.path.dirname(db_path) or ".").mkdir(parents=True, exist_ok=True)
    return db_path


def init_db() -> None:
    db_path = get_db_path()
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS conversations (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(conversation_id) REFERENCES conversations(id)
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_messages_conversation_created ON messages(conversation_id, created_at)"
        )


def list_conversations(limit: int = 50) -> list[dict]:
    db_path = get_db_path()
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT id, title, created_at, updated_at
            FROM conversations
            ORDER BY datetime(updated_at) DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]


def load_messages_from_db(conversation_id: str) -> list[dict]:
    db_path = get_db_path()
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT role, content, created_at
            FROM messages
            WHERE conversation_id = ?
            ORDER BY datetime(created_at) ASC
            """,
            (conversation_id,),
        ).fetchall()
        return [{"role": r["role"], "content": r["content"]} for r in rows]


def create_conversation(title: str) -> str:
    db_path = get_db_path()
    conversation_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "INSERT INTO conversations (id, title, created_at, updated_at) VALUES (?, ?, ?, ?)",
            (conversation_id, title, now, now),
        )
    return conversation_id


def update_conversation_title(conversation_id: str, title: str) -> None:
    db_path = get_db_path()
    now = datetime.utcnow().isoformat()
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "UPDATE conversations SET title = ?, updated_at = ? WHERE id = ?",
            (title, now, conversation_id),
        )


def append_message_to_db(conversation_id: str, role: str, content: str) -> None:
    db_path = get_db_path()
    now = datetime.utcnow().isoformat()
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "INSERT INTO messages (conversation_id, role, content, created_at) VALUES (?, ?, ?, ?)",
            (conversation_id, role, content, now),
        )
        conn.execute(
            "UPDATE conversations SET updated_at = ? WHERE id = ?",
            (now, conversation_id),
        )


def delete_conversation(conversation_id: str) -> None:
    db_path = get_db_path()
    with sqlite3.connect(db_path) as conn:
        conn.execute("DELETE FROM messages WHERE conversation_id = ?", (conversation_id,))
        conn.execute("DELETE FROM conversations WHERE id = ?", (conversation_id,))


# ----------------------
# Existing app code
# ----------------------

def initialize_env() -> None:
    load_dotenv()


def get_azure_openai_client() -> AzureOpenAI:
    endpoint: str | None = os.getenv("AZURE_OPENAI_ENDPOINT")
    api_version: str = os.getenv("AZURE_OPENAI_API_VERSION", "2025-01-01-preview")
    tenant_id: str | None = os.getenv("AZURE_TENANT_ID")
    client_id: str | None = os.getenv("AZURE_CLIENT_ID")
    client_secret: str | None = os.getenv("AZURE_CLIENT_SECRET", "")

    if not endpoint:
        raise ValueError("AZURE_OPENAI_ENDPOINT is not set in .env or environment")

    # Prefer explicit client secret credential if provided, else fall back
    credential = (
        ClientSecretCredential(
            tenant_id=tenant_id or "",
            client_id=client_id or "",
            client_secret=client_secret or "",
        )
        if tenant_id and client_id and client_secret
        else DefaultAzureCredential(exclude_interactive_browser_credential=True)
    )

    scope: str = "https://cognitiveservices.azure.com/.default"

    def token_provider() -> str:
        return credential.get_token(scope).token

    return AzureOpenAI(
        azure_endpoint=endpoint,
        api_version=api_version,
        azure_ad_token_provider=token_provider,
    )


def render_chat_history(messages: List[Dict[str, str]]) -> None:
    for message in messages:
        role = message.get("role", "user").lower()
        content = message.get("content", "")
        streamlit_role = "user" if role == "user" else "assistant"
        with st.chat_message(streamlit_role):
            label = "User" if role == "user" else "Assistant"
            st.markdown(f"**{label}**\n\n{content}")


def load_frontend_config() -> tuple[list[str], str]:
    config_path = os.path.join(os.path.dirname(__file__), "config.json")
    default_deployments: list[str] = ["gpt-5-chat-deployment"]
    default_choice: str = "gpt-5-chat-deployment"

    try:
        with open(config_path, "r", encoding="utf-8") as config_file:
            data = json.load(config_file)
            deployments = data.get("deployments", default_deployments)
            if not isinstance(deployments, list) or not all(isinstance(d, str) for d in deployments):
                deployments = default_deployments
            default_name = data.get("default_deployment", default_choice)
            if not isinstance(default_name, str) or not default_name:
                default_name = default_choice
    except Exception:
        deployments = default_deployments
        default_name = default_choice

    if default_name not in deployments:
        deployments = [default_name] + [d for d in deployments if d != default_name]

    return deployments, default_name


def main() -> None:
    initialize_env()
    init_db()

    st.set_page_config(page_title=PAGE_TITLE, page_icon="🧠", layout="centered")
    st.title(PAGE_TITLE)

    # Sidebar configuration
    with st.sidebar:
        st.subheader("Settings")
        default_temperature = float(os.getenv("LLM_TEMPERATURE", "1"))
        temperature: float = st.slider("Temperature", 0.0, 2.0, default_temperature, 0.1)
        deployments, default_name = load_frontend_config()
        try:
            default_index = deployments.index(default_name)
        except ValueError:
            default_index = 0
        selected_deployment: str = st.selectbox(
            "Azure OpenAI deployment name",
            options=deployments,
            index=default_index,
            help="Choose the Chat Completions deployment",
        )

        st.divider()
        st.subheader("Conversations")
        conversations = list_conversations(limit=100)

        # Action buttons
        col_new, col_del = st.columns(2)
        with col_new:
            if st.button("New chat"):
                st.session_state.pop("conversation_id", None)
                st.session_state.messages = []  # type: ignore[attr-defined]
                st.rerun()
        with col_del:
            can_delete = bool(st.session_state.get("conversation_id"))
            if st.button("Delete", disabled=not can_delete):
                conv_id_to_delete = st.session_state.get("conversation_id")
                if conv_id_to_delete:
                    delete_conversation(conv_id_to_delete)
                st.session_state.pop("conversation_id", None)
                st.session_state.messages = []  # type: ignore[attr-defined]
                st.rerun()

        # Current selection
        current_conv_id: str | None = st.session_state.get("conversation_id")

        # List conversations with most recent on top
        for conv in conversations:
            conv_id = conv["id"]
            is_selected = (conv_id == current_conv_id)
            label = f"{('▶ ' if is_selected else '')}{conv['title']} · {conv['updated_at'].split('T')[0]}"
            if st.button(label, key=f"convbtn_{conv_id}"):
                st.session_state["conversation_id"] = conv_id
                try:
                    st.session_state.messages = load_messages_from_db(conv_id)  # type: ignore[attr-defined]
                except Exception as load_err:
                    st.warning(f"Failed to load saved conversation: {load_err}")
                    st.session_state.messages = []  # type: ignore[attr-defined]
                st.rerun()

    # Initialize chat history in memory
    if "messages" not in st.session_state:
        st.session_state.messages = []  # type: ignore[attr-defined]

    # If a conversation is selected and in-memory messages are empty, load from DB
    current_conv_id = st.session_state.get("conversation_id")
    if current_conv_id and not st.session_state.messages:
        try:
            st.session_state.messages = load_messages_from_db(current_conv_id)  # type: ignore[attr-defined]
        except Exception as load_err:
            st.warning(f"Failed to load saved conversation: {load_err}")
            st.session_state.messages = []  # type: ignore[attr-defined]

    # Render existing history
    render_chat_history(st.session_state.messages)  # type: ignore[arg-type]

    # Input box
    user_prompt: str | None = st.chat_input("Type your message and press Enter…")
    if user_prompt:
        # Append user message (in-memory)
        st.session_state.messages.append({  # type: ignore[attr-defined]
            "role": "user",
            "content": user_prompt,
        })
        with st.chat_message("user"):
            st.markdown(f"**User**\n\n{user_prompt}")

        # Ensure we have a conversation id; create if first time
        conversation_id: str | None = st.session_state.get("conversation_id")
        if not conversation_id:
            # Use first user message as title (truncated)
            title = user_prompt.strip().splitlines()[0][:80] or "New conversation"
            try:
                conversation_id = create_conversation(title)
            except Exception as create_err:
                st.error(f"Failed to create conversation: {create_err}")
                conversation_id = str(uuid.uuid4())
            st.session_state["conversation_id"] = conversation_id
        else:
            # If conversation exists but has placeholder title, optionally update on first user message
            try:
                update_conversation_title(conversation_id, user_prompt.strip().splitlines()[0][:80] or "Conversation")
            except Exception:
                pass

        # Persist the user message to DB
        try:
            append_message_to_db(conversation_id, "user", user_prompt)
        except Exception as persist_err:
            st.warning(f"Failed to save user message: {persist_err}")

        if not selected_deployment:
            with st.chat_message("assistant"):
                st.warning("Please set the Azure OpenAI deployment name in the sidebar.")
            return

        # Build messages for Azure OpenAI
        chat_messages = [
            {"role": m.get("role", "user"), "content": m.get("content", "")}
            for m in st.session_state.messages
        ]

        with st.spinner("Waiting for Assistant response…"):
            try:
                client = get_azure_openai_client()
                response = client.chat.completions.create(
                    model=selected_deployment,
                    messages=chat_messages,
                    temperature=temperature,
                )
                assistant_reply: str = response.choices[0].message.content or ""
            except Exception as err:  # Broad to surface SDK/HTTP errors to the user
                assistant_reply = f"Error calling Azure OpenAI: {err}"

        # Append assistant reply (in-memory)
        st.session_state.messages.append({  # type: ignore[attr-defined]
            "role": "assistant",
            "content": assistant_reply,
        })
        with st.chat_message("assistant"):
            st.markdown(f"**Assistant**\n\n{assistant_reply}")

        # Persist assistant reply to DB
        try:
            append_message_to_db(conversation_id, "assistant", assistant_reply)
        except Exception as persist_err:
            st.warning(f"Failed to save assistant message: {persist_err}")


if __name__ == "__main__":
    main()


