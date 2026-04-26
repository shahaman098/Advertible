from datetime import datetime

from pydantic import BaseModel, Field, HttpUrl


class SceneSegmentationRequest(BaseModel):
    video_url: HttpUrl = Field(..., description="Public URL to the input video.")
    threshold: float = Field(
        default=27.0,
        gt=0,
        description="PySceneDetect content threshold used to split scenes.",
    )


class SceneSegment(BaseModel):
    scene_number: int
    start_timecode: str
    end_timecode: str
    start_seconds: float
    end_seconds: float
    duration_seconds: float


class SceneSegmentationResponse(BaseModel):
    generated_at: datetime
    status: str
    source_video_url: str
    threshold: float
    scenes_json_path: str
    scene_count: int
    scenes: list[SceneSegment]
