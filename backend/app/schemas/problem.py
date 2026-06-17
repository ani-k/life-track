"""
RFC 7807 Problem Details for AI endpoints.
"""
from __future__ import annotations

from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse


class AIProblemDetail(Exception):
    """Raised when the LLM returns invalid or unparseable output."""

    def __init__(
        self,
        detail: str,
        status_code: int = 422,
        instance: str | None = None,
        extra: dict[str, Any] | None = None,
    ) -> None:
        self.type = "about:blank"
        self.title = "AI Processing Error"
        self.status = status_code
        self.detail = detail
        self.instance = instance
        self.extra = extra or {}
        super().__init__(detail)


def problem_response(exc: AIProblemDetail, request: Request) -> JSONResponse:
    body: dict[str, Any] = {
        "type": exc.type,
        "title": exc.title,
        "status": exc.status,
        "detail": exc.detail,
    }
    if exc.instance:
        body["instance"] = exc.instance
    body.update(exc.extra)
    return JSONResponse(status_code=exc.status, content=body)