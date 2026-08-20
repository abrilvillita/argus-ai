"""
Built-in demo telemetry generator.

Runs as a background asyncio task so a freshly deployed instance (e.g. the
public Render demo) is never a blank dashboard -- it seeds itself with a
synthetic IoT fleet and periodically injects anomalies, the same way
`simulator/simulate.py` does standalone. Disable with ARGUS_DEMO_SEED=0.
"""

from __future__ import annotations

import asyncio
import math
import random

DEVICES = ["furnace-01", "chiller-02", "pump-03"]
BASELINES = {
    "temperature": {"mean": 42.0, "std": 1.5},
    "humidity": {"mean": 38.0, "std": 3.0},
    "vibration": {"mean": 0.8, "std": 0.15},
}


def _reading(t: float, metric: str, device_index: int, anomaly: bool) -> float:
    base = BASELINES[metric]
    phase = device_index * 0.6
    drift = math.sin(t / 20 + phase) * base["std"]
    noise = random.gauss(0, base["std"] * 0.4)
    value = base["mean"] + drift + noise
    if anomaly:
        value += random.choice([-1, 1]) * base["mean"] * random.uniform(0.6, 1.4)
    return round(value, 3)


async def run_demo_seed(ingest) -> None:
    """`ingest` is an async callable(device_id, metric, value) -> None."""
    t = 0.0
    while True:
        anomaly_tick = random.random() < 0.06
        for i, device_id in enumerate(DEVICES):
            for metric in BASELINES:
                value = _reading(t, metric, i, anomaly=anomaly_tick and random.random() < 0.5)
                await ingest(device_id, metric, value)
        t += 1.5
        await asyncio.sleep(1.5)
