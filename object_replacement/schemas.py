from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field, HttpUrl


DEFAULT_ANCHOR_PROMPT = (
    "Replace the original object with the product from the reference image. "
    "Match the scene lighting, reflections, contact shadows, scale, and perspective so the "
    "product looks naturally embedded in the shot. Do not relight, recolor, denoise, sharpen, "
    "stylize, add glow, add halos, smooth edges, or alter any person, background, camera texture, "
    "grain, exposure, shadows, or non-product pixels."
)

DEFAULT_MOTION_PROMPT = (
    "PixVerse Swap does not use a text motion prompt. Configure swap mode, keyframe, "
    "resolution, seed, and original audio instead."
)

PixverseMode = Literal["person", "object", "background"]
PixverseResolution = Literal["360p", "540p", "720p"]


class ObjectReplacementRequest(BaseModel):
    source_video_url: HttpUrl = Field(
        ...,
        description="Public URL to the source scene video.",
    )
    reference_image_url: HttpUrl = Field(
        ...,
        description="Public URL to the product reference image.",
    )
    anchor_prompt: str = Field(
        default=DEFAULT_ANCHOR_PROMPT,
        min_length=1,
        description="Prompt sent to GPT Image 2 Edit for the anchor frame.",
    )
    motion_prompt: str = Field(
        default=DEFAULT_MOTION_PROMPT,
        min_length=1,
        description="Deprecated compatibility field; PixVerse Swap does not use text prompts.",
    )
    pixverse_mode: PixverseMode = Field(
        default="object",
        description="PixVerse swap mode: person, object, or background.",
    )
    pixverse_keyframe_id: int = Field(
        default=1,
        ge=1,
        description="PixVerse keyframe ID at 24 FPS; 1 is the first frame.",
    )
    pixverse_resolution: PixverseResolution = Field(
        default="720p",
        description="PixVerse output resolution. 1080p is not supported by this endpoint.",
    )
    pixverse_seed: Optional[int] = Field(
        default=None,
        ge=0,
        description="Optional PixVerse seed for reproducible A/B testing.",
    )
    preserve_original_audio: bool = Field(
        default=True,
        description="Keep the original source video audio in PixVerse output.",
    )


class PipelineStage(BaseModel):
    status: Literal["pending", "running", "completed", "failed", "skipped"] = "pending"
    request_id: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    output_url: Optional[str] = None
    error: Optional[str] = None



class ReplacementArtifacts(BaseModel):
    first_frame_url: Optional[str] = None
    anchor_frame_url: Optional[str] = None
    output_video_url: Optional[str] = None


class ObjectReplacementJob(BaseModel):
    job_id: str
    status: Literal["queued", "running", "completed", "failed"]
    current_stage: str
    created_at: datetime
    updated_at: datetime
    source_video_url: str
    reference_image_url: str
    anchor_prompt: str
    motion_prompt: str
    pixverse_mode: PixverseMode = "object"
    pixverse_keyframe_id: int = 1
    pixverse_resolution: PixverseResolution = "720p"
    pixverse_seed: Optional[int] = None
    preserve_original_audio: bool = True
    status_path: str
    result_path: str
    artifacts: ReplacementArtifacts = Field(default_factory=ReplacementArtifacts)
    anchor_frame: PipelineStage = Field(default_factory=PipelineStage)
    pixverse_swap: PipelineStage = Field(default_factory=PipelineStage)
    error: Optional[str] = None
