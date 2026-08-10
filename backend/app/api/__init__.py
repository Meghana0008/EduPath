from fastapi import APIRouter

from app.api import routes_agent, routes_apps, routes_auth, routes_chat, routes_core, routes_docs


api_router = APIRouter(prefix="/api")
api_router.include_router(routes_auth.router, tags=["auth"])
api_router.include_router(routes_core.router, tags=["core"])
api_router.include_router(routes_apps.router, tags=["applications"])
api_router.include_router(routes_docs.router, tags=["documents"])
api_router.include_router(routes_agent.router, tags=["agent"])
api_router.include_router(routes_chat.router, tags=["chat"])
