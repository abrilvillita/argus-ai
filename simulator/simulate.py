"""
Synthetic IoT fleet simulator for Argus AI.

Streams temperature / humidity / vibration readings for a handful of
virtual devices to the backend's REST API, occasionally injecting spikes
so the anomaly engine and any no-code rules you've defined have something
real to catch. Point BACKEND_URL at a local or deployed instance.

Usage:
    python simulate.py --backend http://localhost:8000 --devices 4 --interval 1
"""

from __future__ import annotations

import argparse
import math
import random
import time

import httpx

DEVICES = ["furnace-01", "chiller-02", "pump-03", "conveyor-04", "compressor-05"]

BASELINES = {
    "temperature": {"mean": 42.0, "std": 1.5},
    "humidity": {"mean": 38.0, "std": 3.0},
    "vibration": {"mean": 0.8, "std": 0.15},
}


def reading(t: float, metric: str, device_index: int, anomaly: bool) -> float:
    base = BASELINES[metric]
    phase = device_index * 0.6
    drift = math.sin(t / 20 + phase) * base["std"]
    noise = random.gauss(0, base["std"] * 0.4)
    value = base["mean"] + drift + noise
    if anomaly:
        value += random.choice([-1, 1]) * base["mean"] * random.uniform(0.6, 1.4)
    return round(value, 3)


def run(backend: str, num_devices: int, interval: float, anomaly_chance: float) -> None:
    devices = DEVICES[:num_devices]
    print(f"Argus AI simulator -> {backend}  devices={devices}  interval={interval}s")
    with httpx.Client(timeout=5.0) as client:
        t = 0.0
        while True:
            for i, device_id in enumerate(devices):
                is_anomalous_tick = random.random() < anomaly_chance
                for metric in BASELINES:
                    value = reading(t, metric, i, anomaly=is_anomalous_tick and random.random() < 0.5)
                    try:
                        resp = client.post(
                            f"{backend}/api/telemetry",
                            json={"device_id": device_id, "metric": metric, "value": value},
                        )
                        tag = " <-- injected anomaly" if is_anomalous_tick else ""
                        print(f"{device_id:14s} {metric:11s} {value:8.2f}{tag}")
                        if resp.json().get("alerts_triggered"):
                            print(f"   !! alert(s) triggered for {device_id}/{metric}")
                    except httpx.HTTPError as exc:
                        print(f"  send failed: {exc}")
            t += interval
            time.sleep(interval)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--backend", default="http://localhost:8000")
    parser.add_argument("--devices", type=int, default=4)
    parser.add_argument("--interval", type=float, default=1.0)
    parser.add_argument("--anomaly-chance", type=float, default=0.08)
    args = parser.parse_args()
    run(args.backend, args.devices, args.interval, args.anomaly_chance)
