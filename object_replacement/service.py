from __future__ import annotations

import base64
import os
import shutil
import socket
import time
from datetime import datetime, timezone
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Optional
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import urlopen
from uuid import uuid4

import cv2
import fal_client
from fastapi import HTTPException
from pydantic import ValidationError

from object_replacement_rendering.storage import job_upload_dir, read_job, write_job

from .schemas import (
    ObjectReplacementJob,
    ObjectReplacementRequest,
)

ANCHOR_FRAME_ENDPOINT = "openai/gpt-image-2/edit"
PIXVERSE_SWAP_ENDPOINT = "fal-ai/pixverse/swap"
MAX_SOURCE_VIDEO_SECONDS = 30.0
IMAGE_URL_PATHS = (
    ("image", "url"),
    ("images", 0, "url"),
    ("image_url",),
    ("data", "image", "url"),
    ("data", "images", 0, "url"),
    ("output", "image", "url"),
    ("output", "images", 0, "url"),
)

VIDEO_URL_PATHS = (
    ("video", "url"),
    ("videos", 0, "url"),
    ("video_url",),
    ("data", "video", "url"),
    ("data", "videos", 0, "url"),
    ("output", "video", "url"),
    ("output", "videos", 0, "url"),
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def ensure_fal_configured() -> None:
    if not os.getenv("FAL_KEY"):
        raise HTTPException(
            status_code=503,
            detail="FAL_KEY is not configured for the object replacement pipeline.",
        )


def create_object_replacement_job(
    payload: ObjectReplacementRequest,
) -> ObjectReplacementJob:
    ensure_fal_configured()

    return _create_job(
        source_video_reference=str(payload.source_video_url),
        reference_image_reference=str(payload.reference_image_url),
        anchor_prompt=payload.anchor_prompt,
        motion_prompt=payload.motion_prompt,
        pixverse_mode=payload.pixverse_mode,
        pixverse_keyframe_id=payload.pixverse_keyframe_id,
        pixverse_resolution=payload.pixverse_resolution,
        pixverse_seed=payload.pixverse_seed,
        preserve_original_audio=payload.preserve_original_audio,
    )


def create_uploaded_object_replacement_job(
    *,
    source_video_url: Optional[str],
    reference_image_url: Optional[str],
    anchor_prompt: str,
    motion_prompt: str,
    pixverse_mode: str = "object",
    pixverse_keyframe_id: int = 1,
    pixverse_resolution: str = "720p",
    pixverse_seed: Optional[int] = None,
    preserve_original_audio: bool = True,
    source_video_filename: Optional[str] = None,
    reference_image_filename: Optional[str] = None,
) -> ObjectReplacementJob:
    ensure_fal_configured()

    normalized_source_video_url = _validate_optional_url(
        source_video_url,
        field_name="source_video_url",
    )
    normalized_reference_image_url = _validate_optional_url(
        reference_image_url,
        field_name="reference_image_url",
    )

    if not normalized_source_video_url and not source_video_filename:
        raise HTTPException(
            status_code=422,
            detail="Provide either source_video_url or source_video_file.",
        )

    if not normalized_reference_image_url and not reference_image_filename:
        raise HTTPException(
            status_code=422,
            detail="Provide either reference_image_url or reference_image_file.",
        )

    source_video_reference = (
        f"uploaded://{source_video_filename}"
        if source_video_filename
        else normalized_source_video_url
    )
    reference_image_reference = (
        f"uploaded://{reference_image_filename}"
        if reference_image_filename
        else normalized_reference_image_url
    )

    return _create_job(
        source_video_reference=source_video_reference,
        reference_image_reference=reference_image_reference,
        anchor_prompt=anchor_prompt,
        motion_prompt=motion_prompt,
        pixverse_mode=pixverse_mode,
        pixverse_keyframe_id=pixverse_keyframe_id,
        pixverse_resolution=pixverse_resolution,
        pixverse_seed=pixverse_seed,
        preserve_original_audio=preserve_original_audio,
    )


def store_uploaded_asset(job_id: str, slot: str, filename: str, file_handle) -> Path:
    upload_dir = job_upload_dir(job_id)
    suffix = Path(filename).suffix or ""
    destination = upload_dir / f"{slot}{suffix}"
    with destination.open("wb") as output_file:
        shutil.copyfileobj(file_handle, output_file)
    return destination


def _create_job(
    *,
    source_video_reference: str,
    reference_image_reference: str,
    anchor_prompt: str,
    motion_prompt: str,
    pixverse_mode: str,
    pixverse_keyframe_id: int,
    pixverse_resolution: str,
    pixverse_seed: Optional[int],
    preserve_original_audio: bool,
) -> ObjectReplacementJob:
    created_at = _now()
    job_id = f"replace-{uuid4().hex[:12]}"
    job = ObjectReplacementJob(
        job_id=job_id,
        status="queued",
        current_stage="queued",
        created_at=created_at,
        updated_at=created_at,
        source_video_url=source_video_reference,
        reference_image_url=reference_image_reference,
        anchor_prompt=anchor_prompt,
        motion_prompt=motion_prompt,
        pixverse_mode=pixverse_mode,
        pixverse_keyframe_id=pixverse_keyframe_id,
        pixverse_resolution=pixverse_resolution,
        pixverse_seed=pixverse_seed,
        preserve_original_audio=preserve_original_audio,
        status_path=f"/api/object-replacement-rendering/{job_id}",
        result_path=f"/api/object-replacement-rendering/{job_id}",
    )
    return write_job(job)


def run_object_replacement_job(job_id: str) -> None:
    job = read_job(job_id)
    first_frame_path: Optional[Path] = None
    video_path: Optional[Path] = None
    uploaded_source_video_path = _find_uploaded_asset(job.job_id, "source_video")
    uploaded_reference_image_path = _find_uploaded_asset(job.job_id, "reference_image")
    downloaded_source_video = uploaded_source_video_path is None

    try:
        _update_job_status(job, status="running", current_stage="extracting_first_frame")
        reference_image_url = job.reference_image_url

        if uploaded_source_video_path is not None:
            video_path = uploaded_source_video_path
        else:
            video_path = _download_file(job.source_video_url)

        _validate_pixverse_source_duration(video_path)

        first_frame_path = _extract_first_frame(video_path)

        if uploaded_reference_image_path is not None:
            reference_image_url = _file_to_data_uri(uploaded_reference_image_path)

        first_frame_url = _file_to_data_uri(first_frame_path)
        job.artifacts.first_frame_url = first_frame_url
        write_job(job)

        if uploaded_source_video_path is not None:
            source_video_remote_url = _upload_local_asset(uploaded_source_video_path)
        else:
            source_video_remote_url = job.source_video_url

        # Stage 1: GPT Image 2 — synthesise the anchor frame by editing the
        # first frame using the reference product image as visual context.
        _mark_stage_running(job, "anchor_frame", "creating_anchor_frame")
        anchor_request_id, anchor_result = _submit_and_wait(
            ANCHOR_FRAME_ENDPOINT,
            {
                "image_urls": [first_frame_url, reference_image_url],
                "prompt": job.anchor_prompt,
                "quality": "high",
                "output_format": "png",
            },
        )
        anchor_frame_url = _extract_url(anchor_result, IMAGE_URL_PATHS, "anchor frame")
        _mark_stage_completed(job, "anchor_frame", anchor_request_id, anchor_frame_url)
        job.artifacts.anchor_frame_url = anchor_frame_url
        write_job(job)

        # Stage 2: PixVerse Swap — targeted person/object/background swap.
        _mark_stage_running(job, "pixverse_swap", "swapping_video")
        pixverse_request_id, output_video_url = _pixverse_swap(
            video_url=source_video_remote_url,
            image_url=reference_image_url,
            mode=job.pixverse_mode,
            keyframe_id=job.pixverse_keyframe_id,
            resolution=job.pixverse_resolution,
            seed=job.pixverse_seed,
            preserve_original_audio=job.preserve_original_audio,
        )
        _mark_stage_completed(job, "pixverse_swap", pixverse_request_id, output_video_url)
        job.artifacts.output_video_url = output_video_url
        write_job(job)

        _update_job_status(job, status="completed", current_stage="completed", error=None)
    except (
        HTTPError,
        URLError,
        OSError,
        ValueError,
        RuntimeError,
        TimeoutError,
        fal_client.FalClientError,
    ) as exc:
        _mark_job_failed(job, str(exc))
    finally:
        if downloaded_source_video and video_path is not None:
            video_path.unlink(missing_ok=True)
        if first_frame_path is not None:
            first_frame_path.unlink(missing_ok=True)


def _update_job_status(
    job: ObjectReplacementJob,
    *,
    status: str,
    current_stage: str,
    error: str | None = None,
) -> None:
    job.status = status
    job.current_stage = current_stage
    job.updated_at = _now()
    job.error = error
    write_job(job)


def _mark_stage_running(
    job: ObjectReplacementJob,
    stage_name: str,
    current_stage: str,
) -> None:
    stage = getattr(job, stage_name)
    stage.status = "running"
    stage.started_at = _now()
    stage.completed_at = None
    stage.error = None
    stage.output_url = None
    _update_job_status(job, status="running", current_stage=current_stage, error=None)


def _mark_stage_completed(
    job: ObjectReplacementJob,
    stage_name: str,
    request_id: str,
    output_url: str,
) -> None:
    stage = getattr(job, stage_name)
    stage.status = "completed"
    stage.request_id = request_id
    stage.completed_at = _now()
    stage.output_url = output_url
    stage.error = None
    job.updated_at = _now()
    write_job(job)


def _mark_stage_failed(
    job: ObjectReplacementJob,
    stage_name: str,
    error: str,
) -> None:
    stage = getattr(job, stage_name)
    stage.status = "failed"
    stage.completed_at = _now()
    stage.error = error
    job.updated_at = _now()
    write_job(job)


def _mark_job_failed(job: ObjectReplacementJob, error: str) -> None:
    stage_name = _stage_name_for_current_stage(job.current_stage)
    if stage_name is not None:
        stage = getattr(job, stage_name)
        stage.status = "failed"
        stage.completed_at = _now()
        stage.error = error

    _update_job_status(job, status="failed", current_stage="failed", error=error)


def _stage_name_for_current_stage(current_stage: str) -> str | None:
    if current_stage == "creating_anchor_frame":
        return "anchor_frame"
    if current_stage == "swapping_video":
        return "pixverse_swap"
    return None


def _pixverse_swap(
    *,
    video_url: str,
    image_url: str,
    mode: str,
    keyframe_id: int,
    resolution: str,
    seed: Optional[int] = None,
    preserve_original_audio: bool = True,
) -> tuple[str, str]:
    arguments: dict = {
        "video_url": video_url,
        "image_url": image_url,
        "mode": mode,
        "keyframe_id": keyframe_id,
        "resolution": resolution,
        "original_sound_switch": preserve_original_audio,
    }
    if seed is not None:
        arguments["seed"] = seed

    request_id, result = _submit_and_wait(PIXVERSE_SWAP_ENDPOINT, arguments)
    return request_id, _extract_url(result, VIDEO_URL_PATHS, "PixVerse output video")


def _submit_and_wait(application: str, arguments: dict) -> tuple[str, object]:
    handle = fal_client.submit(application, arguments)
    deadline = time.monotonic() + 1800

    while True:
        status = fal_client.status(application, handle.request_id, with_logs=True)
        if isinstance(status, fal_client.Completed):
            if status.error:
                raise RuntimeError(f"{application} failed: {status.error}")
            return handle.request_id, fal_client.result(application, handle.request_id)

        if time.monotonic() >= deadline:
            raise TimeoutError(f"{application} timed out before completion.")

        time.sleep(5)


def _download_file(source_url: str) -> Path:
    suffix = Path(urlparse(source_url).path).suffix or ".bin"
    with NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
        temp_path = Path(temp_file.name)

    try:
        with urlopen(source_url, timeout=60) as response, temp_path.open("wb") as output_file:
            shutil.copyfileobj(response, output_file)
    except (HTTPError, URLError, socket.timeout) as exc:
        temp_path.unlink(missing_ok=True)
        raise RuntimeError(f"Unable to download asset from {source_url}.") from exc

    return temp_path


def _validate_optional_url(value: Optional[str], *, field_name: str) -> Optional[str]:
    if value is None:
        return None

    normalized = value.strip()
    if not normalized:
        return None

    try:
        payload = ObjectReplacementRequest.model_validate(
            {
                field_name: normalized,
                "source_video_url": (
                    normalized if field_name == "source_video_url" else "https://example.com/video.mp4"
                ),
                "reference_image_url": (
                    normalized
                    if field_name == "reference_image_url"
                    else "https://example.com/reference.png"
                ),
                "anchor_prompt": "placeholder",
                "motion_prompt": "placeholder",
            }
        )
    except ValidationError as exc:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid {field_name}.",
        ) from exc

    return str(getattr(payload, field_name))


