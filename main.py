from fastapi import FastAPI

from app.routers import api_router

app = FastAPI(title="Knowledge Management")
app.include_router(api_router)


@app.get("/health")
async def health():
    return {"status": "ok"}
