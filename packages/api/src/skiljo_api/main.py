from fastapi import FastAPI

from skiljo_api.routers import skills

app = FastAPI(title="Skiljo API")
app.include_router(skills.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
