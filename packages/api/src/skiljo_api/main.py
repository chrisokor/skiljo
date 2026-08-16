from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException

from skiljo_api.error_handler import (
    http_exception_to_envelope,
    unhandled_exception_to_envelope,
    validation_exception_to_envelope,
)
from skiljo_api.routers import evals, jobs, policies, simulations, skills, tickets

app = FastAPI(title="Skiljo API")
app.include_router(policies.router)
app.include_router(skills.router)
app.include_router(jobs.router)
app.include_router(simulations.router)
app.include_router(tickets.router)
app.include_router(evals.router)

# Consistent error envelope for every error response: {"error": {"code", "message", "details"}}.
# See DESIGN_DOCUMENT.md Section 5.6 / Appendix B.
app.add_exception_handler(HTTPException, http_exception_to_envelope)
app.add_exception_handler(RequestValidationError, validation_exception_to_envelope)
app.add_exception_handler(Exception, unhandled_exception_to_envelope)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
