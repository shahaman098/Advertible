const form = document.getElementById("job-form");
const submitButton = document.getElementById("submit-button");
const refreshLatestButton = document.getElementById("refresh-latest");
const message = document.getElementById("message");
const jobSummary = document.getElementById("job-summary");
const artifacts = document.getElementById("artifacts");
const jobJson = document.getElementById("job-json");

const jobIdField = document.getElementById("job-id");
const jobStatusField = document.getElementById("job-status");
const jobStageField = document.getElementById("job-stage");
const jobUpdatedField = document.getElementById("job-updated");
const anchorStatusField = document.getElementById("anchor-status");
const pixverseStatusField = document.getElementById("pixverse-status");

const API_BASE = `${window.location.origin}/api`;
let pollHandle = null;

function setMessage(text, isError = false) {
  message.textContent = text;
  message.classList.toggle("error", isError);
}

function renderArtifacts(job) {
  const links = [
    ["First frame", job.artifacts?.first_frame_url],
    ["Anchor frame (GPT Image 2)", job.artifacts?.anchor_frame_url],
    ["Output video (PixVerse Swap)", job.artifacts?.output_video_url],
  ].filter(([, url]) => Boolean(url));

  if (links.length === 0) {
    artifacts.classList.add("hidden");
    artifacts.innerHTML = "";
    return;
  }

  artifacts.classList.remove("hidden");
  artifacts.innerHTML = links
    .map(
      ([label, url]) =>
        `<a href="${url}" target="_blank" rel="noreferrer">${label}: ${url}</a>`,
    )
    .join("");
}

function renderJob(job) {
  jobSummary.classList.remove("hidden");
  jobIdField.textContent = job.job_id;
  jobStatusField.textContent = job.status;
  jobStageField.textContent = job.current_stage;
  jobUpdatedField.textContent = new Date(job.updated_at).toLocaleString();
  anchorStatusField.textContent = job.anchor_frame?.status ?? "pending";
  pixverseStatusField.textContent = job.pixverse_swap?.status ?? "pending";
  jobJson.textContent = JSON.stringify(job, null, 2);
  renderArtifacts(job);

  if (job.error) {
    setMessage(job.error, true);
  } else {
    setMessage(`Job ${job.job_id} is ${job.status}.`);
  }
}

async function fetchJson(url, options = {}) {
  const response = await fetch(url, options);
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = data.detail ?? `Request failed with status ${response.status}.`;
    throw new Error(detail);
  }
  return data;
}

async function pollJob(jobId) {
  if (pollHandle) clearInterval(pollHandle);

  const refresh = async () => {
    try {
      const job = await fetchJson(`${API_BASE}/object-replacement-rendering/${jobId}`);
      renderJob(job);
      if (job.status === "completed" || job.status === "failed") {
        clearInterval(pollHandle);
        pollHandle = null;
      }
    } catch (error) {
      clearInterval(pollHandle);
      pollHandle = null;
      setMessage(error.message, true);
    }
  };

  await refresh();
  pollHandle = setInterval(refresh, 4000);
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  submitButton.disabled = true;
  setMessage("Submitting job...");

  const formData = new FormData();
  const sourceVideoUrl = form.source_video_url.value.trim();
  const referenceImageUrl = form.reference_image_url.value.trim();
  const sourceVideoFile = form.source_video_file.files[0];
  const referenceImageFile = form.reference_image_file.files[0];

  if (!sourceVideoUrl && !sourceVideoFile) {
    setMessage("Provide a source video URL or upload a source video file.", true);
    submitButton.disabled = false;
    return;
  }

  if (!referenceImageUrl && !referenceImageFile) {
    setMessage("Provide a reference image URL or upload a reference image file.", true);
    submitButton.disabled = false;
    return;
  }

  if (sourceVideoUrl) formData.append("source_video_url", sourceVideoUrl);
  if (referenceImageUrl) formData.append("reference_image_url", referenceImageUrl);
  if (sourceVideoFile) formData.append("source_video_file", sourceVideoFile);
  if (referenceImageFile) formData.append("reference_image_file", referenceImageFile);
  formData.append("anchor_prompt", form.anchor_prompt.value.trim());
  formData.append("pixverse_mode", form.pixverse_mode.value);
  formData.append("pixverse_keyframe_id", form.pixverse_keyframe_id.value);
  formData.append("pixverse_resolution", form.pixverse_resolution.value);
  formData.append("preserve_original_audio", form.preserve_original_audio.checked ? "true" : "false");
  if (form.pixverse_seed.value.trim()) {
    formData.append("pixverse_seed", form.pixverse_seed.value.trim());
  }

  try {
    const job = await fetchJson(`${API_BASE}/object-replacement/upload`, {
      method: "POST",
      body: formData,
    });
    renderJob(job);
    setMessage(`Job ${job.job_id} created. Polling for updates...`);
    await pollJob(job.job_id);
  } catch (error) {
    setMessage(error.message, true);
  } finally {
    submitButton.disabled = false;
  }
});

refreshLatestButton.addEventListener("click", async () => {
  try {
    setMessage("Loading latest job...");
    const job = await fetchJson(`${API_BASE}/object-replacement-rendering/latest`);
    renderJob(job);
    if (job.status !== "completed" && job.status !== "failed") {
      await pollJob(job.job_id);
    }
  } catch (error) {
    setMessage(error.message, true);
  }
});
