const videoExtensions = new Set([
  ".3gp",
  ".avi",
  ".m4v",
  ".mkv",
  ".mov",
  ".mp4",
  ".mpeg",
  ".mpg",
  ".mts",
  ".mxf",
  ".webm",
]);

const audioExtensions = new Set([
  ".aac",
  ".aif",
  ".aiff",
  ".flac",
  ".m4a",
  ".mp3",
  ".ogg",
  ".wav",
  ".wave",
]);

const state = {
  files: [],
  busy: false,
};

const dropZone = document.querySelector("#dropZone");
const chooseFiles = document.querySelector("#chooseFiles");
const chooseFolder = document.querySelector("#chooseFolder");
const fileInput = document.querySelector("#fileInput");
const folderInput = document.querySelector("#folderInput");
const videoList = document.querySelector("#videoList");
const audioList = document.querySelector("#audioList");
const unsupportedList = document.querySelector("#unsupportedList");
const videoCount = document.querySelector("#videoCount");
const audioCount = document.querySelector("#audioCount");
const unsupportedCount = document.querySelector("#unsupportedCount");
const syncButton = document.querySelector("#syncButton");
const clearButton = document.querySelector("#clearButton");
const jobStatus = document.querySelector("#jobStatus");
const threshold = document.querySelector("#threshold");
const thresholdValue = document.querySelector("#thresholdValue");
const systemStatus = document.querySelector("#systemStatus");
const resultsPanel = document.querySelector("#resultsPanel");
const coverageMetric = document.querySelector("#coverageMetric");
const matchesMetric = document.querySelector("#matchesMetric");
const ambiguousMetric = document.querySelector("#ambiguousMetric");
const diagnostics = document.querySelector("#diagnostics");
const matchesBody = document.querySelector("#matchesBody");
const videoOutputLink = document.querySelector("#videoOutputLink");
const jsonOutputLink = document.querySelector("#jsonOutputLink");
const markdownOutputLink = document.querySelector("#markdownOutputLink");
const premiereXmlLink = document.querySelector("#premiereXmlLink");
const premiereXmlDisabled = document.querySelector("#premiereXmlDisabled");
const resolveXmlLink = document.querySelector("#resolveXmlLink");
const resolveXmlDisabled = document.querySelector("#resolveXmlDisabled");
const timelineDuration = document.querySelector("#timelineDuration");
const timelineWarnings = document.querySelector("#timelineWarnings");
const timelineScale = document.querySelector("#timelineScale");
const timelineLayers = document.querySelector("#timelineLayers");

threshold.addEventListener("input", () => {
  thresholdValue.value = Number(threshold.value).toFixed(2);
});

chooseFiles.addEventListener("click", () => fileInput.click());
chooseFolder.addEventListener("click", () => folderInput.click());
fileInput.addEventListener("change", () => addFiles(Array.from(fileInput.files)));
folderInput.addEventListener("change", () => addFiles(Array.from(folderInput.files)));
clearButton.addEventListener("click", clearWorkspace);
syncButton.addEventListener("click", runSync);

["dragenter", "dragover"].forEach((eventName) => {
  dropZone.addEventListener(eventName, (event) => {
    event.preventDefault();
    dropZone.classList.add("is-over");
  });
});

["dragleave", "drop"].forEach((eventName) => {
  dropZone.addEventListener(eventName, () => {
    dropZone.classList.remove("is-over");
  });
});

dropZone.addEventListener("drop", async (event) => {
  event.preventDefault();
  const files = await filesFromDrop(event.dataTransfer);
  addFiles(files);
});

dropZone.addEventListener("keydown", (event) => {
  if (event.key === "Enter" || event.key === " ") {
    event.preventDefault();
    fileInput.click();
  }
});

async function filesFromDrop(dataTransfer) {
  const items = Array.from(dataTransfer.items || []);
  const entryFiles = [];

  for (const item of items) {
    const entry = item.webkitGetAsEntry ? item.webkitGetAsEntry() : null;
    if (entry) {
      entryFiles.push(...(await filesFromEntry(entry)));
    }
  }

  return dedupeFiles([...entryFiles, ...Array.from(dataTransfer.files || [])]);
}

async function filesFromEntry(entry, prefix = "") {
  if (entry.isFile) {
    const file = await new Promise((resolve, reject) => entry.file(resolve, reject));
    file.relativePath = `${prefix}${file.name}`;
    return [file];
  }
  if (!entry.isDirectory) {
    return [];
  }

  const reader = entry.createReader();
  const entries = [];
  let batch = [];
  do {
    batch = await new Promise((resolve, reject) => reader.readEntries(resolve, reject));
    entries.push(...batch);
  } while (batch.length);

  const nested = await Promise.all(
    entries.map((child) => filesFromEntry(child, `${prefix}${entry.name}/`)),
  );
  return nested.flat();
}

