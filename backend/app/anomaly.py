"""
AI anomaly detection engine -- pure Python, zero heavy ML dependencies.

Two complementary streaming techniques, both fit online (no offline
training step, no model file to ship):

1. EWMA z-score       -- flags a single metric spiking away from its own
                          rolling baseline. Catches obvious single-sensor
                          faults immediately.
2. Online Mahalanobis -- flags a device's *combined* metrics drifting away
                          from their learned joint distribution using an
                          incrementally-updated mean vector and covariance
                          matrix (Welford's algorithm, generalized to the
                          multivariate case). Catches subtler cross-metric
                          anomalies a single threshold would miss -- e.g.
                          temperature and vibration rising together.

Keeping this dependency-free (no numpy/scipy/scikit-learn) matters in
practice: those wheels don't always exist for every interpreter/OS
combination, and even when they do, shipping compiled extensions to a
serverless function inflates cold-start time. This engine runs anywhere
a bare `python` interpreter runs.
"""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass, field

WINDOW = 50
ALPHA = 0.3  # EWMA smoothing factor
Z_THRESHOLD = 3.0
MAHALANOBIS_THRESHOLD = 5.5  # ~ chi-square 99.9th percentile for a few dims
MIN_SAMPLES_FOR_COV = 15


@dataclass
class _MetricState:
    values: deque = field(default_factory=lambda: deque(maxlen=WINDOW))
    ewma_mean: float | None = None
    ewma_var: float = 0.0


def _zeros(n: int) -> list[list[float]]:
    return [[0.0] * n for _ in range(n)]


def _mat_inv(m: list[list[float]]) -> list[list[float]] | None:
    """Gauss-Jordan inverse of a small square matrix. None if singular."""
    n = len(m)
    aug = [row[:] + [1.0 if i == j else 0.0 for j in range(n)] for i, row in enumerate(m)]
    for col in range(n):
        pivot_row = max(range(col, n), key=lambda r: abs(aug[r][col]))
        if abs(aug[pivot_row][col]) < 1e-9:
            return None
        aug[col], aug[pivot_row] = aug[pivot_row], aug[col]
        pivot = aug[col][col]
        aug[col] = [v / pivot for v in aug[col]]
        for r in range(n):
            if r == col:
                continue
            factor = aug[r][col]
            aug[r] = [v - factor * aug[col][i] for i, v in enumerate(aug[r])]
    return [row[n:] for row in aug]


COV_ALPHA = 0.1  # slower decay than the per-metric EWMA so it tolerates gentle joint drift


class _OnlineCovariance:
    """EWMA mean + covariance for a fixed, ordered set of metrics.

    Exponential decay (rather than an equally-weighted running average)
    matters here: real sensor baselines drift slowly over time, and a
    covariance estimate that treats a reading from an hour ago the same
    as one from a second ago will flag perfectly normal drift as an
    anomaly forever. Decaying old evidence lets the model's notion of
    "normal" move with the device.
    """

    def __init__(self, dims: list[str]) -> None:
        self.dims = dims
        n = len(dims)
        self.n = 0
        self.mean = [0.0] * n
        self.cov = _zeros(n)

    def update(self, vec: list[float]) -> None:
        self.n += 1
        if self.n == 1:
            self.mean = list(vec)
            return
        diff = [v - m for v, m in zip(vec, self.mean)]
        self.mean = [m + COV_ALPHA * d for m, d in zip(self.mean, diff)]
        for i in range(len(vec)):
            for j in range(len(vec)):
                self.cov[i][j] = (1 - COV_ALPHA) * (self.cov[i][j] + COV_ALPHA * diff[i] * diff[j])

    def mahalanobis(self, vec: list[float]) -> float | None:
        if self.n < MIN_SAMPLES_FOR_COV:
            return None
        n = len(self.dims)
        cov = [row[:] for row in self.cov]
        avg_var = max(sum(cov[i][i] for i in range(n)) / n, 1e-9)
        ridge = avg_var * 0.15
        for i in range(n):
            cov[i][i] += ridge
        inv = _mat_inv(cov)
        if inv is None:
            return None
        diff = [v - m for v, m in zip(vec, self.mean)]
        # diff^T * inv * diff
        tmp = [sum(diff[i] * inv[i][j] for i in range(n)) for j in range(n)]
        dist_sq = sum(tmp[j] * diff[j] for j in range(n))
        return dist_sq ** 0.5


class AnomalyEngine:
    def __init__(self) -> None:
        self._metric_state: dict[tuple[str, str], _MetricState] = defaultdict(_MetricState)
        self._device_latest: dict[str, dict[str, float]] = defaultdict(dict)
        self._device_dims: dict[str, list[str]] = {}
        self._device_cov: dict[str, _OnlineCovariance] = {}

    def observe(self, device_id: str, metric: str, value: float) -> dict | None:
        z_hit = self._ewma_zscore(device_id, metric, value)
        mv_hit = self._multivariate(device_id, metric, value)
        return z_hit or mv_hit

    def _ewma_zscore(self, device_id: str, metric: str, value: float) -> dict | None:
        state = self._metric_state[(device_id, metric)]
        state.values.append(value)

        if state.ewma_mean is None:
            state.ewma_mean = value
            state.ewma_var = 0.0
            return None

        prev_mean = state.ewma_mean
        diff = value - prev_mean
        state.ewma_mean += ALPHA * diff
        state.ewma_var = (1 - ALPHA) * (state.ewma_var + ALPHA * diff * diff)
        std = state.ewma_var ** 0.5

        if len(state.values) < 8 or std < 1e-6:
            return None

        z = abs(diff) / std
        if z > Z_THRESHOLD:
            return {
                "source": "ewma_zscore",
                "message": f"{metric} on {device_id} is {z:.1f}σ from its rolling baseline "
                           f"({value:.2f} vs expected ~{prev_mean:.2f})",
            }
        return None

    def _multivariate(self, device_id: str, metric: str, value: float) -> dict | None:
        dims = self._device_dims.setdefault(device_id, [])
        if metric not in dims:
            dims.append(metric)
        if len(dims) < 2:
            self._device_latest[device_id][metric] = value
            return None

        cov = self._device_cov.get(device_id)
        if cov is None or cov.dims != dims:
            cov = _OnlineCovariance(list(dims))
            self._device_cov[device_id] = cov

        latest = self._device_latest[device_id]
        latest[metric] = value
        if not all(d in latest for d in dims):
            return None

        vec = [latest[d] for d in dims]
        dist = cov.mahalanobis(vec)
        cov.update(vec)

        if dist is not None and dist > MAHALANOBIS_THRESHOLD:
            return {
                "source": "mahalanobis",
                "message": f"Multivariate anomaly on {device_id}: joint pattern of "
                           f"{', '.join(dims)} is {dist:.1f} std-equivalents from the device's "
                           f"learned normal envelope",
            }
        return None


engine = AnomalyEngine()
