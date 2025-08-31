import os
import json
from typing import List, Dict

from dotenv import load_dotenv
from azure.identity import ClientSecretCredential, DefaultAzureCredential
from openai import AzureOpenAI
import streamlit as st


PAGE_TITLE: str = "Think Chat"


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
        if st.button("Clear chat history"):
            st.session_state.pop("messages", None)

    # Initialize chat history
    if "messages" not in st.session_state:
        st.session_state.messages = []  # type: ignore[attr-defined]

    # Render existing history
    render_chat_history(st.session_state.messages)  # type: ignore[arg-type]

    # Input box
    user_prompt: str | None = st.chat_input("Type your message and press Enter…")
    if user_prompt:
        # Append user message
        st.session_state.messages.append({  # type: ignore[attr-defined]
            "role": "user",
            "content": user_prompt,
        })
        with st.chat_message("user"):
            st.markdown(f"**User**\n\n{user_prompt}")

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

        # Append assistant reply
        st.session_state.messages.append({  # type: ignore[attr-defined]
            "role": "assistant",
            "content": assistant_reply,
        })
        with st.chat_message("assistant"):
            st.markdown(f"**Assistant**\n\n{assistant_reply}")


if __name__ == "__main__":
    main()


