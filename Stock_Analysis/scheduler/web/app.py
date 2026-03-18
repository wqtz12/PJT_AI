"""
═══════════════════════════════════════════════════════════════
  FastAPI Web Application
  - 스케줄러 대시보드, 워치리스트 관리, 이력 조회
  - Jinja2 템플릿 + htmx 동적 업데이트
═══════════════════════════════════════════════════════════════
"""
import os
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse

from scheduler.web.api import create_api_router

_WEB_DIR = os.path.dirname(os.path.abspath(__file__))
_TEMPLATES_DIR = os.path.join(_WEB_DIR, "templates")
_STATIC_DIR = os.path.join(_WEB_DIR, "static")

templates = Jinja2Templates(directory=_TEMPLATES_DIR)


def create_app(scheduler_instance=None) -> FastAPI:
    """FastAPI 앱 생성 (스케줄러 인스턴스 주입)"""
    app = FastAPI(
        title="Stock Analysis Scheduler",
        description="주식 분석 스케줄러 관리 UI",
        version="1.0.0",
    )

    # 스케줄러 인스턴스 저장
    app.state.scheduler = scheduler_instance

    # 정적 파일 마운트
    os.makedirs(_STATIC_DIR, exist_ok=True)
    app.mount("/static", StaticFiles(directory=_STATIC_DIR), name="static")

    # API 라우터 등록
    api_router = create_api_router()
    app.include_router(api_router)

    # ─── 페이지 라우트 ───

    @app.get("/", response_class=HTMLResponse)
    async def dashboard(request: Request):
        """메인 대시보드"""
        scheduler = request.app.state.scheduler
        ctx = {"request": request, "page": "dashboard"}

        if scheduler:
            ctx["status"] = scheduler.get_status()
            ctx["watchlists"] = scheduler.get_watchlists()

            # 각 워치리스트의 최근 실행 정보
            latest_runs = {}
            for name in ctx["watchlists"]:
                latest = scheduler.history_db.get_latest_run(name)
                if latest:
                    latest_runs[name] = latest
            ctx["latest_runs"] = latest_runs
        else:
            ctx["status"] = {"running": False, "jobs": [], "current_jobs": {}, "stats": {}}
            ctx["watchlists"] = {}
            ctx["latest_runs"] = {}

        return templates.TemplateResponse("dashboard.html", ctx)

    @app.get("/watchlists", response_class=HTMLResponse)
    async def watchlists_page(request: Request):
        """워치리스트 관리"""
        scheduler = request.app.state.scheduler
        ctx = {"request": request, "page": "watchlists"}

        if scheduler:
            ctx["watchlists"] = scheduler.get_watchlists()
        else:
            ctx["watchlists"] = {}

        return templates.TemplateResponse("watchlists.html", ctx)

    @app.get("/history", response_class=HTMLResponse)
    async def history_page(request: Request):
        """분석 이력"""
        scheduler = request.app.state.scheduler
        ctx = {"request": request, "page": "history"}

        if scheduler:
            ctx["batch_history"] = scheduler.history_db.get_batch_history(limit=30)
            ctx["watchlists"] = list(scheduler.get_watchlists().keys())
        else:
            ctx["batch_history"] = []
            ctx["watchlists"] = []

        return templates.TemplateResponse("history.html", ctx)

    @app.get("/settings", response_class=HTMLResponse)
    async def settings_page(request: Request):
        """알림 설정"""
        scheduler = request.app.state.scheduler
        ctx = {"request": request, "page": "settings"}

        if scheduler:
            ctx["notifications"] = scheduler.config.get("notifications", {})
            ctx["scheduler_config"] = scheduler.config.get("scheduler", {})
        else:
            ctx["notifications"] = {}
            ctx["scheduler_config"] = {}

        return templates.TemplateResponse("settings.html", ctx)

    # ─── htmx 파셜 라우트 ───

    @app.get("/partials/run-status/{watchlist_name}", response_class=HTMLResponse)
    async def run_status_partial(request: Request, watchlist_name: str):
        """실행 상태 파셜 (htmx polling)"""
        scheduler = request.app.state.scheduler
        status = {}
        if scheduler:
            current = scheduler._current_jobs.get(watchlist_name, {})
            status = current

        return templates.TemplateResponse("partials/run_status.html", {
            "request": request,
            "watchlist_name": watchlist_name,
            "status": status,
        })

    @app.get("/partials/history-table", response_class=HTMLResponse)
    async def history_table_partial(request: Request,
                                     watchlist: str = None,
                                     limit: int = 20):
        """이력 테이블 파셜"""
        scheduler = request.app.state.scheduler
        history = []
        if scheduler:
            history = scheduler.history_db.get_batch_history(
                watchlist_name=watchlist if watchlist else None,
                limit=limit,
            )

        return templates.TemplateResponse("partials/history_table.html", {
            "request": request,
            "batch_history": history,
        })

    return app