def _find_uploaded_asset(job_id: str, slot: str) -> Optional[Path]:
    matches = sorted(job_upload_dir(job_id).glob(f"{slot}.*"))
    if not matches:
        return None
    return matches[0]


def _file_to_data_uri(path: Path) -> str:
    """Read a local file and return it as a base64-encoded data URI.

    This avoids uploading to fal's Google Cloud Storage bucket, which
    requires outbound access to googleapis.com.
    """
    suffix = path.suffix.lower()
    mime_map = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
        ".gif": "image/gif",
    }
    mime = mime_map.get(suffix, "application/octet-stream")
    data = base64.b64encode(path.read_bytes()).decode()
    return f"data:{mime};base64,{data}"


def _upload_local_asset(path: Path) -> str:
    return fal_client.upload_file(path)


def _get_video_duration_seconds(video_path: Path) -> float:
    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        capture.release()
        raise RuntimeError("Unable to open the source video to inspect its duration.")

    fps = capture.get(cv2.CAP_PROP_FPS) or 0.0
    frame_count = capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0.0
    capture.release()

    if fps <= 0:
        raise RuntimeError("Unable to determine the source video frame rate.")

    return frame_count / fps


def _validate_pixverse_source_duration(video_path: Path) -> None:
    duration = _get_video_duration_seconds(video_path)
    if duration <= MAX_SOURCE_VIDEO_SECONDS:
        return

    raise ValueError(
        "PixVerse Swap is currently limited to short-to-medium source clips in this "
        f"pipeline. Your video is {duration:.2f}s, but the supported maximum is "
        f"{MAX_SOURCE_VIDEO_SECONDS:.0f}s. Please manually crop/export a shorter "
        "clip and submit that to keep processing predictable."
    )


def _extract_first_frame(video_path: Path) -> Path:
    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        capture.release()
        raise RuntimeError("Unable to open the source video for frame extraction.")

    ok, frame = capture.read()
    capture.release()
    if not ok:
        raise RuntimeError("Unable to read the first frame from the source video.")

    with NamedTemporaryFile(delete=False, suffix=".png") as temp_file:
        frame_path = Path(temp_file.name)

    if not cv2.imwrite(str(frame_path), frame):
        frame_path.unlink(missing_ok=True)
        raise RuntimeError("Unable to write the extracted first frame to disk.")

    return frame_path


def _extract_url(result: object, candidate_paths: tuple[tuple[object, ...], ...], label: str) -> str:
    for path in candidate_paths:
        value = _resolve_path(result, path)
        if isinstance(value, str) and value:
            return value

    raise ValueError(f"Could not find {label} URL in FAL response: {result}")


def _resolve_path(value: object, path: tuple[object, ...]) -> object | None:
    current = value
    for part in path:
        if isinstance(part, int):
            if not isinstance(current, list) or part >= len(current):
                return None
            current = current[part]
            continue

        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]

    return current
