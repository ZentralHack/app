"""Production serving: the built frontend under the same origin and optional basic auth."""

import base64
import secrets
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request


class BasicAuthMiddleware(BaseHTTPMiddleware):
    """Protects every path (site and API) when BASIC_AUTH_USER and _PASSWORD are set."""

    def __init__(self, app, user: str, password: str) -> None:
        super().__init__(app)
        self._expected = f"{user}:{password}".encode()

    async def dispatch(self, request: Request, call_next):
        header = request.headers.get("authorization", "")
        if header.lower().startswith("basic "):
            try:
                given = base64.b64decode(header[6:].strip())
            except ValueError:
                given = b""
            if secrets.compare_digest(given, self._expected):
                return await call_next(request)
        return Response(
            status_code=401,
            headers={"WWW-Authenticate": 'Basic realm="FundPilot"'},
        )


def mount_frontend(app: FastAPI, dist: Path) -> None:
    """Static files from frontend/dist, every other non-API path falls back to index.html."""
    root = dist.resolve()
    index = root / "index.html"

    @app.get("/{path:path}", include_in_schema=False)
    async def spa(path: str) -> Response:
        if path == "api" or path.startswith("api/"):
            raise HTTPException(status_code=404)
        file = (root / path).resolve()
        if path and file.is_file() and file.is_relative_to(root):
            return FileResponse(file)
        return FileResponse(index)
