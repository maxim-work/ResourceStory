from aiogram import Router

from .add import add_router
from .list import list_router
from .search import search_router

resource_router = Router()
resource_router.include_router(add_router)
resource_router.include_router(list_router)
resource_router.include_router(search_router)
