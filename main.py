import logging

from fastapi import FastAPI

from app.exceptions import register_exception_handlers
from app.routers import api_router

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

app = FastAPI(title="Knowledge Management")
register_exception_handlers(app)
app.include_router(api_router)


@app.get("/health")
async def health():
    return {"status": "ok"}
