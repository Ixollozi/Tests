from typing import Any

from fastapi import HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


class AppError(Exception):
    def __init__(self, detail: str, code: str, status_code: int = status.HTTP_400_BAD_REQUEST):
        self.detail = detail
        self.code = code
        self.status_code = status_code
        super().__init__(detail)


async def app_error_handler(_: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail, "code": exc.code},
    )


async def http_exception_handler(_: Request, exc: HTTPException) -> JSONResponse:
    detail = exc.detail
    code = "http_error"
    if isinstance(detail, dict):
        code = detail.get("code", code)
        detail = detail.get("detail", str(detail))
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": detail, "code": code},
        headers=getattr(exc, "headers", None),
    )


async def validation_exception_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
    errors: list[dict[str, Any]] = []
    for err in exc.errors():
        errors.append(
            {
                "loc": list(err.get("loc", [])),
                "msg": err.get("msg"),
                "type": err.get("type"),
            }
        )
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": "Validation error", "code": "validation_error", "errors": errors},
    )
