import shutil
import socket
from datetime import datetime, timezone
from pathlib import Path
from tempfile import NamedTemporaryFile
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import urlopen

from fastapi import HTTPException
from scenedetect import ContentDetector, detect, open_video

from scene_rendering.storage import write_scenes_payload

from .schemas import SceneSegment, SceneSegmentationRequest, SceneSegmentationResponse


def _download_video(source_url: str) -> Path:
    suffix = Path(urlparse(source_url).path).suffix or ".mp4"
    with NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
        temp_path = Path(temp_file.name)

    try:
        with urlopen(source_url, timeout=60) as response, temp_path.open("wb") as output_file:
            shutil.copyfileobj(response, output_file)
    except (HTTPError, URLError, socket.timeout) as exc:
        temp_path.unlink(missing_ok=True)
        raise HTTPException(
            status_code=400,
            detail=f"Unable to download video from {source_url}.",
        ) from exc

    return temp_path


def run_scene_segmentation(payload: SceneSegmentationRequest) -> SceneSegmentationResponse:
    video_path = _download_video(str(payload.video_url))
    try:
        video = open_video(str(video_path))
        scene_list = detect(
            str(video_path),
            ContentDetector(threshold=payload.threshold),
        )
    except (OSError, ValueError) as exc:
        raise HTTPException(
            status_code=422,
            detail="The supplied video could not be processed by PySceneDetect.",
        ) from exc
    finally:
        video_path.unlink(missing_ok=True)

    if scene_list:
        scenes = [
            SceneSegment(
                scene_number=index,
                start_timecode=start_time.get_timecode(),
                end_timecode=end_time.get_timecode(),
                start_seconds=round(start_time.get_seconds(), 3),
                end_seconds=round(end_time.get_seconds(), 3),
                duration_seconds=round(end_time.get_seconds() - start_time.get_seconds(), 3),
            )
            for index, (start_time, end_time) in enumerate(scene_list, start=1)
        ]
    else:
        duration = video.duration
        scenes = [
            SceneSegment(
                scene_number=1,
                start_timecode=video.base_timecode.get_timecode(),
                end_timecode=duration.get_timecode(),
                start_seconds=0.0,
                end_seconds=round(duration.get_seconds(), 3),
                duration_seconds=round(duration.get_seconds(), 3),
            )
        ]

    response = SceneSegmentationResponse(
        generated_at=datetime.now(timezone.utc),
        status="completed",
        source_video_url=str(payload.video_url),
        threshold=payload.threshold,
        scenes_json_path="/api/scene-rendering",
        scene_count=len(scenes),
        scenes=scenes,
    )

    return write_scenes_payload(response)
