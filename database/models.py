from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from utils.time_utils import moscow_now


@dataclass(slots=True)
class TruckSettings:
    code: str
    name: str
    driver_name: str


@dataclass(slots=True)
class LoadOperation:
    volume: float
    created_at: str = field(default_factory=lambda: moscow_now().isoformat(timespec="seconds"))


@dataclass(slots=True)
class DeliveryPoint:
    point_number: int
    fact_volume: float
    doc_volume: float
    savings_volume: float
    created_at: str = field(default_factory=lambda: moscow_now().isoformat(timespec="seconds"))


@dataclass(slots=True)
class ShiftRecord:
    shift_id: str
    truck_code: str
    truck_name: str
    driver_name: str
    work_date: str
    started_at: str
    finished_at: str
    loaded_total: float
    delivered_fact_total: float
    delivered_doc_total: float
    remaining_volume: float
    savings_total: float
    total_km: float
    loads: list[LoadOperation]
    delivery_points: list[DeliveryPoint]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
