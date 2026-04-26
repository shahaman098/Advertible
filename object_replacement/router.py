from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, UploadFile, status

from .schemas import (
    DEFAULT_ANCHOR_PROMPT,
    DEFAULT_MOTION_PROMPT,
    ObjectReplacementJob,
    ObjectReplacementRequest,
    PixverseMode,
    PixverseResolution,
)
from .service import (
    create_object_replacement_job,
    create_uploaded_object_replacement_job,
    run_object_replacement_job,
    store_uploaded_asset,
)


router = APIRouter(tags=["object-replacement"])

@router.post(
    "/object-replacement",
    response_model=ObjectReplacementJob,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Start async product replacement in a video scene",
)
def object_replacement(
    payload: ObjectReplacementRequest,
    background_tasks: BackgroundTasks,
) -> ObjectReplacementJob:
    job = create_object_replacement_job(payload)
    background_tasks.add_task(run_object_replacement_job, job.job_id)
    return job


@router.post(
    "/object-replacement/upload",
    response_model=ObjectReplacementJob,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Start async product replacement with uploaded assets",
)
def object_replacement_upload(
    background_tasks: BackgroundTasks,
    source_video_url: Optional[str] = Form(default=None),
    reference_image_url: Optional[str] = Form(default=None),
    source_video_file: Optional[UploadFile] = File(default=None),
    reference_image_file: Optional[UploadFile] = File(default=None),
    anchor_prompt: str = Form(default=DEFAULT_ANCHOR_PROMPT, min_length=1),
    motion_prompt: str = Form(default=DEFAULT_MOTION_PROMPT, min_length=1),
    pixverse_mode: PixverseMode = Form(default="object"),
    pixverse_keyframe_id: int = Form(default=1, ge=1),
    pixverse_resolution: PixverseResolution = Form(default="720p"),
    pixverse_seed: Optional[int] = Form(default=None, ge=0),
    preserve_original_audio: bool = Form(default=True),
) -> ObjectReplacementJob:
    if not source_video_url and source_video_file is None:
        raise HTTPException(
            status_code=422,
            detail="Provide either a source video URL or upload a source video file.",
        )

    if not reference_image_url and reference_image_file is None:
        raise HTTPException(
            status_code=422,
            detail="Provide either a reference image URL or upload a reference image file.",
        )

    job = create_uploaded_object_replacement_job(
        source_video_url=source_video_url,
        reference_image_url=reference_image_url,
        anchor_prompt=anchor_prompt.strip(),
        motion_prompt=motion_prompt.strip(),
        pixverse_mode=pixverse_mode,
        pixverse_keyframe_id=pixverse_keyframe_id,
        pixverse_resolution=pixverse_resolution,
        pixverse_seed=pixverse_seed,
        preserve_original_audio=preserve_original_audio,
        source_video_filename=(
            source_video_file.filename if source_video_file and source_video_file.filename else None
        ),
        reference_image_filename=(
            reference_image_file.filename
            if reference_image_file and reference_image_file.filename
            else None
        ),
    )

    if source_video_file and source_video_file.filename:
        store_uploaded_asset(
            job.job_id,
            "source_video",
            source_video_file.filename,
            source_video_file.file,
        )

    if reference_image_file and reference_image_file.filename:
        store_uploaded_asset(
            job.job_id,
            "reference_image",
            reference_image_file.filename,
            reference_image_file.file,
        )

    background_tasks.add_task(run_object_replacement_job, job.job_id)
    return job
