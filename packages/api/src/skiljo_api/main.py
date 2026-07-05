from fastapi import FastAPI

from skiljo_api.routers import jobs, simulations, skills

app = FastAPI(title="Skiljo API")
app.include_router(skills.router)
app.include_router(jobs.router)
app.include_router(simulations.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
