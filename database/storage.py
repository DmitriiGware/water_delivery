from __future__ import annotations

import json
from pathlib import Path

from database.models import ShiftRecord


class JsonStorage:
    def __init__(self, base_path: Path | None = None) -> None:
        root = base_path or Path(__file__).resolve().parent
        self.data_dir = root / "data"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.shifts_path = self.data_dir / "shifts.json"
        if not self.shifts_path.exists():
            self.shifts_path.write_text("[]", encoding="utf-8")

    def save_shift(self, shift: ShiftRecord) -> None:
        records = self.load_shifts()
        records.append(shift.to_dict())
        self.shifts_path.write_text(
            json.dumps(records, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def load_shifts(self) -> list[dict]:
        return json.loads(self.shifts_path.read_text(encoding="utf-8"))
