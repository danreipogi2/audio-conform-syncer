from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class JobLogEvent:
    timestamp: str
    level: str
    message: str
    details: dict[str, Any] = field(default_factory=dict)


def append_job_log(
    job_root: Path,
    level: str,
    message: str,
    details: dict[str, Any] | None = None,
) -> JobLogEvent:
    event = JobLogEvent(
        timestamp=datetime.now(timezone.utc).isoformat(),
        level=level,
        message=message,
        details=details or {},
    )
    log_path = job_root / "job_log.jsonl"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as file:
        file.write(json.dumps(asdict(event), ensure_ascii=False) + "\n")
    return event


def read_job_log(job_root: Path) -> list[JobLogEvent]:
    log_path = job_root / "job_log.jsonl"
    if not log_path.exists():
        return []

    events: list[JobLogEvent] = []
    for line in log_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        events.append(
            JobLogEvent(
                timestamp=str(item.get("timestamp", "")),
                level=str(item.get("level", "info")),
                message=str(item.get("message", "")),
                details=dict(item.get("details") or {}),
            )
        )
    return events


def job_logs_to_dicts(events: list[JobLogEvent]) -> list[dict[str, Any]]:
    return [asdict(event) for event in events]
