"""Web UI template loader and static file utilities.

Provides functions to load and assemble HTML templates for the AgentSkillOS web UI.
"""

from pathlib import Path
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

# Directory paths
WEB_DIR = Path(__file__).parent
TEMPLATES_DIR = WEB_DIR / "templates"
STATIC_DIR = WEB_DIR / "static"


def get_template(name: str) -> str:
    """Load and assemble a template by name.

    Args:
        name: Template name without extension (currently only 'unified' is supported)

    Returns:
        Complete HTML string with base template and content merged

    The template system uses simple string replacement:
    - <!-- TITLE --> is replaced with the page title
    - <!-- HEAD_EXTRA --> is replaced with extra head content (e.g., D3.js for unified)
    - <!-- SCRIPTS --> is replaced with page-specific script tags
    - <!-- APP_DATA --> is replaced with the Alpine.js app function name
    - <!-- ESCAPE_HANDLER --> is replaced with the escape key handler
    - <!-- CONTENT --> is replaced with the page-specific HTML content
    - <!-- APP_SCRIPT --> is replaced with the page-specific JavaScript
    """
    base_html = (TEMPLATES_DIR / "base.html").read_text(encoding="utf-8")
    content_html = (TEMPLATES_DIR / f"{name}.html").read_text(encoding="utf-8")

    # Template-specific configurations
    configs = {
        "unified": {
            "title": "AgentSkillOS",
            "head_extra": '<script src="https://d3js.org/d3.v7.min.js"></script>\n<script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>',
            "scripts": '<script src="/static/js/unified.js"></script>',
            "app_data": "unifiedApp()",
            "escape_handler": "closeModals()",
            "app_script": "",
        },
    }

    config = configs.get(name, configs["unified"])

    # Perform replacements
    html = base_html
    html = html.replace("<!-- TITLE -->", config["title"])
    html = html.replace("<!-- HEAD_EXTRA -->", config["head_extra"])
    html = html.replace("<!-- SCRIPTS -->", config["scripts"])
    html = html.replace("<!-- APP_DATA -->", config["app_data"])
    html = html.replace("<!-- ESCAPE_HANDLER -->", config["escape_handler"])
    html = html.replace("<!-- CONTENT -->", content_html)
    html = html.replace("<!-- APP_SCRIPT -->", config["app_script"])

    return html


def mount_static(app: FastAPI) -> None:
    """Mount the static files directory to a FastAPI app.

    Args:
        app: FastAPI application instance

    Mounts static files at /static/ serving CSS and JS from the static directory.
    """
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


def get_unified_html() -> str:
    """Get the complete HTML for the unified UI.

    Returns:
        Complete HTML string ready to serve
    """
    return get_template("unified")


# For backwards compatibility - expose paths
__all__ = [
    "get_template",
    "mount_static",
    "get_unified_html",
    "WEB_DIR",
    "TEMPLATES_DIR",
    "STATIC_DIR",
]
