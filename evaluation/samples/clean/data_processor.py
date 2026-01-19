from typing import Dict, List, Any, Optional
from dataclasses import dataclass


@dataclass
class ProcessedRecord:
    id: str
    value: float
    is_valid: bool


def process_records(records: List[Dict[str, Any]]) -> List[ProcessedRecord]:
    results = []
    for record in records:
        processed = ProcessedRecord(
            id=str(record.get("id", "")),
            value=float(record.get("value", 0)),
            is_valid=record.get("status") == "active",
        )
        results.append(processed)
    return results


def filter_valid_records(records: List[ProcessedRecord]) -> List[ProcessedRecord]:
    return [r for r in records if r.is_valid and r.value > 0]
