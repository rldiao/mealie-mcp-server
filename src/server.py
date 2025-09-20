import logging
import os
import traceback

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

from mealie import MealieFetcher
from prompts import register_prompts
from tools import register_all_tools

# Load environment variables first
load_dotenv()

# Get log level from environment variable with INFO as default
log_level_name = os.getenv("LOG_LEVEL", "INFO")
log_level = getattr(logging, log_level_name.upper(), logging.INFO)

# Configure logging
logging.basicConfig(
    level=log_level,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(), logging.FileHandler("mealie_mcp_server.log")],
)
logger = logging.getLogger("mealie-mcp")

mcp = FastMCP("mealie")

MEALIE_BASE_URL = os.getenv("MEALIE_BASE_URL")
MEALIE_API_KEY = os.getenv("MEALIE_API_KEY")
if not MEALIE_BASE_URL or not MEALIE_API_KEY:
    raise ValueError(
        "MEALIE_BASE_URL and MEALIE_API_KEY must be set in environment variables."
    )

try:
    mealie = MealieFetcher(
        base_url=MEALIE_BASE_URL,
        api_key=MEALIE_API_KEY,
    )
except Exception as e:
    logger.error({"message": "Failed to initialize Mealie client", "error": str(e)})
    logger.debug({"message": "Error traceback", "traceback": traceback.format_exc()})
    raise

register_prompts(mcp)
register_all_tools(mcp, mealie)

if __name__ == "__main__":
    try:
        logger.info({"message": "Starting Mealie MCP Server"})
        mcp.run(transport="stdio")
    except Exception as e:
        logger.critical(
            {"message": "Fatal error in Mealie MCP Server", "error": str(e)}
        )
        logger.debug(
            {"message": "Error traceback", "traceback": traceback.format_exc()}
        )
        raise
