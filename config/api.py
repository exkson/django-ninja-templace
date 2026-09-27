from ninja import NinjaAPI

from web.admin.users import router as admin_users_router
from web.exc_handlers import setup_handlers
from web.views.auth import router as auth_router
from web.views.users import router as users_router

api = NinjaAPI()
setup_handlers(api)
api.add_router("auth", auth_router)
api.add_router("users", users_router)
api.add_router("admin", admin_users_router)