function addFiles(files) {
  const next = files.map((file) => ({
      file,
      id: `${file.name}-${file.size}-${file.lastModified}-${crypto.randomUUID()}`,
      name: file.relativePath || file.webkitRelativePath || file.name,
      type: classifyFile(file),
    }));

  state.files.push(...next);
  render();
}

function classifyFile(file) {
  const suffix = extensionFor(file.name);
  if (videoExtensions.has(suffix) || file.type.startsWith("video/")) {
    return "video";
  }
  if (audioExtensions.has(suffix) || file.type.startsWith("audio/")) {
    return "audio";
  }
  return "unknown";
}

function extensionFor(name) {
  const index = name.lastIndexOf(".");
  return index >= 0 ? name.slice(index).toLowerCase() : "";
}

function render() {
  const videos = state.files.filter((item) => item.type === "video");
  const audio = state.files.filter((item) => item.type === "audio");
  const unsupported = state.files.filter((item) => item.type === "unknown");
  videoCount.textContent = videos.length;
  audioCount.textContent = audio.length;
  unsupportedCount.textContent = unsupported.length;
  renderList(videoList, videos, { selectedFirst: true });
  renderList(audioList, audio);
  renderList(unsupportedList, unsupported, { unsupported: true });

  syncButton.disabled = state.busy || videos.length < 1 || audio.length < 1;
  if (videos.length > 1) {
    setStatus("First video will be used", "");
  } else if (!state.busy && videos.length === 1 && audio.length >= 1) {
    setStatus("Ready", "");
  } else if (!state.busy) {
    setStatus("Ready", "");
  }
}

function renderList(container, items, options = {}) {
  container.replaceChildren();
  if (!items.length) {
    const empty = document.createElement("div");
    empty.className = "media-item";
    empty.innerHTML = "<strong>Empty</strong><span>0 files</span>";
    container.append(empty);
    return;
  }

  for (const [index, item] of items.entries()) {
    const element = document.createElement("div");
    element.className = `media-item ${options.unsupported ? "is-unsupported" : ""}`;
    const label = document.createElement("strong");
    label.textContent = item.name;
    const meta = document.createElement("span");
    if (options.selectedFirst && index === 0) {
      meta.textContent = `Selected | ${formatBytes(item.file.size)}`;
    } else if (options.selectedFirst) {
      meta.textContent = `Ignored extra video | ${formatBytes(item.file.size)}`;
    } else if (options.unsupported) {
      meta.textContent = "Unsupported";
    } else {
      meta.textContent = formatBytes(item.file.size);
    }
    element.append(label, meta);
    container.append(element);
  }
}

async function runSync() {
  const videos = state.files.filter((item) => item.type === "video");
  const audio = state.files.filter((item) => item.type === "audio");
  if (videos.length < 1 || !audio.length || state.busy) {
    return;
  }

  state.busy = true;
  render();
  setStatus("Synchronizing...", "");
  resultsPanel.hidden = true;

  const formData = new FormData();
  for (const item of [videos[0], ...audio]) {
    formData.append("files", item.file, item.name);
  }
  formData.append("threshold", threshold.value);
  formData.append("window_seconds", document.querySelector("#windowSeconds").value);
  formData.append("hop_seconds", document.querySelector("#hopSeconds").value);
  formData.append("minimum_score_margin", document.querySelector("#scoreMargin").value);

  try {
    const response = await fetch("/api/sync", {
      method: "POST",
      body: formData,
    });
    const payload = await response.json();
    if (!response.ok || !payload.ok) {
      throw new Error(payload.error || "Sync failed");
    }
    renderResults(payload);
    setStatus("Complete", "");
  } catch (error) {
    setStatus(error.message, "error");
  } finally {
    state.busy = false;
    render();
  }
}

