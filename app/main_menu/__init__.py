from .router import router as main_menu_router
from .channel_registration import router as registration_router

main_menu_router.include_router(registration_router)