"""FastAPI backend: REST API + WebSocket live feed + static dashboard.

Also runs the background scoring worker as an asyncio task: it picks up jobs
with status 'new', scores them (respecting the kill switch), and pushes live
events to connected dashboards.
"""
from __future__ import annotations

import asyncio
import contextlib
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import config, db, killswitch, matcher, notify, resume_parser

app = FastAPI(title="Job Application Copilot")


# ── WebSocket hub ─────────────────────────────────────────────────────────

class Hub:
    def __init__(self) -> None:
        self._clients: set[WebSocket] = set()
        self._loop: asyncio.AbstractEventLoop | None = None

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self._clients.add(ws)

    def disconnect(self, ws: WebSocket) -> None:
        self._clients.discard(ws)

    async def broadcast(self, event: dict[str, Any]) -> None:
        dead = []
        for ws in list(self._clients):
            try:
                await ws.send_json(event)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)


hub = Hub()


# ── Request models ────────────────────────────────────────────────────────

class JobIn(BaseModel):
    title: str = ""
    company: str = ""
    location: str = ""
    url: str = ""
    description: str = ""
    source: str = "manual"


class ProfileIn(BaseModel):
    profile: dict[str, Any]


# ── Background scoring worker ─────────────────────────────────────────────

async def scoring_worker() -> None:
    """Continuously score 'new' jobs unless the kill switch is engaged."""
    while True:
        try:
            if killswitch.is_active():
                await asyncio.sleep(3)
                continue
            job = await asyncio.to_thread(db.next_unscored)
            if job is None:
                await asyncio.sleep(4)
                continue
            scored = await asyncio.to_thread(matcher.score_and_store, job)
            if scored:
                await hub.broadcast({"type": "job_scored", "job": scored})
                if scored["status"] == "scored":
                    notify.send(
                        f"✅ Match {scored['score']}%: {scored['title']} @ {scored['company']}"
                    )
        except Exception as exc:  # keep the worker alive
            await hub.broadcast({"type": "error", "message": str(exc)})
            await asyncio.sleep(5)


@app.on_event("startup")
async def _startup() -> None:
    config.ensure_dirs()
    db.init_db()
    app.state.worker = asyncio.create_task(scoring_worker())


@app.on_event("shutdown")
async def _shutdown() -> None:
    task = getattr(app.state, "worker", None)
    if task:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task


# ── REST API ──────────────────────────────────────────────────────────────

@app.get("/api/jobs")
def api_jobs(status: str | None = None) -> dict[str, Any]:
    return {"jobs": db.list_jobs(status=status)}


@app.get("/api/stats")
def api_stats() -> dict[str, Any]:
    s = db.stats()
    s["kill_switch"] = killswitch.is_active()
    s["llm"] = __import__("jobcopilot.llm", fromlist=["available"]).available()
    return s


@app.post("/api/jobs")
async def api_add_job(job: JobIn) -> dict[str, Any]:
    created = db.add_job(**job.model_dump())
    await hub.broadcast({"type": "job_added", "job": created})
    return created


@app.post("/api/rescore/{job_id}")
async def api_rescore(job_id: int) -> dict[str, Any]:
    job = db.get_job(job_id)
    if not job:
        return {"error": "not found"}
    db.set_status(job_id, "new")  # requeue; worker will pick it up
    await hub.broadcast({"type": "job_requeued", "job": db.get_job(job_id)})
    return {"ok": True}


@app.post("/api/approve/{job_id}")
async def api_approve(job_id: int) -> dict[str, Any]:
    job = db.set_status(job_id, "applied")
    await hub.broadcast({"type": "job_updated", "job": job})
    if job:
        notify.send(f"📮 Marked applied: {job['title']} @ {job['company']}")
    return job or {"error": "not found"}


@app.post("/api/reject/{job_id}")
async def api_reject(job_id: int) -> dict[str, Any]:
    job = db.set_status(job_id, "skipped")
    await hub.broadcast({"type": "job_updated", "job": job})
    return job or {"error": "not found"}


@app.delete("/api/jobs/{job_id}")
async def api_delete(job_id: int) -> dict[str, Any]:
    db.delete_job(job_id)
    await hub.broadcast({"type": "job_deleted", "job_id": job_id})
    return {"ok": True}


@app.post("/api/kill")
async def api_kill() -> dict[str, Any]:
    killswitch.engage()
    await hub.broadcast({"type": "kill_switch", "active": True})
    notify.send("🛑 Copilot paused (kill switch engaged).")
    return {"kill_switch": True}


@app.post("/api/resume")
async def api_resume() -> dict[str, Any]:
    killswitch.release()
    await hub.broadcast({"type": "kill_switch", "active": False})
    return {"kill_switch": False}


@app.get("/api/profile")
def api_get_profile() -> dict[str, Any]:
    return config.load_profile()


@app.put("/api/profile")
def api_put_profile(body: ProfileIn) -> dict[str, Any]:
    merged = config.load_profile()
    merged.update(body.profile)
    config.save_profile(merged)
    return merged


@app.get("/api/resume")
def api_resume_info() -> dict[str, Any]:
    r = resume_parser.load_cached()
    return {
        "source": r.get("_source", "none"),
        "skills": r.get("skills", []),
        "years_experience": r.get("years_experience"),
        "summary": r.get("summary", ""),
    }


@app.websocket("/ws/live")
async def ws_live(ws: WebSocket) -> None:
    await hub.connect(ws)
    try:
        # Send an initial snapshot so a freshly-opened dashboard is populated.
        await ws.send_json({"type": "snapshot", "jobs": db.list_jobs(),
                            "stats": db.stats(), "kill_switch": killswitch.is_active()})
        while True:
            await ws.receive_text()  # keepalive; we ignore client messages
    except WebSocketDisconnect:
        hub.disconnect(ws)
    except Exception:
        hub.disconnect(ws)


# Static dashboard (mounted last so /api and /ws take priority).
app.mount("/", StaticFiles(directory=str(config.STATIC_DIR), html=True), name="static")