function renderResults(payload) {
  const summary = payload.summary;
  const clientUnsupported = state.files.filter((item) => item.type === "unknown");
  const extraVideos = state.files.filter((item) => item.type === "video").slice(1);
  coverageMetric.textContent = `${Number(summary.coverage_percent).toFixed(1)}%`;
  matchesMetric.textContent = String(summary.match_count);
  ambiguousMetric.textContent = String(summary.ambiguous_match_count);

  const diagnosticItems = [
    ...payload.diagnostics,
    ...(payload.warnings || []).map((message) => ({ level: "warning", message })),
    ...extraVideos.map((item) => ({
      level: "warning",
      message: `Extra video not synced: ${item.name}`,
    })),
  ];
  const unsupportedTotal = (payload.unsupported || []).length + clientUnsupported.length;
  if (unsupportedTotal) {
    diagnosticItems.push({
      level: "warning",
      message: `${unsupportedTotal} unsupported file(s) were skipped.`,
    });
  }

  diagnostics.replaceChildren(
    ...diagnosticItems.map((note) => {
      const element = document.createElement("div");
      element.className = `diagnostic ${note.level}`;
      element.textContent = `${note.level}: ${note.message}`;
      return element;
    }),
  );

  matchesBody.replaceChildren(
    ...payload.matches.map((match) => {
      const row = document.createElement("tr");
      row.append(
        tableCell(formatRange(match.reference_start_seconds, match.reference_end_seconds)),
        tableCell(formatRange(match.source_start_seconds, match.source_end_seconds)),
        tableCell(Number(match.score).toFixed(3)),
        tableCell(match.confidence),
      );
      return row;
    }),
  );

  setLink(jsonOutputLink, payload.outputs.json);
  setLink(markdownOutputLink, payload.outputs.markdown);
  videoOutputLink.hidden = !payload.outputs.synced_video;
  videoOutputLink.href = payload.outputs.synced_video;
  setExportControl(
    premiereXmlLink,
    premiereXmlDisabled,
    payload.xml_exports.premiere,
    "Export Premiere XML",
  );
  setExportControl(
    resolveXmlLink,
    resolveXmlDisabled,
    payload.xml_exports.resolve,
    "Export DaVinci Resolve XML",
  );

  if (!payload.export.ok) {
    const element = document.createElement("div");
    element.className = "diagnostic warning";
    element.textContent = `export: ${payload.export.error}`;
    diagnostics.append(element);
  }

  renderTimeline(payload.timeline);
  resultsPanel.hidden = false;
}

function renderTimeline(timeline) {
  const duration = Math.max(Number(timeline.duration_seconds) || 0, 0.001);
  const extraVideos = state.files.filter((item) => item.type === "video").slice(1);
  const clientUnsupported = state.files.filter((item) => item.type === "unknown");
  const warnings = [
    ...(timeline.warnings || []),
    ...extraVideos.map((item) => `Extra video not synced: ${item.name}`),
    ...clientUnsupported.map((item) => `Unsupported file skipped: ${item.name}`),
  ];
  timelineDuration.textContent = formatSeconds(duration);
  timelineWarnings.replaceChildren(
    ...warnings.map((warning) => {
      const item = document.createElement("span");
      item.textContent = warning;
      return item;
    }),
  );

  timelineScale.replaceChildren(...buildScaleTicks(duration));
  timelineLayers.replaceChildren(
    renderTimelineTrack(timeline.video_track, duration, { video: true }),
    renderTimelineTrack(timeline.guide_audio_track, duration, { guide: true }),
    ...timeline.audio_tracks.map((track) => renderTimelineTrack(track, duration)),
  );
}

function renderTimelineTrack(track, duration, options = {}) {
  const row = document.createElement("div");
  row.className = `timeline-row ${track.status} ${options.video ? "video-row" : ""}`;

  const label = document.createElement("div");
  label.className = "timeline-label";
  const title = document.createElement("strong");
  title.textContent = track.name;
  const detail = document.createElement("span");
  if (options.video) {
    detail.textContent = "Flattened edit / reference video";
  } else if (options.guide) {
    detail.textContent = "Attached baked-in guide audio";
  } else {
    detail.textContent = track.status === "matched" ? "External audio" : "Unmatched external audio";
  }
  label.append(title, detail);

  const lane = document.createElement("div");
  lane.className = "timeline-lane";
  lane.append(renderWaveform(track.waveform_peaks));

  if (options.video) {
    const clip = document.createElement("div");
    clip.className = "timeline-clip reference-clip";
    clip.style.left = "0%";
    clip.style.width = "100%";
    clip.textContent = track.source_name;
    lane.append(clip);
  } else if (!track.clips.length) {
    const empty = document.createElement("div");
    empty.className = "unmatched-marker";
    empty.textContent = track.status === "reference" ? "Guide audio" : "No synced regions";
    lane.append(empty);
  } else {
    for (const clip of track.clips) {
      lane.append(renderTimelineClip(clip, duration));
    }
  }

  row.append(label, lane);
  return row;
}

