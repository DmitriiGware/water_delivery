from __future__ import annotations

import csv
from pathlib import Path
from uuid import uuid4

from database.models import DeliveryPoint, LoadOperation, ShiftRecord, TruckSettings
from utils.time_utils import moscow_now


def build_shift_record(
    truck: TruckSettings,
    work_date: str,
    started_at: str,
    loads: list[LoadOperation],
    delivery_points: list[DeliveryPoint],
    total_km: float,
    remaining_volume: float,
) -> ShiftRecord:
    loaded_total = round(sum(item.volume for item in loads), 2)
    delivered_fact_total = round(sum(item.fact_volume for item in delivery_points), 2)
    delivered_doc_total = round(sum(item.doc_volume for item in delivery_points), 2)
    savings_total = round(sum(item.savings_volume for item in delivery_points), 2)

    return ShiftRecord(
        shift_id=uuid4().hex[:10],
        truck_code=truck.code,
        truck_name=truck.name,
        driver_name=truck.driver_name,
        work_date=work_date,
        started_at=started_at,
        finished_at=moscow_now().isoformat(timespec="seconds"),
        loaded_total=loaded_total,
        delivered_fact_total=delivered_fact_total,
        delivered_doc_total=delivered_doc_total,
        remaining_volume=round(remaining_volume, 2),
        savings_total=savings_total,
        total_km=round(total_km, 2),
        loads=loads,
        delivery_points=delivery_points,
    )


def export_shift_to_csv(shift: ShiftRecord, base_dir: Path | None = None) -> Path:
    root = base_dir or Path(__file__).resolve().parents[1]
    reports_dir = root / "exports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    report_path = reports_dir / f"{shift.work_date}_{shift.truck_code}_{shift.shift_id}.csv"
    with report_path.open("w", newline="", encoding="utf-8-sig") as csvfile:
        writer = csv.writer(csvfile, delimiter=";")

        writer.writerow(["Дата", shift.work_date])
        writer.writerow(["Машина", shift.truck_name])
        writer.writerow(["Водитель", shift.driver_name])
        writer.writerow(["ID смены", shift.shift_id])
        writer.writerow([])

        writer.writerow(["Показатель", "Значение"])
        writer.writerow(["Всего закачано, куб", shift.loaded_total])
        writer.writerow(["Слито по факту, куб", shift.delivered_fact_total])
        writer.writerow(["Слито по документам, куб", shift.delivered_doc_total])
        writer.writerow(["Экономия, куб", shift.savings_total])
        writer.writerow(["Остаток воды, куб", shift.remaining_volume])
        writer.writerow(["Пробег, км", shift.total_km])
        writer.writerow([])

        writer.writerow(["Закачки"])
        writer.writerow(["#", "Кубы", "Время"])
        for index, load in enumerate(shift.loads, start=1):
            writer.writerow([index, load.volume, load.created_at])

        writer.writerow([])
        writer.writerow(["Точки доставки"])
        writer.writerow(["#", "Факт, куб", "Документы, куб", "Экономия, куб", "Время"])
        for point in shift.delivery_points:
            writer.writerow(
                [
                    point.point_number,
                    point.fact_volume,
                    point.doc_volume,
                    point.savings_volume,
                    point.created_at,
                ]
            )

    return report_path
