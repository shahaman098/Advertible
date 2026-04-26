from fastapi import APIRouter

from .schemas import SceneSegmentationRequest, SceneSegmentationResponse
from .service import run_scene_segmentation


router = APIRouter(tags=["scene-segmentation"])


@router.post(
    "/scene-segmentation",
    response_model=SceneSegmentationResponse,
    summary="Scene segmentation with PySceneDetect",
)
def scene_segmentation(
    payload: SceneSegmentationRequest,
) -> SceneSegmentationResponse:
    return run_scene_segmentation(payload)
