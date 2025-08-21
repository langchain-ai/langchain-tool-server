from fastapi import APIRouter
from fastapi.responses import HTMLResponse
from typing_extensions import TypedDict

from langchain_tool_server._version import __version__

from .splash import SPLASH


class InfoResponse(TypedDict):
    """Get information about the server."""

    version: str


router = APIRouter()


@router.get("/", response_class=HTMLResponse)
async def index() -> str:
    SPLASH_HTML = SPLASH.replace("\n", "<br>")
    html_content = f"""
    <html>
        <head>
            <title>LangChain Tool Server</title>
        </head>
        <body>
        <div>
        <p style="white-space: pre-wrap; font-family: monospace;">
            {SPLASH_HTML}
        </p>
        </div>
        <div>
            <p>
                <ul>
                    <li><strong>Version</strong>: {__version__}</li>
                    <li><a href="docs">Docs</strong></li>
                </ul>
            </p>
        </div>
        </body>
    </html>
    """

    return html_content


@router.get("/info")
def get_info() -> InfoResponse:
    """Get information about the server."""
    return {"version": __version__}


@router.get("/health")
def health() -> dict:
    """Are we OK?"""
    return {"status": "OK"}
