from __future__ import annotations

import asyncio
import json
import logging
import os
from contextlib import AsyncExitStack
from datetime import timedelta
from typing import Any, Dict, List, Optional

import httpx
from urllib.parse import urlsplit, urlunsplit
from langchain_core.messages import (
    AIMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)

# Optional MCP imports
try:
    from mcp.client.session import ClientSession
    from mcp.client.streamable_http import streamablehttp_client
except ImportError:
    ClientSession = None
    streamablehttp_client = None

logger = logging.getLogger("agent_service.mcp_manager")


class MCPSessionManager:
    """Handles discovery, connection, and lifecycle of MCP sessions."""

    def __init__(self, config_path: Optional[str] = None):
        self._config_path = config_path
        self._exit_stack = AsyncExitStack()
        self._connected_servers: List[Dict[str, Any]] = []
        self._lock = asyncio.Lock()
        self._is_initialized = False

    async def initialize(self):
        """Connects to all configured MCP servers."""
        async with self._lock:
            if self._is_initialized:
                return
            
            logger.info("Initializing MCP Session Manager...")
            config = self._load_mcp_config()
            logger.info(f"MCP config: {config}")
            if config and isinstance(config.get("mcp_servers"), list):
                servers_cfg: List[Dict[str, Any]] = config["mcp_servers"]
                self._connected_servers = await self._connect_all(servers_cfg)
            
            self._is_initialized = True
            logger.info(f"MCP Session Manager initialized. Connected to {len(self._connected_servers)} servers.")

    async def close(self):
        """Closes all MCP connections."""
        logger.info("Closing MCP Session Manager...")
        await self._exit_stack.aclose()
        self._is_initialized = False
        logger.info("MCP Session Manager closed.")

    async def get_connected_servers(self) -> List[Dict[str, Any]]:
        """Returns the list of successfully connected server sessions."""
        if not self._is_initialized:
            await self.initialize()
        return self._connected_servers

    def _load_mcp_config(self) -> Optional[Dict[str, Any]]:
        env_path = os.environ.get("MCP_CONFIG_PATH")
        if env_path:
            config_path = env_path
        else:
            base_dir = os.path.dirname(__file__)
            config_path = os.path.normpath(
                os.path.join(base_dir, "..", "config", "config.json")
            )

        try:
            with open(config_path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
                logger.info(f"Loaded MCP config from {config_path}")
                return cfg
        except FileNotFoundError:
            logger.warning(f"MCP config not found at {config_path}, skipping.")
            return None
        except Exception:
            logger.exception(f"Failed to read MCP config at {config_path}")
            return None

    async def _connect_all(self, servers: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        logger.info(f"_connect_all: Connecting to MCP servers: {servers}")
        if not ClientSession or not streamablehttp_client:
            logger.error("MCP modules not available. Please install 'mcp'.")
            return []

        connected = []
        for server in servers:
            name = server.get("name", "unknown_server")
            address = server.get("address")
            logger.info(f"Connecting to MCP server '{name}' at {address}")
            if not address:
                logger.warning(f"Skipping MCP server '{name}' due to missing address.")
                continue

            max_retries = int(os.environ.get("MCP_CONNECT_RETRIES", "10"))
            base_delay_seconds = float(os.environ.get("MCP_CONNECT_BASE_DELAY", "1.0"))
            max_delay_seconds = float(os.environ.get("MCP_CONNECT_MAX_DELAY", "10.0"))

            attempt = 0
            while True:
                try:
                    # Probe health endpoint before opening stream to avoid creating half-open contexts
                    # Build candidate health URLs robustly from the address path and fallbacks
                    split = urlsplit(address)
                    path = split.path or "/"
                    candidates: list[str] = []
                    if path.endswith("/mcp/"):
                        candidates.append(path[:-5] + "/health")  # /<prefix>/health
                    elif path.endswith("/mcp"):
                        candidates.append(path[:-4] + "/health")
                    else:
                        candidates.append(path.rstrip("/") + "/health")
                    # Add parent-level aliases: /health/<name> and root /health
                    candidates.append(f"/health/{name}")
                    candidates.append("/health")

                    health_ok = False
                    last_error: Exception | None = None
                    for hp in candidates:
                        health_url = urlunsplit((split.scheme, split.netloc, hp, "", ""))
                        try:
                            async with httpx.AsyncClient(timeout=5.0) as client:
                                resp = await client.get(health_url)
                                if resp.status_code == 200:
                                    health_ok = True
                                    break
                                last_error = RuntimeError(
                                    f"Health check failed with status {resp.status_code}"
                                )
                        except Exception as health_exc:
                            last_error = health_exc

                    if not health_ok:
                        attempt += 1
                        if attempt > max_retries:
                            logger.exception(
                                f"MCP server '{name}' health check failed after {max_retries} retries: {last_error}"
                            )
                            break
                        delay = min(max_delay_seconds, base_delay_seconds * (2 ** (attempt - 1)))
                        logger.warning(
                            f"Health check for MCP server '{name}' failed: {last_error}. Retrying in {delay:.1f}s..."
                        )
                        await asyncio.sleep(delay)
                        continue

                    # Open contexts in a temporary stack, initialize, then transfer to the main stack atomically
                    async with AsyncExitStack() as temp_stack:
                        transport_context = streamablehttp_client(
                            url=address, timeout=timedelta(seconds=60)
                        )
                        read_stream, write_stream, _ = await temp_stack.enter_async_context(transport_context)
                        session = await temp_stack.enter_async_context(
                            ClientSession(read_stream, write_stream)
                        )
                        await session.initialize()

                        # Detach resources from temp_stack and attach their close callbacks to the main stack
                        detached = temp_stack.pop_all()
                        self._exit_stack.push_async_callback(detached.aclose)

                        connected.append({"name": name, "address": address, "session": session})
                        logger.info(f"Connected to MCP server '{name}' at {address}")
                    break
                except Exception as exc:
                    attempt += 1
                    if attempt > max_retries:
                        logger.exception(
                            f"Failed to connect to MCP server '{name}' at {address} after {max_retries} retries"
                        )
                        break
                    delay = min(max_delay_seconds, base_delay_seconds * (2 ** (attempt - 1)))
                    logger.warning(
                        f"Attempt {attempt}/{max_retries} to connect to MCP server '{name}' at {address} failed: {exc}. "
                        f"Retrying in {delay:.1f}s..."
                    )
                    await asyncio.sleep(delay)
        
        return connected

# Singleton instance
session_manager = MCPSessionManager()

def get_mcp_session_manager() -> MCPSessionManager:
    return session_manager
