from fastapi import APIRouter, HTTPException

from scene_segmentation.schemas import SceneSegmentationResponse

from .storage import read_scenes_payload


router = APIRouter(tags=["scene-rendering"])


@router.get(
    "/scene-rendering",
    response_model=SceneSegmentationResponse,
    summary="Render the latest scenes.json payload",
)
def render_scene_segmentation() -> SceneSegmentationResponse:
    try:
        return read_scenes_payload()
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail="No scenes.json output is available yet.",
        ) from exc
