from fastapi import APIRouter
from app.api.v1.ai import router as ai_router
from app.api.v1.nodes import router as nodes_router
from app.api.v1.spaces import router as spaces_router
from app.api.v1.templates import router as templates_router

router = APIRouter()
router.include_router(spaces_router)
router.include_router(nodes_router)
router.include_router(templates_router)
router.include_router(ai_router)
