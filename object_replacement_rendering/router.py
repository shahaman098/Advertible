from fastapi import APIRouter, HTTPException

from object_replacement.schemas import ObjectReplacementJob

from .storage import read_job, read_latest_job


router = APIRouter(tags=["object-replacement-rendering"])


@router.get(
    "/object-replacement-rendering/latest",
    response_model=ObjectReplacementJob,
    summary="Render the latest object replacement job payload",
)
def render_latest_object_replacement() -> ObjectReplacementJob:
    try:
        return read_latest_job()
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail="No object replacement job output is available yet.",
        ) from exc


@router.get(
    "/object-replacement-rendering/{job_id}",
    response_model=ObjectReplacementJob,
    summary="Render a specific object replacement job payload",
)
def render_object_replacement_job(job_id: str) -> ObjectReplacementJob:
    try:
        return read_job(job_id)
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail=f"No object replacement job was found for '{job_id}'.",
        ) from exc
