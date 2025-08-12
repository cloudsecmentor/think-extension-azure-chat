from __future__ import annotations

import json
import logging
import os
from typing import Any, List, Optional

from azure.identity import DefaultAzureCredential
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import AzureChatOpenAI


logger = logging.getLogger("agent_service.llm")


def _get_azure_chat_model() -> AzureChatOpenAI:
    """Create and return an AzureChatOpenAI model authenticated via DefaultAzureCredential.

    Required environment variables:
      - AZURE_OPENAI_ENDPOINT: e.g. https://<resource-name>.openai.azure.com
      - AZURE_OPENAI_API_VERSION: e.g. 2024-02-15-preview
      - AZURE_OPENAI_DEPLOYMENT: the deployment name of the chat model (e.g., gpt-4o)
    """
    endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT")
    api_version = os.environ.get("AZURE_OPENAI_API_VERSION", "2024-02-15-preview")
    deployment = os.environ.get("AZURE_OPENAI_DEPLOYMENT")
    api_key = os.environ.get("AZURE_OPENAI_API_KEY")

    if not endpoint:
        raise RuntimeError("AZURE_OPENAI_ENDPOINT is not set")
    if not deployment:
        raise RuntimeError("AZURE_OPENAI_DEPLOYMENT is not set")

    # Prefer API key if present (useful for local/dev), else use AAD via DefaultAzureCredential
    if api_key:
        logger.info("Using Azure OpenAI API key authentication")
        return AzureChatOpenAI(
            azure_endpoint=endpoint,
            api_version=api_version,
            azure_deployment=deployment,
            api_key=api_key,
            temperature=float(os.environ.get("LLM_TEMPERATURE", "0")),
            max_tokens=None,
        )

    logger.info("Using Azure OpenAI AAD authentication via DefaultAzureCredential")
    credential = DefaultAzureCredential(exclude_cli_credential=True)

    def token_provider() -> str:
        token = credential.get_token("https://cognitiveservices.azure.com/.default")
        return token.token

    return AzureChatOpenAI(
        azure_endpoint=endpoint,
        api_version=api_version,
        azure_deployment=deployment,
        azure_ad_token_provider=token_provider,  # type: ignore[arg-type]
        temperature=float(os.environ.get("LLM_TEMPERATURE", "0")),
        max_tokens=None,
    )


def _serialize_history_for_system_message(history: Optional[List[Any]]) -> str:
    if not history:
        return ""
    try:
        return json.dumps(history, ensure_ascii=False, indent=None)
    except Exception:
        return str(history)


async def generate_reply(user_query: str, history: Optional[List[Any]] = None) -> str:
    """Generate a reply using Azure OpenAI via LangChain.

    - Builds a simple system message.
    - Injects raw history (best-effort serialization) into the system message.
    - Adds the user message from user_query.
    - Logs request and reply.
    - Returns the parsed text content.
    """
    model = _get_azure_chat_model()

    base_system = (
        "You are a helpful assistant. If prior conversation history is provided, "
        "use it to maintain context, but do not repeat it back verbatim."
    )
    history_blob = _serialize_history_for_system_message(history)
    system_content = base_system if not history_blob else f"{base_system}\n\nHistory (raw):\n{history_blob}"

    messages = [
        SystemMessage(content=system_content),
        HumanMessage(content=user_query),
    ]

    logger.info("LLM request prepared: endpoint=%s deployment=%s len(history)=%s", os.environ.get("AZURE_OPENAI_ENDPOINT"), os.environ.get("AZURE_OPENAI_DEPLOYMENT"), 0 if history is None else len(history))

    try:
        response = await model.ainvoke(messages)
    except Exception as exc:
        logger.exception("LLM call failed: %s", exc)
        raise

    # LangChain ChatResult -> pick the content text
    text: str = response.content if isinstance(response.content, str) else str(response.content)

    logger.info("LLM reply received: %s", text[:500])
    return text


