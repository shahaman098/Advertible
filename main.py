from pathlib import Path
import os

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from object_replacement.router import router as object_replacement_router
from object_replacement_rendering.router import router as object_replacement_rendering_router
from scene_rendering.router import router as scene_rendering_router
from scene_segmentation.router import router as scene_segmentation_router

load_dotenv(dotenv_path=Path(__file__).resolve().parent / ".env")


app = FastAPI(
    title="Scene Editing Backend",
    version="0.1.0",
    description="Backend with scene detection and async product replacement endpoints.",
)

allowed_origins = [
    origin.strip()
    for origin in os.getenv("ALLOWED_ORIGINS", "*").split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins or ["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", include_in_schema=False)
def root() -> RedirectResponse:
    return RedirectResponse(url="/frontend/")


@app.get("/health")
def healthcheck() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(scene_segmentation_router, prefix="/api")
app.include_router(scene_rendering_router, prefix="/api")
app.include_router(object_replacement_router, prefix="/api")
app.include_router(object_replacement_rendering_router, prefix="/api")
app.mount(
    "/frontend",
    StaticFiles(directory=Path(__file__).resolve().parent / "frontend", html=True),
    name="frontend",
)
