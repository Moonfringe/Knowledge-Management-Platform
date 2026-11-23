from fastapi import APIRouter

from . import notes
from . import tags
from . import auth

api_router = APIRouter()
api_router.include_router(notes.router)
api_router.include_router(tags.router)
api_router.include_router(auth.router)