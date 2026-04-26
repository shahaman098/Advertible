import json
from pathlib import Path

from object_replacement.schemas import ObjectReplacementJob


STORAGE_ROOT = Path(__file__).resolve().parent
JOBS_DIR = STORAGE_ROOT / "jobs"
LATEST_JSON_PATH = STORAGE_ROOT / "latest.json"
UPLOADS_DIR = STORAGE_ROOT / "uploads"


def write_job(job: ObjectReplacementJob) -> ObjectReplacementJob:
    JOBS_DIR.mkdir(parents=True, exist_ok=True)
    job_path(job.job_id).write_text(
        json.dumps(job.model_dump(mode="json"), indent=2),
        encoding="utf-8",
    )
    LATEST_JSON_PATH.write_text(
        json.dumps(job.model_dump(mode="json"), indent=2),
        encoding="utf-8",
    )
    return job


def read_job(job_id: str) -> ObjectReplacementJob:
    path = job_path(job_id)
    if not path.exists():
        raise FileNotFoundError(path)

    return ObjectReplacementJob.model_validate_json(path.read_text(encoding="utf-8"))


def read_latest_job() -> ObjectReplacementJob:
    if not LATEST_JSON_PATH.exists():
        raise FileNotFoundError(LATEST_JSON_PATH)

    return ObjectReplacementJob.model_validate_json(
        LATEST_JSON_PATH.read_text(encoding="utf-8"),
    )


def job_path(job_id: str) -> Path:
    return JOBS_DIR / f"{job_id}.json"


def job_upload_dir(job_id: str) -> Path:
    path = UPLOADS_DIR / job_id
    path.mkdir(parents=True, exist_ok=True)
    return path
