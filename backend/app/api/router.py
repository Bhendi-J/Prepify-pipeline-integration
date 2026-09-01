from fastapi import APIRouter

from app.api.v1.auth import router as auth_router
from app.api.v1.documents import router as documents_router
from app.api.v1.topics import router as topics_router


router = APIRouter() #top-level API router used to collect versioned feature routers
router.include_router(auth_router)
router.include_router(documents_router)
router.include_router(topics_router)
