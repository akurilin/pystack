from fastapi import APIRouter

from pystack_api.api.routes import health, tasks

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(tasks.router)
