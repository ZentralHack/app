"""One place that turns every error into an `ApiError` response (contract §2)."""

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

from app.agent.errors import InvalidInputError
from app.agent.orchestrator import RetryNotAllowedError
from app.llm.errors import LLMOutputError, LLMUnavailableError, RefusalError
from app.models.contract import ApiError
from app.runs import RunNotFoundError

log = logging.getLogger(__name__)

HTTP_CODES = {404: "nicht_gefunden", 405: "methode_nicht_erlaubt"}


def _error(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(ApiError(code=code, message=message).model_dump(), status_code=status)


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(RequestValidationError)
    async def invalid_request(_: Request, error: RequestValidationError) -> JSONResponse:
        fields = sorted({".".join(map(str, e["loc"][1:])) or "body" for e in error.errors()})
        return _error(400, "ungueltige_eingabe", f"Ungültige Eingabe: {', '.join(fields)}.")

    @app.exception_handler(InvalidInputError)
    async def invalid_input(_: Request, error: InvalidInputError) -> JSONResponse:
        return _error(400, "ungueltige_eingabe", error.message)

    @app.exception_handler(RunNotFoundError)
    async def run_not_found(_: Request, __: RunNotFoundError) -> JSONResponse:
        return _error(404, "run_nicht_gefunden", "Diese Analyse gibt es nicht (mehr).")

    @app.exception_handler(RetryNotAllowedError)
    async def retry_not_allowed(_: Request, __: RetryNotAllowedError) -> JSONResponse:
        return _error(
            409, "pruefung_laeuft", "Dieses Programm wird gerade geprüft oder ist fertig."
        )

    @app.exception_handler(LLMOutputError)
    @app.exception_handler(RefusalError)
    async def bad_llm_output(_: Request, error: LLMOutputError | RefusalError) -> JSONResponse:
        return _error(502, "ki_antwort_ungueltig", error.message)

    @app.exception_handler(LLMUnavailableError)
    async def llm_unavailable(_: Request, error: LLMUnavailableError) -> JSONResponse:
        return _error(503, "ki_nicht_verfuegbar", error.message)

    @app.exception_handler(HTTPException)
    async def http_error(_: Request, error: HTTPException) -> JSONResponse:
        code = HTTP_CODES.get(error.status_code, "http_fehler")
        return _error(error.status_code, code, "Diese Anfrage ist nicht möglich.")

    @app.exception_handler(Exception)
    async def unexpected(_: Request, error: Exception) -> JSONResponse:
        log.exception("Unerwarteter Fehler", exc_info=error)
        return _error(500, "interner_fehler", "Ein interner Fehler ist aufgetreten.")
