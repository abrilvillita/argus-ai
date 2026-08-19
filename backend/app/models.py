from typing import Literal

from pydantic import BaseModel, Field

Operator = Literal["gt", "lt", "gte", "lte", "eq"]
Action = Literal["notify", "throttle_device", "shutdown_device", "dispatch_technician"]


class TelemetryIn(BaseModel):
    device_id: str = Field(min_length=1, max_length=64)
    metric: str = Field(min_length=1, max_length=32)
    value: float


class RuleIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    device_id: str = Field(default="*", max_length=64)
    metric: str = Field(min_length=1, max_length=32)
    operator: Operator
    threshold: float
    action: Action


OPERATORS = {
    "gt": lambda v, t: v > t,
    "lt": lambda v, t: v < t,
    "gte": lambda v, t: v >= t,
    "lte": lambda v, t: v <= t,
    "eq": lambda v, t: v == t,
}
