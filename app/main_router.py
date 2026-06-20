from aiogram import Router
from app.main_menu import main_menu_router
from app.bug_report.router import router as bug_report_router
from app.info.router import router as info_router

router = Router()


router.include_router(main_menu_router)
router.include_router(bug_report_router)
router.include_router(info_router)
