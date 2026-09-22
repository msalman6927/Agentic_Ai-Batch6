from typing import Any

from fastapi import HTTPException, status


def next_id(records: dict[int, dict[str, Any]]) -> int:
    return max(records, default=0) + 1


def get_record(
    records: dict[int, dict[str, Any]],
    record_id: int,
    resource_name: str,
) -> dict[str, Any]:
    record = records.get(record_id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{resource_name} with id {record_id} was not found",
        )
    return record


def delete_record(
    records: dict[int, dict[str, Any]],
    record_id: int,
    resource_name: str,
) -> dict[str, Any]:
    get_record(records, record_id, resource_name)
    return records.pop(record_id)
