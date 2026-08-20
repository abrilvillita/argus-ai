from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from . import db
from .anomaly import engine
from .demo import run_demo_seed
from .models import OPERATORS, RuleIn, TelemetryIn

app = FastAPI(title="Argus AI", description="No-code IoT anomaly detection & auto-remediation")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class ConnectionManager:
    def __init__(self) -> None:
        self.active: list[WebSocket] = []

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self.active.append(ws)

    def disconnect(self, ws: WebSocket) -> None:
        if ws in self.active:
            self.active.remove(ws)

    async def broadcast(self, payload: dict) -> None:
        dead = []
        for ws in self.active:
            try:
                await ws.send_text(json.dumps(payload))
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)


manager = ConnectionManager()


async def ingest_reading(device_id: str, metric: str, value: float) -> dict:
    ts = db.insert_telemetry(device_id, metric, value)
    await manager.broadcast(
        {"type": "telemetry", "device_id": device_id, "metric": metric, "value": value, "created_at": ts}
    )

    anomaly = engine.observe(device_id, metric, value)
    triggered_alerts = []

    if anomaly is not None:
        alert = db.insert_alert(
            device_id, metric, value,
            source=anomaly["source"], message=anomaly["message"], action_taken="notify",
        )
        triggered_alerts.append(alert)

    for rule in db.list_rules():
        if not rule["enabled"]:
            continue
        if rule["device_id"] not in ("*", device_id):
            continue
        if rule["metric"] != metric:
            continue
        op = OPERATORS[rule["operator"]]
        if op(value, rule["threshold"]):
            alert = db.insert_alert(
                device_id, metric, value,
                source=f"rule:{rule['name']}",
                message=f"Rule '{rule['name']}' matched: {metric} {rule['operator']} {rule['threshold']}",
                action_taken=rule["action"],
            )
            triggered_alerts.append(alert)

    for alert in triggered_alerts:
        await manager.broadcast({"type": "alert", **alert})

    return {"ok": True, "anomaly": anomaly is not None, "alerts_triggered": len(triggered_alerts)}


@app.on_event("startup")
async def on_startup() -> None:
    db.init_db()
    if not db.list_rules():
        db.create_rule("Furnace overheat", "furnace-01", "temperature", "gt", 65, "shutdown_device")
    if os.environ.get("ARGUS_DEMO_SEED", "1") != "0":
        asyncio.create_task(run_demo_seed(ingest_reading))


@app.post("/api/telemetry")
async def post_telemetry(reading: TelemetryIn):
    return await ingest_reading(reading.device_id, reading.metric, reading.value)


@app.get("/api/devices")
def get_devices():
    return db.list_devices()


@app.get("/api/telemetry/{device_id}/{metric}")
def get_telemetry(device_id: str, metric: str, limit: int = 200):
    return db.recent_telemetry(device_id, metric, limit)


@app.get("/api/alerts")
def get_alerts(limit: int = 100):
    return db.list_alerts(limit)


@app.post("/api/rules")
def post_rule(rule: RuleIn):
    return db.create_rule(rule.name, rule.device_id, rule.metric, rule.operator, rule.threshold, rule.action)


@app.get("/api/rules")
def get_rules():
    return db.list_rules()


@app.delete("/api/rules/{rule_id}")
def remove_rule(rule_id: int):
    db.delete_rule(rule_id)
    return {"ok": True}


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await manager.connect(ws)
    try:
        while True:
            await asyncio.sleep(3600)
    except WebSocketDisconnect:
        manager.disconnect(ws)


FRONTEND_DIR = Path(__file__).resolve().parent.parent.parent / "frontend"
if FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
