from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, List, Optional

from azure.identity import DefaultAzureCredential
from langchain_core.messages import (
    AIMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_openai import AzureChatOpenAI

from .mcp_session_manager import get_mcp_session_manager

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


def _mcp_tools_to_openai_tools(mcp_tools: List[Any]) -> List[Dict[str, Any]]:
    tools: List[Dict[str, Any]] = []
    for tool in mcp_tools:
        # Obtain JSON schema for the tool parameters in a robust way
        schema = getattr(tool, "inputSchema", None)
        if hasattr(schema, "model_dump"):
            parameters = schema.model_dump()
        elif hasattr(schema, "dict"):
            parameters = schema.dict()
        elif hasattr(schema, "to_dict"):
            parameters = schema.to_dict()
        else:
            parameters = schema

        tools.append(
            {
                "type": "function",
                "function": {
                    "name": getattr(tool, "name", "unknown_tool"),
                    "description": getattr(tool, "description", ""),
                    "parameters": parameters or {"type": "object", "properties": {}},
                },
            }
        )
    return tools

def _messages_to_text(messages: List[Any]) -> str:
    # skip the first message (system message)
    return "\n".join([f"{m.type}: {m.content}" for m in messages[1:]])

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
        "you need to always use the tools you have available to you."
        "At the end of your response you have to provide:"
        " 1. list of all tools you used in your response. "
        " 2. web page addresses you used to get the information."
    )
    history_blob = _serialize_history_for_system_message(history)
    system_content = base_system if not history_blob else f"{base_system}\n\nHistory (raw):\n{history_blob}"

    messages: List[Any] = [SystemMessage(content=system_content), HumanMessage(content=user_query)]

    logger.info(
        f"LLM request prepared: endpoint={os.environ.get('AZURE_OPENAI_ENDPOINT')} "
        f"deployment={os.environ.get('AZURE_OPENAI_DEPLOYMENT')} "
        f"len(history)={(0 if history is None else len(history))}"
    )

    # If MCP is configured, engage tool loop similar to the _dev example
    max_tool_calls = int(os.environ.get("MAX_TOOL_CALL", "4"))
    # Prefer HTTP MCP via config.json if present
    mcp_manager = get_mcp_session_manager()
    await mcp_manager.initialize()
    connected_servers = await mcp_manager.get_connected_servers()
    logger.info(f"Connected servers: {connected_servers}")

    if connected_servers:
        try:
            logger.info(f"Using {len(connected_servers)} connected MCP servers.")

            # Aggregate tools across servers
            namespaced_tools: List[Dict[str, Any]] = []
            name_to_route: Dict[str, Dict[str, Any]] = {}
            for srv in connected_servers:
                srv_name = srv["name"]
                session = srv["session"]
                mcp_tool_list = (await session.list_tools()).tools
                logger.info(f"MCP tool list: {mcp_tool_list}")
                for tool in mcp_tool_list:
                    original_name = getattr(tool, "name", "unknown_tool")
                    namespaced_name = f"{srv_name}__{original_name}"

                    # Translate schema
                    schema = getattr(tool, "inputSchema", None)
                    if hasattr(schema, "model_dump"):
                        parameters = schema.model_dump()
                    elif hasattr(schema, "dict"):
                        parameters = schema.dict()
                    elif hasattr(schema, "to_dict"):
                        parameters = schema.to_dict()
                    else:
                        parameters = schema

                    namespaced_tools.append(
                        {
                            "type": "function",
                            "function": {
                                "name": namespaced_name,
                                "description": getattr(tool, "description", ""),
                                "parameters": parameters or {"type": "object", "properties": {}},
                            },
                        }
                    )
                    name_to_route[namespaced_name] = {
                        "session": session,
                        "original_name": original_name,
                    }

            logger.info(f"Namespaced tools: {namespaced_tools}")
            tool_enabled_model = model.bind_tools(namespaced_tools)

            tool_calls_used = 0
            while True:
                response: AIMessage = await tool_enabled_model.ainvoke(messages)

                if getattr(response, "tool_calls", None):
                    messages.append(response)
                    for tool_call in response.tool_calls:
                        if tool_calls_used >= max_tool_calls:
                            logger.info(
                                f"MAX_TOOL_CALL reached ({max_tool_calls}). Forcing final answer without more tools."
                            )
                            messages.append(
                                SystemMessage(
                                    content=(
                                        "Tool call limit reached. Provide the best possible answer "
                                        "using available information and previously returned tool results."
                                    )
                                )
                            )
                            final = await tool_enabled_model.ainvoke(messages)
                            final_text: str = (
                                final.content if isinstance(final.content, str) else str(final.content)
                            )
                            logger.info(f"LLM final reply (limit reached): {final_text[:500]}")
                            return final_text

                        name = tool_call.get("name") if isinstance(tool_call, dict) else getattr(tool_call, "name", None)
                        args = tool_call.get("args") if isinstance(tool_call, dict) else getattr(tool_call, "args", {})
                        tool_call_id = tool_call.get("id") if isinstance(tool_call, dict) else getattr(tool_call, "id", None)

                        route = name_to_route.get(name or "")
                        if not route:
                            logger.warning(f"No route found for tool '{name}', skipping")
                            continue
                        session = route["session"]
                        original_name = route["original_name"]

                        logger.info(f"Calling MCP tool: {name} -> {original_name} with args: {args}")
                        try:
                            result = await session.call_tool(original_name, args)
                        except Exception as tool_exc:
                            logger.exception(f"MCP tool '{name}' failed: {tool_exc}")
                            messages.append(
                                ToolMessage(
                                    content=f"Tool '{name}' execution error: {tool_exc}",
                                    tool_call_id=tool_call_id or (name or "tool"),
                                )
                            )
                            tool_calls_used += 1
                            continue

                        if hasattr(result, "content"):
                            tool_content = json.dumps(
                                getattr(result, "content"), ensure_ascii=False, default=str
                            )
                        else:
                            tool_content = json.dumps(result, ensure_ascii=False, default=str)

                        logger.info(f"MCP tool '{name}' reply: {tool_content[:500]}")

                        messages.append(
                            ToolMessage(
                                content=tool_content,
                                tool_call_id=tool_call_id or (name or "tool"),
                            )
                        )
                        tool_calls_used += 1

                    continue

                final_text: str = (
                    response.content if isinstance(response.content, str) else str(response.content)
                )
                final_text_and_response = f"{final_text}\n\n#Technical details\n\n{tool_calls_used} tool calls used\n\nraw messages: {_messages_to_text(messages)}"
                logger.info(f"LLM reply received02: {final_text_and_response[:500]}")
                return final_text_and_response

        except Exception as exc:
            logger.exception(
                f"MCP HTTP flow failed (falling back to plain LLM): {exc}"
            )

    # Plain LLM call without MCP tools
    try:
        response = await model.ainvoke(messages)
    except Exception as exc:
        logger.exception(f"LLM call failed: {exc}")
        raise

    text: str = response.content if isinstance(response.content, str) else str(response.content)
    text_and_response = f"No MCP tools used. Plain LLM call without MCP tools: \n{text}\n\nraw messages: {_messages_to_text(messages)}"
    logger.info(f"LLM reply received03: {text_and_response[:500]}")
    return text_and_response


