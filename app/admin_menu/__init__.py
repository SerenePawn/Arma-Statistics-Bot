from .router import router as admin_menu_router
from .squad_name.router import router as squad_name_router
from .tags.router import router as tags_router
from .common import router as common_router
from .schedule.router import router as schedule_router


admin_menu_router.include_router(squad_name_router)
admin_menu_router.include_router(tags_router)
admin_menu_router.include_router(common_router)
admin_menu_router.include_router(schedule_router)