function renderTimelineClip(clip, duration) {
  const element = document.createElement("div");
  element.className = `timeline-clip ${clip.low_confidence ? "low-confidence" : ""}`;
  const left = (Number(clip.timeline_in_seconds) / duration) * 100;
  const width = (Number(clip.duration_seconds) / duration) * 100;
  element.style.left = `${Math.max(0, Math.min(100, left))}%`;
  element.style.width = `${Math.max(1, Math.min(100, width))}%`;
  element.title = [
    clip.source_name,
    `Timeline: ${formatRange(clip.timeline_in_seconds, clip.timeline_out_seconds)}`,
    `Source: ${formatRange(clip.source_in_seconds, clip.source_out_seconds)}`,
    `Confidence: ${clip.confidence} (${Number(clip.score).toFixed(3)})`,
  ].join("\n");
  element.innerHTML = `
    <strong>${escapeHtml(clip.source_name)}</strong>
    <span>${formatRange(clip.timeline_in_seconds, clip.timeline_out_seconds)}</span>
    <small>${clip.confidence} | ${Number(clip.score).toFixed(3)}</small>
  `;
  return element;
}

function renderWaveform(peaks) {
  const waveform = document.createElement("div");
  waveform.className = "waveform";
  for (const peak of peaks || []) {
    const bar = document.createElement("i");
    bar.style.height = `${Math.max(8, Number(peak) * 100)}%`;
    waveform.append(bar);
  }
  return waveform;
}

function buildScaleTicks(duration) {
  const tickCount = 6;
  const label = document.createElement("div");
  label.className = "timeline-scale-label";
  label.textContent = "Time";

  const lane = document.createElement("div");
  lane.className = "timeline-scale-lane";

  for (let index = 0; index < tickCount; index += 1) {
    const percent = (index / (tickCount - 1)) * 100;
    const seconds = (duration * percent) / 100;
    const tick = document.createElement("div");
    tick.className = "timeline-tick";
    tick.style.left = `${percent}%`;
    tick.textContent = formatSeconds(seconds);
    lane.append(tick);
  }
  return [label, lane];
}

function setLink(link, href) {
  link.hidden = !href;
  if (href) {
    link.href = href;
  }
}

function setExportControl(link, disabledButton, status, label) {
  if (status.ok && status.url) {
    link.hidden = false;
    link.href = status.url;
    disabledButton.hidden = true;
    disabledButton.title = "";
    return;
  }

  link.hidden = true;
  disabledButton.hidden = false;
  disabledButton.textContent = label;
  disabledButton.title = status.error || "Export unavailable";
}

function tableCell(value) {
  const cell = document.createElement("td");
  cell.textContent = value;
  return cell;
}

function clearWorkspace() {
  state.files = [];
  fileInput.value = "";
  folderInput.value = "";
  resultsPanel.hidden = true;
  timelineLayers.replaceChildren();
  setStatus("Ready", "");
  render();
}

function setStatus(message, tone) {
  jobStatus.textContent = message;
  jobStatus.className = `job-status ${tone || ""}`;
}

function formatBytes(bytes) {
  if (!bytes) {
    return "0 B";
  }
  const units = ["B", "KB", "MB", "GB"];
  const power = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1);
  return `${(bytes / 1024 ** power).toFixed(power ? 1 : 0)} ${units[power]}`;
}

function formatRange(start, end) {
  return `${formatSeconds(start)} - ${formatSeconds(end)}`;
}

function formatSeconds(value) {
  const safe = Math.max(0, Number(value) || 0);
  const minutes = Math.floor(safe / 60);
  const seconds = safe - minutes * 60;
  return `${String(minutes).padStart(2, "0")}:${seconds.toFixed(3).padStart(6, "0")}`;
}

function dedupeFiles(files) {
  const seen = new Set();
  const unique = [];
  for (const file of files) {
    const key = `${file.name}-${file.size}-${file.lastModified}`;
    if (seen.has(key)) {
      continue;
    }
    seen.add(key);
    unique.push(file);
  }
  return unique;
}

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (character) => (
    {
      "&": "&amp;",
      "<": "&lt;",
      ">": "&gt;",
      '"': "&quot;",
      "'": "&#039;",
    }[character]
  ));
}

async function checkHealth() {
  try {
    const response = await fetch("/api/health");
    const payload = await response.json();
    if (payload.ffmpeg.ok) {
      systemStatus.textContent = `FFmpeg OK | v${payload.version}`;
      systemStatus.className = "system-status ok";
    } else {
      systemStatus.textContent = payload.ffmpeg.detail;
      systemStatus.className = "system-status error";
    }
  } catch (error) {
    systemStatus.textContent = error.message;
    systemStatus.className = "system-status error";
  }
}

checkHealth();
render();
