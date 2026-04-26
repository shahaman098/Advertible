import json
from pathlib import Path

from scene_segmentation.schemas import SceneSegmentationResponse


SCENES_JSON_PATH = Path(__file__).resolve().parent / "scenes.json"


def write_scenes_payload(
    payload: SceneSegmentationResponse,
) -> SceneSegmentationResponse:
    SCENES_JSON_PATH.write_text(
        json.dumps(payload.model_dump(mode="json"), indent=2),
        encoding="utf-8",
    )
    return payload


def read_scenes_payload() -> SceneSegmentationResponse:
    if not SCENES_JSON_PATH.exists():
        raise FileNotFoundError(SCENES_JSON_PATH)

    return SceneSegmentationResponse.model_validate_json(
        SCENES_JSON_PATH.read_text(encoding="utf-8"),
    )
