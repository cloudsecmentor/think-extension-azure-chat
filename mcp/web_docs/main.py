import os
from typing import Optional
import logging

import httpx
from bs4 import BeautifulSoup
from mcp.server.fastmcp import FastMCP
from starlette.responses import JSONResponse
from dotenv import load_dotenv
import json


load_dotenv()

mcp = FastMCP(name="web_docs")
logger = logging.getLogger(__name__)


USER_AGENT = "docs-app/1.0"
SERPAPI_URL = "https://serpapi.com/search"

# Output safety limits to avoid oversized SSE/JSON-RPC frames
# These can be tuned via env vars if needed
MAX_PER_PAGE_CHARS = int(os.getenv("MAX_PER_PAGE_CHARS", "400"))
MAX_RESULTS = int(os.getenv("MAX_RESULTS", "2"))
MAX_FINAL_CHARS = int(os.getenv("MAX_FINAL_CHARS", "900"))


async def search_web(query: str) -> dict | None:
    api_key = os.getenv("SERPAPI_API_KEY") or os.getenv("SERPER_API_KEY")
    if not api_key:
        return {"organic_results": []}

    params = {
        "api_key": api_key,
        "engine": "google",
        "q": query,
        "google_domain": "google.com",
        "gl": "us",
        "hl": "en",
        "num": "5",
    }

    # Optional: allow overriding location via env
    if os.getenv("SERPAPI_LOCATION"):
        params["location"] = os.getenv("SERPAPI_LOCATION")

    headers = {
        "User-Agent": USER_AGENT,
    }

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                SERPAPI_URL, headers=headers, params=params, timeout=30.0
            )
            response.raise_for_status()
            return response.json()
        except (httpx.TimeoutException, httpx.HTTPError):
            return {"organic_results": []}


async def fetch_url(url: str) -> str:
    async with httpx.AsyncClient(headers={"User-Agent": USER_AGENT}) as client:
        try:
            response = await client.get(url, timeout=30.0)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")
            text = soup.get_text("\n", strip=True)
            # Cap extremely large pages to keep responses manageable for SSE transport
            if len(text) > MAX_PER_PAGE_CHARS:
                text = text[:MAX_PER_PAGE_CHARS] + "\n\n[...content truncated...]"
            return text
        except (httpx.TimeoutException, httpx.HTTPError):
            return ""

@mcp.tool()
async def fetch(url: str, selector: Optional[str] = None, timeout_seconds: int = 20) -> str:
    """
    Use this tool to fetch of a web page.

    - url: Full URL to fetch (http/https)
    - selector: Optional CSS selector to narrow the content. If omitted, returns page text.
    - timeout_seconds: HTTP timeout in seconds
    """
    async with httpx.AsyncClient(timeout=timeout_seconds, follow_redirects=True) as client:
        response = await client.get(url)
        response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    if selector:
        selected = soup.select(selector)
        text = "\n\n".join(elem.get_text("\n", strip=True) for elem in selected)
    else:
        text = soup.get_text("\n", strip=True)

    # Cap extremely large pages to keep responses manageable
    if len(text) > MAX_PER_PAGE_CHARS:
        text = text[:MAX_PER_PAGE_CHARS]

    return text


@mcp.tool()
async def get_docs(query: str) -> str:
    """
    Use this tool to search the web and return page text from top results.

    Args:
      query: The query to search for (e.g. "Chroma DB in LangChain")

    Returns:
      Aggregated text content from the top results
    """
    logger.info(f"get_docs invoked with query: {query}")
    results = await search_web(query)
    logger.info(f"search_web returned: {json.dumps(results, indent=2)[:500]}")
    organic = (results or {}).get("organic_results") or (results or {}).get("organic") or []
    if len(organic) == 0:
        return "No results found"

    texts: list[str] = []
    for result in organic[:MAX_RESULTS]:
        link = result.get("link")
        if not link:
            continue
        content = await fetch_url(link)
        if content:
            texts.append(f"From: {link}\n\n{content}")

    final_content = "\n\n".join(texts) if texts else "No results found"
    # Final safety cap to keep JSON-RPC message size in a safe range for SSE
    if len(final_content) > MAX_FINAL_CHARS:
        # Keep the beginning; append a concise tail marker
        final_content = final_content[:MAX_FINAL_CHARS] + "\n\n[...aggregated content truncated...]"
    logger.info(f"get_docs final content length: {len(final_content)}")
    return final_content


def main() -> None:
    port = int(os.getenv("PORT", "8801"))

    @mcp.custom_route("/health", methods=["GET"])
    async def health_check(request):
        return JSONResponse({"status": "ok", "server": "web_docs"})

    # Run using HTTP Stream transport
    mcp.settings.host = "0.0.0.0"
    mcp.settings.port = port
    mcp.run(transport="streamable-http")


if __name__ == "__main__":
    # Run inside an asyncio event loop friendly context
    try:
        main()
    except KeyboardInterrupt:
        pass


