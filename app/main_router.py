from aiogram import Router
from app.main_menu import main_menu_router
from app.admin_menu import admin_menu_router
from app.bug_report.router import router as bug_report_router
from app.road_map.router import router as road_map_router
from app.attendances.router import router as attendances_router
from app.kill_log.router import router as kill_log_router
from app.schedule.router import router as schedule_router

router = Router()


router.include_router(main_menu_router)
router.include_router(admin_menu_router)
router.include_router(bug_report_router)
router.include_router(road_map_router)
router.include_router(attendances_router)
router.include_router(kill_log_router)
router.include_router(schedule_router)
