# Frontend Connection Guide: Render Backend

Use this guide to connect your frontend to the backend after deploying it on Render.

## 1. Render Deployment

Deploy this repository as a Render Blueprint using `render.yaml`, or create a Render Web Service manually.

Required Render environment variables:

| Key | Value |
| --- | --- |
| `FAL_KEY` | Your fal.ai API key. Used for GPT Image 2 Edit and PixVerse Swap. |
| `ALLOWED_ORIGINS` | Your frontend origin, for example `https://your-frontend.vercel.app` |
| `PYTHON_VERSION` | `3.11.9` |

Render settings if creating manually:

| Setting | Value |
| --- | --- |
| Environment | Python |
| Build Command | `pip install -r requirements.txt` |
| Start Command | `uvicorn main:app --host 0.0.0.0 --port $PORT` |
| Health Check Path | `/health` |

Backend base URL:

```text
https://YOUR-RENDER-SERVICE.onrender.com
```

API base URL:

```text
https://YOUR-RENDER-SERVICE.onrender.com/api
```

## 2. Frontend Environment Variable

Set this in your frontend app:

```text
VITE_API_BASE_URL=https://YOUR-RENDER-SERVICE.onrender.com/api
```

Use the equivalent variable name for your framework:

- Vite: `VITE_API_BASE_URL`
- Next.js browser client: `NEXT_PUBLIC_API_BASE_URL`
- Plain JavaScript: hardcode or inject the URL at build time

## 3. Health Check

```bash
curl https://YOUR-RENDER-SERVICE.onrender.com/health
```

Expected response:

```json
{"status":"ok"}
```

## 4. Pipeline Summary

```text
source video + reference image
→ extract first frame
→ GPT Image 2 Edit creates an anchor frame preview
→ PixVerse Swap replaces the selected person/object/background in the source video
→ poll job status until output_video_url is ready
```

PixVerse Swap receives the source video plus the original reference image. The GPT Image 2 anchor is kept as an artifact/preview so you can verify the visual target, but the video swap stage is handled by PixVerse.

## 5. Create Object Replacement Job

Endpoint:

```text
POST /api/object-replacement/upload
```

Full URL:

```text
https://YOUR-RENDER-SERVICE.onrender.com/api/object-replacement/upload
```

Submit as `multipart/form-data`.

Required input, choose one source video option:

- `source_video_url`, or
- `source_video_file`

Required input, choose one reference image option:

- `reference_image_url`, or
- `reference_image_file`

Optional fields:

| Field | Type | Default | Notes |
| --- | --- | --- | --- |
| `anchor_prompt` | string | Backend default | Sent to GPT Image 2 Edit for the anchor preview |
| `pixverse_mode` | `person`, `object`, or `background` | `object` | PixVerse target mode |
| `pixverse_keyframe_id` | integer >= 1 | `1` | PixVerse keyframe at 24 FPS; `1` is first frame, `24` is about 1 second |
| `pixverse_resolution` | `360p`, `540p`, or `720p` | `720p` | 1080p is not supported by this PixVerse endpoint |
| `pixverse_seed` | integer | empty | Optional reproducibility seed |
| `preserve_original_audio` | boolean string | `true` | Maps to PixVerse `original_sound_switch` |

Compatibility field:

| Field | Type | Notes |
| --- | --- | --- |
| `motion_prompt` | string | Accepted for older clients, but PixVerse Swap does not use text motion prompts |

Important constraints:

- This backend accepts source clips up to 30 seconds for infrastructure testing.
- PixVerse pricing is cheapest around 5-second clips; longer clips can cost more and take longer.
- If your frontend uploads a local video file, the backend uploads that video to fal storage so PixVerse can access it.
- If you pass a public `source_video_url`, the backend sends that URL directly to PixVerse after duration validation.

## 6. JavaScript Example

```js
const API_BASE = import.meta.env.VITE_API_BASE_URL;

async function createReplacementJob({
  sourceVideoFile,
  sourceVideoUrl,
  referenceImageFile,
  referenceImageUrl,
  anchorPrompt,
  pixverseMode = "object",
  pixverseKeyframeId = 1,
  pixverseResolution = "720p",
  pixverseSeed,
  preserveOriginalAudio = true,
}) {
  const formData = new FormData();

  if (sourceVideoFile) formData.append("source_video_file", sourceVideoFile);
  if (sourceVideoUrl) formData.append("source_video_url", sourceVideoUrl);
  if (referenceImageFile) formData.append("reference_image_file", referenceImageFile);
  if (referenceImageUrl) formData.append("reference_image_url", referenceImageUrl);
  if (anchorPrompt) formData.append("anchor_prompt", anchorPrompt);

  formData.append("pixverse_mode", pixverseMode);
  formData.append("pixverse_keyframe_id", String(pixverseKeyframeId));
  formData.append("pixverse_resolution", pixverseResolution);
  formData.append("preserve_original_audio", preserveOriginalAudio ? "true" : "false");
  if (pixverseSeed !== undefined && pixverseSeed !== null && pixverseSeed !== "") {
    formData.append("pixverse_seed", String(pixverseSeed));
  }

  const response = await fetch(`${API_BASE}/object-replacement/upload`, {
    method: "POST",
    body: formData,
  });

  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.detail || `Request failed with ${response.status}`);
  }

  return data;
}
```

## 7. Poll Job Status

The create response contains:

```json
{
  "job_id": "replace-abc123...",
  "status": "queued",
  "status_path": "/api/object-replacement-rendering/replace-abc123...",
  "result_path": "/api/object-replacement-rendering/replace-abc123..."
}
```

Poll this endpoint every 3-5 seconds:

```text
GET /api/object-replacement-rendering/{job_id}
```

JavaScript example:

```js
async function getJob(jobId) {
  const response = await fetch(`${API_BASE}/object-replacement-rendering/${jobId}`);
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.detail || `Request failed with ${response.status}`);
  }
  return data;
}

async function pollJob(jobId, onUpdate) {
  while (true) {
    const job = await getJob(jobId);
    onUpdate(job);

    if (job.status === "completed" || job.status === "failed") {
      return job;
    }

    await new Promise((resolve) => setTimeout(resolve, 4000));
  }
}
```

## 8. Output URLs

When complete, read:

```js
job.artifacts.first_frame_url;
job.artifacts.anchor_frame_url;
job.artifacts.output_video_url;
```

Display/download `job.artifacts.output_video_url` as the final PixVerse video.

Stage status fields:

```js
job.anchor_frame.status;
job.pixverse_swap.status;
```

## 9. CORS

For production, set Render `ALLOWED_ORIGINS` to your frontend URL, for example:

```text
https://your-frontend.vercel.app
```

For multiple frontends, comma-separate them:

```text
https://app.example.com,https://staging.example.com
```

During quick testing, `ALLOWED_ORIGINS=*` is allowed by the current backend config.

## 10. Common Errors

### `FAL_KEY is not configured`

Add `FAL_KEY` in Render environment variables and redeploy.

### Video duration error

Crop/export your source clip to 30 seconds or shorter, then resubmit.

### PixVerse keyframe error

PixVerse keyframes are normalized to 24 FPS. Use `1` for the first frame, `24` for about 1 second, `48` for about 2 seconds, etc. The keyframe must be within the clip duration.

### CORS error from frontend

Set Render `ALLOWED_ORIGINS` to your frontend origin and redeploy.

### Render free instance sleeps

The first request after inactivity can be slow. Use `/health` to warm it up before submitting a job.
