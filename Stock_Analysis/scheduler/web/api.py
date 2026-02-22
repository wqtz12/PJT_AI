"""
═══════════════════════════════════════════════════════════════
  REST API Endpoints
  - 워치리스트 CRUD, 수동 실행, 이력 조회, 상태 확인
═══════════════════════════════════════════════════════════════
"""
import logging
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import Optional

logger = logging.getLogger("scheduler.web.api")


class WatchlistCreate(BaseModel):
    name: str
    tickers: list[str]
    schedule: str = "09:00"
    analysis_type: str = "full"
    notifications: list[str] = ["file"]
    enabled: bool = True


class WatchlistUpdate(BaseModel):
    tickers: Optional[list[str]] = None
    schedule: Optional[str] = None
    analysis_type: Optional[str] = None
    notifications: Optional[list[str]] = None
    enabled: Optional[bool] = None


def create_api_router() -> APIRouter:
    """API 라우터 생성"""
    router = APIRouter(prefix="/api", tags=["API"])

    def _get_scheduler(request: Request):
        scheduler = request.app.state.scheduler
        if not scheduler:
            raise HTTPException(status_code=503, detail="스케줄러 미초기화")
        return scheduler

    @router.get("/status")
    async def get_status(request: Request):
        """스케줄러 상태"""
        scheduler = _get_scheduler(request)
        return scheduler.get_status()

    @router.get("/watchlists")
    async def list_watchlists(request: Request):
        """워치리스트 목록"""
        scheduler = _get_scheduler(request)
        return scheduler.get_watchlists()

    @router.post("/watchlists")
    async def create_watchlist(request: Request, data: WatchlistCreate):
        """워치리스트 생성"""
        scheduler = _get_scheduler(request)
        watchlists = scheduler.get_watchlists()

        if data.name in watchlists:
            raise HTTPException(status_code=409,
                                detail=f"워치리스트 '{data.name}' 이미 존재")

        wl_config = {
            "tickers": data.tickers,
            "schedule": data.schedule,
            "analysis_type": data.analysis_type,
            "notifications": data.notifications,
            "enabled": data.enabled,
        }
        scheduler.update_watchlist(data.name, wl_config)
        return {"status": "created", "name": data.name}

    @router.put("/watchlists/{name}")
    async def update_watchlist(request: Request, name: str, data: WatchlistUpdate):
        """워치리스트 수정"""
        scheduler = _get_scheduler(request)
        watchlists = scheduler.get_watchlists()

        if name not in watchlists:
            raise HTTPException(status_code=404,
                                detail=f"워치리스트 '{name}' 없음")

        wl_config = watchlists[name]
        if data.tickers is not None:
            wl_config["tickers"] = data.tickers
        if data.schedule is not None:
            wl_config["schedule"] = data.schedule
        if data.analysis_type is not None:
            wl_config["analysis_type"] = data.analysis_type
        if data.notifications is not None:
            wl_config["notifications"] = data.notifications
        if data.enabled is not None:
            wl_config["enabled"] = data.enabled

        scheduler.update_watchlist(name, wl_config)
        return {"status": "updated", "name": name}

    @router.delete("/watchlists/{name}")
    async def delete_watchlist(request: Request, name: str):
        """워치리스트 삭제"""
        scheduler = _get_scheduler(request)
        watchlists = scheduler.get_watchlists()

        if name not in watchlists:
            raise HTTPException(status_code=404,
                                detail=f"워치리스트 '{name}' 없음")

        scheduler.delete_watchlist(name)
        return {"status": "deleted", "name": name}

    @router.post("/run/{watchlist_name}")
    async def manual_run(request: Request, watchlist_name: str):
        """수동 분석 실행"""
        scheduler = _get_scheduler(request)
        result = scheduler.manual_run(watchlist_name)
        if "error" in result:
            raise HTTPException(status_code=404, detail=result["error"])
        return result

    @router.get("/history")
    async def get_history(request: Request,
                           watchlist: str = None,
                           ticker: str = None,
                           limit: int = 50,
                           offset: int = 0):
        """분석 이력 조회"""
        scheduler = _get_scheduler(request)
        if watchlist:
            batches = scheduler.history_db.get_batch_history(
                watchlist_name=watchlist, limit=limit)
        else:
            batches = scheduler.history_db.get_batch_history(limit=limit)

        return {"history": batches}

    @router.get("/history/{run_id}")
    async def get_run_details(request: Request, run_id: str):
        """특정 실행의 상세 결과"""
        scheduler = _get_scheduler(request)
        details = scheduler.history_db.get_run_details(run_id)
        if not details:
            raise HTTPException(status_code=404, detail="실행 기록 없음")
        return {"run_id": run_id, "details": details}

    @router.post("/settings/test/{channel}")
    async def test_notification(request: Request, channel: str):
        """알림 채널 테스트"""
        scheduler = _get_scheduler(request)
        notifications_config = scheduler.config.get("notifications", {})
        channel_config = notifications_config.get(channel, {})

        if not channel_config:
            raise HTTPException(status_code=404,
                                detail=f"알림 채널 '{channel}' 설정 없음")

        try:
            from scheduler.notifiers import create_notifier
            notifier = create_notifier(channel, channel_config)
            success, message = notifier.test_connection()
            return {"channel": channel, "success": success, "message": message}
        except Exception as e:
            return {"channel": channel, "success": False, "message": str(e)}

    @router.post("/config/reload")
    async def reload_config(request: Request):
        """설정 재로드"""
        scheduler = _get_scheduler(request)
        scheduler.reload_config()
        return {"status": "reloaded"}

    return router
