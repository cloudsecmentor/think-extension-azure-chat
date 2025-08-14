import logging
import os
import shutil
import subprocess

from mcp.server.fastmcp import FastMCP
from starlette.responses import JSONResponse


mcp = FastMCP(name="date")
logger = logging.getLogger(__name__)


@mcp.tool()
async def date_now() -> str:
    """
    Use this tool to get the current date and time using the host OS 'date' command.
    """
    logger.info("date_now invoked")
    date_path = shutil.which("date")
    if not date_path:
        return "Error: 'date' command not found on PATH"

    try:
        output_bytes = subprocess.check_output([date_path], stderr=subprocess.STDOUT, timeout=5)
        result = output_bytes.decode(errors="replace").strip()
        logger.info(f"date_now result: {result}")
        return result
    except subprocess.CalledProcessError as exc:
        error_msg = exc.output.decode(errors="replace").strip()
        logger.error(f"Error running date: {error_msg}")
        return f"Error running date: {error_msg}"
    except Exception as exc:  # noqa: BLE001 - return error text to the caller
        return f"Error running date: {exc}"


def main() -> None:
    port = int(os.getenv("PORT", "8802"))

    @mcp.custom_route("/health", methods=["GET"])
    async def health_check(request):  # type: ignore[unused-ignore]
        return JSONResponse({"status": "ok", "server": "date"})

    mcp.settings.host = "0.0.0.0"
    mcp.settings.port = port
    mcp.run(transport="streamable-http")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass


