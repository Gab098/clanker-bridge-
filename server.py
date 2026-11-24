from __future__ import annotations

import hmac
import os
import platform
from pathlib import Path
from typing import Any

import uvicorn
from mcp.server.fastmcp import FastMCP
from starlette.responses import JSONResponse

APP_NAME = "Clanker Bridge"
HOST = os.environ.get("CLANKER_HOST", "127.0.0.1")
PORT = int(os.environ.get("CLANKER_PORT", "8765"))
TOKEN = os.environ.get("CLANKER_BRIDGE_TOKEN", "")
WORKSPACE = Path(
    os.environ.get("CLANKER_WORKSPACE", str(Path.home() / "clanker-workspace"))
).expanduser().resolve()
MAX_FILE_BYTES = 1_000_000
BLOCKED_NAMES = {".git", ".ssh", ".gnupg", ".env", ".env.local"}

if not TOKEN or len(TOKEN) < 32:
    raise SystemExit(
        "Set CLANKER_BRIDGE_TOKEN to a random secret of at least 32 characters."
    )

WORKSPACE.mkdir(parents=True, exist_ok=True)
mcp = FastMCP(APP_NAME)


def resolve_workspace_path(relative_path: str) -> Path:
    """Resolve a user path without allowing traversal or symlink escapes."""
    raw = Path(relative_path or ".")
    if raw.is_absolute():
        raise ValueError("Use a relative path inside the workspace.")
    if ".." in raw.parts:
        raise ValueError("Path traversal is not allowed.")
    if any(part in BLOCKED_NAMES for part in raw.parts):
        raise ValueError("This path is blocked.")
    target = (WORKSPACE / raw).resolve()
    try:
        target.relative_to(WORKSPACE)
    except ValueError as exc:
        raise ValueError("Path is outside the workspace.") from exc
    return target


@mcp.tool()
def workspace_info() -> dict[str, Any]:
    """Return bridge status and the configured workspace path."""
    return {
        "name": APP_NAME,
        "status": "ready",
        "workspace": str(WORKSPACE),
        "platform": platform.platform(),
        "python": platform.python_version(),
        "host": HOST,
        "port": PORT,
    }


@mcp.tool()
def list_files(path: str = ".") -> list[dict[str, str]]:
    """List files and folders one level below a workspace-relative path."""
    folder = resolve_workspace_path(path)
    if not folder.exists() or not folder.is_dir():
        raise ValueError("Directory does not exist.")
    items = []
    for item in sorted(folder.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())):
        if item.name.startswith(".") or item.is_symlink():
            continue
        items.append({
            "name": item.name,
            "type": "directory" if item.is_dir() else "file",
        })
    return items[:200]


@mcp.tool()
def read_file(path: str) -> str:
    """Read a UTF-8 text file from the workspace (maximum 1 MB)."""
    target = resolve_workspace_path(path)
    if not target.is_file() or target.is_symlink():
        raise ValueError("File does not exist or is not a regular file.")
    if target.stat().st_size > MAX_FILE_BYTES:
        raise ValueError("File exceeds the 1 MB limit.")
    return target.read_text(encoding="utf-8")


@mcp.tool()
def write_file(path: str, content: str) -> dict[str, Any]:
    """Write UTF-8 text inside the workspace. Existing files are overwritten."""
    target = resolve_workspace_path(path)
    if target == WORKSPACE:
        raise ValueError("A file path is required.")
    if len(content.encode("utf-8")) > MAX_FILE_BYTES:
        raise ValueError("Content exceeds the 1 MB limit.")
    if target.exists() and (not target.is_file() or target.is_symlink()):
        raise ValueError("Target is not a regular file.")
    target.parent.mkdir(parents=True, exist_ok=True)
    target = resolve_workspace_path(path)
    target.write_text(content, encoding="utf-8")
    return {
        "written": True,
        "path": str(target.relative_to(WORKSPACE)),
        "bytes": target.stat().st_size,
    }


@mcp.custom_route("/healthz", methods=["GET"])
async def health_check(request):
    return JSONResponse({"status": "ok", "service": APP_NAME})


class BearerAuthMiddleware:
    """Require a bearer token on all HTTP routes except the health check."""

    def __init__(self, app, token: str):
        self.app = app
        self.token = token.encode("utf-8")

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope.get("path") == "/healthz":
            await self.app(scope, receive, send)
            return

        headers = dict(scope.get("headers", []))
        supplied = headers.get(b"authorization", b"")
        expected = b"Bearer " + self.token
        if not hmac.compare_digest(supplied, expected):
            response = JSONResponse({"error": "Unauthorized"}, status_code=401)
            await response(scope, receive, send)
            return

        await self.app(scope, receive, send)


def main() -> None:
    app = mcp.streamable_http_app()
    app.add_middleware(BearerAuthMiddleware, token=TOKEN)
    print(f"{APP_NAME} listening on http://{HOST}:{PORT}/mcp")
    print(f"Workspace: {WORKSPACE}")
    uvicorn.run(app, host=HOST, port=PORT, log_level="info")


if __name__ == "__main__":
    main()
