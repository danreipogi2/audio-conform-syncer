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
  exporting: {
    premiere: false,
    resolve: false,
  },
  selectedId: "",
  selectedTimeline: null,
  activeJob: "",
  payload: null,
  timeline: null,
  outputs: {},
  xmlExports: {},
  logs: [],
  backendWarnings: [],
  exportError: "",
};

const addMediaButton = document.querySelector("#addMediaButton");
const dropZone = document.querySelector("#dropZone");
const chooseFiles = document.querySelector("#chooseFiles");
const chooseFolder = document.querySelector("#chooseFolder");
const fileInput = document.querySelector("#fileInput");
const folderInput = document.querySelector("#folderInput");
const videoList = document.querySelector("#videoList");
const audioList = document.querySelector("#audioList");
const warningList = document.querySelector("#warningList");
const videoCount = document.querySelector("#videoCount");
const audioCount = document.querySelector("#audioCount");
const warningCount = document.querySelector("#warningCount");
const syncButton = document.querySelector("#syncButton");
const clearButton = document.querySelector("#clearButton");
const jobStatus = document.querySelector("#jobStatus");
const threshold = document.querySelector("#threshold");
const thresholdValue = document.querySelector("#thresholdValue");
const systemStatus = document.querySelector("#systemStatus");
const coverageMetric = document.querySelector("#coverageMetric");
const matchesMetric = document.querySelector("#matchesMetric");
const ambiguousMetric = document.querySelector("#ambiguousMetric");
const diagnostics = document.querySelector("#diagnostics");
const logCount = document.querySelector("#logCount");
const matchesBody = document.querySelector("#matchesBody");
const videoOutputLink = document.querySelector("#videoOutputLink");
const jsonOutputLink = document.querySelector("#jsonOutputLink");
const markdownOutputLink = document.querySelector("#markdownOutputLink");
const premiereXmlLink = document.querySelector("#premiereXmlLink");
const resolveXmlLink = document.querySelector("#resolveXmlLink");
const exportPremiereButton = document.querySelector("#exportPremiereButton");
const exportResolveButton = document.querySelector("#exportResolveButton");
const premiereExportAction = document.querySelector("#premiereExportAction");
const resolveExportAction = document.querySelector("#resolveExportAction");
const exportError = document.querySelector("#exportError");
const resultsHint = document.querySelector("#resultsHint");
const guidanceTitle = document.querySelector("#guidanceTitle");
const guidanceText = document.querySelector("#guidanceText");
const viewerTitle = document.querySelector("#viewerTitle");
const viewerStatus = document.querySelector("#viewerStatus");
const previewStage = document.querySelector("#previewStage");
const clipDetails = document.querySelector("#clipDetails");
const timelineDuration = document.querySelector("#timelineDuration");
const timelineState = document.querySelector("#timelineState");
const timelineScale = document.querySelector("#timelineScale");
const timelineLayers = document.querySelector("#timelineLayers");

threshold.addEventListener("input", () => {
  thresholdValue.value = Number(threshold.value).toFixed(2);
});

addMediaButton.addEventListener("click", () => fileInput.click());
chooseFiles.addEventListener("click", () => fileInput.click());
chooseFolder.addEventListener("click", () => folderInput.click());
fileInput.addEventListener("change", () => addFiles(Array.from(fileInput.files)));
folderInput.addEventListener("change", () => addFiles(Array.from(folderInput.files)));
clearButton.addEventListener("click", clearWorkspace);
syncButton.addEventListener("click", runSync);
exportPremiereButton.addEventListener("click", () => exportXml("premiere"));
exportResolveButton.addEventListener("click", () => exportXml("resolve"));
premiereExportAction.addEventListener("click", () => exportXml("premiere"));
resolveExportAction.addEventListener("click", () => exportXml("resolve"));

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
  const directFiles = Array.from(dataTransfer.files || []);
  const entries = [];
  const itemFiles = [];

  for (const item of items) {
    if (item.kind && item.kind !== "file") {
      continue;
    }
    const entry = typeof item.webkitGetAsEntry === "function" ? item.webkitGetAsEntry() : null;
    if (entry) {
      entries.push(entry);
      continue;
    }
    if (typeof item.getAsFile === "function") {
      const file = item.getAsFile();
      if (file) {
        itemFiles.push(file);
      }
    }
  }

  const entryGroups = await Promise.all(entries.map((entry) => filesFromEntry(entry)));
  return dedupeFiles([...entryGroups.flat(), ...itemFiles, ...directFiles]);
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
  const existing = new Set(state.files.map((item) => fileKey(item.file)));
  const next = [];

  for (const file of files) {
    const key = fileKey(file);
    if (existing.has(key)) {
      continue;
    }
    existing.add(key);
    next.push(createFileItem(file));
  }

  if (!next.length) {
    return;
  }

  state.files.push(...next);
  state.payload = null;
  state.timeline = null;
  state.outputs = {};
  state.xmlExports = {};
  state.backendWarnings = [];
  state.exportError = "";

  if (!state.selectedId) {
    const firstSelectable = next.find((item) => item.type !== "unknown") || next[0];
    state.selectedId = firstSelectable.id;
  }

  for (const item of next) {
    loadMediaMetadata(item);
  }

  render();
}

function createFileItem(file) {
  const name = file.relativePath || file.webkitRelativePath || file.name;
  const type = classifyFile(file);
  return {
    file,
    id: `${fileKey(file)}-${randomId()}`,
    key: fileKey(file),
    name,
    type,
    extension: extensionFor(file.name),
    objectUrl: URL.createObjectURL(file),
    duration: 0,
    metadataStatus: type === "unknown" ? "warning" : "loading",
  };
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

function loadMediaMetadata(item) {
  if (item.type !== "video" && item.type !== "audio") {
    return;
  }

  const media = document.createElement(item.type === "video" ? "video" : "audio");
  media.preload = "metadata";
  media.src = item.objectUrl;
  media.onloadedmetadata = () => {
    item.duration = Number.isFinite(media.duration) ? media.duration : 0;
    item.metadataStatus = "ready";
    render();
  };
  media.onerror = () => {
    item.metadataStatus = "metadata unavailable";
    render();
  };
}

function extensionFor(name) {
  const index = name.lastIndexOf(".");
  return index >= 0 ? name.slice(index).toLowerCase() : "";
}

function render() {
  const groups = groupedMedia();
  const hasReadyInput = Boolean(groups.selectedVideo && groups.audio.length);
  const canSync = hasReadyInput && !state.busy;

  videoCount.textContent = groups.selectedVideo ? "1" : "0";
  audioCount.textContent = String(groups.audio.length);
  warningCount.textContent = String(groups.warnings.length);

  renderClipList(videoList, groups.selectedVideo ? [groups.selectedVideo] : [], "Flattened edit");
  renderClipList(audioList, groups.audio, "Source audio");
  renderWarningList(groups.warnings);
  renderGuidance(groups);
  renderViewer();
  renderTimeline();
  renderDiagnostics();
  renderMatches();
  renderOutputs();
  renderMetrics();

  syncButton.disabled = !canSync;
  syncButton.textContent = state.busy ? "Synchronizing..." : "Synchronize";
  updateExportButtons();
}

function groupedMedia() {
  const videos = state.files.filter((item) => item.type === "video");
  const selectedVideo = videos[0] || null;
  const extraVideos = videos.slice(1);
  const audio = state.files.filter((item) => item.type === "audio");
  const unsupported = state.files.filter((item) => item.type === "unknown");
  const warningMap = new Map();

  for (const item of extraVideos) {
    warningMap.set(`video:${item.name}`, {
      title: item.name,
      detail: "Extra video not synced; the first video is used.",
    });
  }
  for (const item of unsupported) {
    warningMap.set(`unsupported:${item.name}`, {
      title: item.name,
      detail: "Unsupported file skipped.",
    });
  }
  for (const warning of state.backendWarnings) {
    warningMap.set(`backend:${warning}`, {
      title: warning,
      detail: "Backend warning",
    });
  }

  return {
    videos,
    selectedVideo,
    extraVideos,
    audio,
    unsupported,
    warnings: Array.from(warningMap.values()),
  };
}

function renderClipList(container, items, emptyLabel) {
  container.replaceChildren();
  if (!items.length) {
    container.append(emptyClip(emptyLabel));
    return;
  }

  for (const item of items) {
    const row = document.createElement("button");
    row.type = "button";
    row.className = `clip-row ${state.selectedId === item.id ? "is-selected" : ""}`;
    row.addEventListener("click", () => selectMedia(item.id));

    const copy = document.createElement("div");
    const title = document.createElement("strong");
    title.textContent = item.name;
    const meta = document.createElement("span");
    meta.textContent = `${fileTypeLabel(item)} | ${item.duration ? formatSeconds(item.duration) : formatBytes(item.file.size)}`;
    copy.append(title, meta);

    const status = document.createElement("span");
    status.className = "clip-status";
    status.textContent = item.metadataStatus === "ready" ? "Ready" : statusLabel(item);

    row.append(copy, status);
    container.append(row);
  }
}

function renderWarningList(warnings) {
  warningList.replaceChildren();
  if (!warnings.length) {
    warningList.append(emptyClip("No warnings"));
    return;
  }

  for (const warning of warnings) {
    const row = document.createElement("div");
    row.className = "clip-row warning";
    const copy = document.createElement("div");
    const title = document.createElement("strong");
    title.textContent = warning.title;
    const detail = document.createElement("span");
    detail.textContent = warning.detail;
    copy.append(title, detail);

    const status = document.createElement("span");
    status.className = "clip-status";
    status.textContent = "Warning";

    row.append(copy, status);
    warningList.append(row);
  }
}

function emptyClip(label) {
  const row = document.createElement("div");
  row.className = "clip-row";
  const copy = document.createElement("div");
  const title = document.createElement("strong");
  title.textContent = label;
  const detail = document.createElement("span");
  detail.textContent = "0 files";
  copy.append(title, detail);
  row.append(copy);
  return row;
}

function renderGuidance(groups) {
  if (state.busy) {
    guidanceTitle.textContent = "Analyzing guide audio and matching source recordings...";
    guidanceText.textContent = "The timeline and diagnostics will update when the local job returns.";
    return;
  }

  if (state.payload) {
    guidanceTitle.textContent = "Review the synced regions below, then export XML for your editor.";
    guidanceText.textContent = `${state.payload.summary.match_count} matched region(s) across ${groups.audio.length} source audio file(s).`;
    return;
  }

  if (groups.selectedVideo && groups.audio.length) {
    guidanceTitle.textContent = `Ready to sync 1 video with ${groups.audio.length} source audio file(s).`;
    guidanceText.textContent = groups.extraVideos.length
      ? "Extra videos are listed as warnings and will not be synced."
      : "Click Synchronize to build the timeline model.";
    return;
  }

  guidanceTitle.textContent = "Drop one flattened edited video and your clean source audio files.";
  guidanceText.textContent = "Multiple highlighted files are accepted in one drag.";
}

function renderViewer() {
  const selected = currentSelection();

  if (!selected) {
    viewerTitle.textContent = "No clip selected";
    viewerStatus.textContent = "Waiting";
    viewerStatus.className = "status-pill";
    previewStage.replaceChildren(previewMessage("Select a clip from the media pane or timeline."));
    renderDetails([
      ["Media type", "--"],
      ["Duration", "--"],
      ["Sync status", "No clip selected"],
      ["Confidence", "--"],
    ]);
    return;
  }

  viewerTitle.textContent = selected.title;
  viewerStatus.textContent = selected.status;
  viewerStatus.className = `status-pill ${selected.statusTone || ""}`;
  renderPreview(selected);
  renderDetails(selected.details);
}

function currentSelection() {
  if (state.selectedTimeline) {
    return selectionFromTimeline(state.selectedTimeline);
  }

  const item = state.files.find((candidate) => candidate.id === state.selectedId);
  if (!item) {
    return null;
  }

  return selectionFromMedia(item);
}

function selectionFromMedia(item) {
  return {
    kind: item.type,
    title: item.name,
    status: item.type === "unknown" ? "Warning" : statusLabel(item),
    statusTone: item.type === "unknown" ? "error" : "",
    objectUrl: item.objectUrl,
    details: [
      ["File name", item.name],
      ["Media type", item.type === "video" ? "Flattened edit video" : item.type === "audio" ? "Source audio" : "Unsupported"],
      ["Duration", item.duration ? formatSeconds(item.duration) : "Unavailable"],
      ["File type", fileTypeLabel(item)],
      ["Sample rate", "Unavailable"],
      ["Channels", "Unavailable"],
      ["Sync status", state.payload ? syncStatusForMedia(item) : "Imported"],
      ["Confidence", confidenceForMedia(item)],
    ],
  };
}

function selectionFromTimeline(selection) {
  const { track, clip } = selection;
  const sourceName = clip ? clip.source_name : track.source_name;
  const matchingFile = state.files.find((item) => item.name.endsWith(sourceName));
  const kind = track.kind === "video" ? "video" : "audio";
  const confidence = clip ? `${clip.confidence} (${Number(clip.score).toFixed(3)})` : track.status;

  return {
    kind,
    title: sourceName || track.name,
    status: clip ? clip.confidence : track.status,
    statusTone: clip && clip.low_confidence ? "error" : clip ? "success" : "",
    objectUrl: matchingFile ? matchingFile.objectUrl : "",
    details: [
      ["File name", sourceName || track.name],
      ["Media type", track.kind],
      ["Duration", clip ? formatSeconds(clip.duration_seconds) : formatSeconds(track.duration_seconds)],
      ["Timeline range", clip ? formatRange(clip.timeline_in_seconds, clip.timeline_out_seconds) : "--"],
      ["Source range", clip ? formatRange(clip.source_in_seconds, clip.source_out_seconds) : "--"],
      ["Sample rate", track.sample_rate ? `${track.sample_rate} Hz` : "Unavailable"],
      ["Channels", track.channels ? String(track.channels) : "Unavailable"],
      ["Sync status", track.status],
      ["Confidence", confidence],
    ],
  };
}

function renderPreview(selection) {
  previewStage.replaceChildren();
  if (selection.kind === "video" && selection.objectUrl) {
    const video = document.createElement("video");
    video.controls = true;
    video.src = selection.objectUrl;
    previewStage.append(video);
    return;
  }

  if (selection.kind === "audio") {
    const wrapper = document.createElement("div");
    wrapper.className = "preview-placeholder";
    wrapper.append(waveformPreview(36));
    if (selection.objectUrl) {
      const audio = document.createElement("audio");
      audio.controls = true;
      audio.src = selection.objectUrl;
      wrapper.append(audio);
    } else {
      const message = document.createElement("span");
      message.textContent = "Waveform preview placeholder";
      wrapper.append(message);
    }
    previewStage.append(wrapper);
    return;
  }

  previewStage.append(previewMessage("Preview unavailable for this clip."));
}

function previewMessage(message) {
  const wrapper = document.createElement("div");
  wrapper.className = "preview-placeholder";
  wrapper.append(waveformPreview(28));
  const text = document.createElement("span");
  text.textContent = message;
  wrapper.append(text);
  return wrapper;
}

function waveformPreview(count) {
  const waveform = document.createElement("div");
  waveform.className = "waveform-large";
  for (const peak of placeholderPeaks(count)) {
    const bar = document.createElement("i");
    bar.style.height = `${Math.max(16, peak * 100)}%`;
    waveform.append(bar);
  }
  return waveform;
}

function renderDetails(items) {
  clipDetails.replaceChildren();
  for (const [term, value] of items) {
    const wrapper = document.createElement("div");
    const dt = document.createElement("dt");
    dt.textContent = term;
    const dd = document.createElement("dd");
    dd.textContent = value;
    wrapper.append(dt, dd);
    clipDetails.append(wrapper);
  }
}

function renderTimeline() {
  if (state.timeline) {
    renderSyncedTimeline(state.timeline);
    return;
  }
  renderLocalTimeline(groupedMedia());
}

function renderLocalTimeline(groups) {
  const localDuration = Math.max(
    groups.selectedVideo?.duration || 0,
    ...groups.audio.map((item) => item.duration || 0),
    60,
  );
  timelineDuration.textContent = formatSeconds(groups.selectedVideo || groups.audio.length ? localDuration : 0);
  timelineState.textContent = groups.selectedVideo || groups.audio.length ? "Imported media" : "No media";
  timelineScale.replaceChildren(...buildScaleTicks(localDuration));

  if (!groups.selectedVideo && !groups.audio.length) {
    timelineLayers.replaceChildren(emptyTimelineRow("Import media to build timeline tracks."));
    return;
  }

  const tracks = [];
  if (groups.selectedVideo) {
    tracks.push({
      id: "local-video",
      kind: "video",
      name: "Flattened edit",
      source_name: groups.selectedVideo.name,
      duration_seconds: localDuration,
      status: "reference",
      clips: [
        {
          id: "local-video-clip",
          source_name: groups.selectedVideo.name,
          timeline_in_seconds: 0,
          timeline_out_seconds: localDuration,
          source_in_seconds: 0,
          source_out_seconds: localDuration,
          duration_seconds: localDuration,
          confidence: "reference",
          score: 1,
          low_confidence: false,
        },
      ],
    });
    tracks.push({
      id: "local-guide",
      kind: "guide_audio",
      name: "Guide audio",
      source_name: `${groups.selectedVideo.name} guide`,
      duration_seconds: localDuration,
      status: "pending",
      clips: [],
    });
  }

  for (const [index, item] of groups.audio.entries()) {
    tracks.push({
      id: `local-audio-${index}`,
      kind: "external_audio",
      name: item.name,
      source_name: item.name,
      duration_seconds: item.duration || localDuration,
      status: "unmatched",
      clips: [],
    });
  }

  timelineLayers.replaceChildren(
    ...tracks.map((track) => renderTimelineTrack(track, localDuration, { local: true })),
  );
}

function renderSyncedTimeline(timeline) {
  const duration = Math.max(Number(timeline.duration_seconds) || 0, 0.001);
  timelineDuration.textContent = formatSeconds(duration);
  timelineState.textContent = "Synced timeline";
  timelineScale.replaceChildren(...buildScaleTicks(duration));
  timelineLayers.replaceChildren(
    renderTimelineTrack(timeline.video_track, duration, { video: true }),
    renderTimelineTrack(timeline.guide_audio_track, duration, { guide: true }),
    ...timeline.audio_tracks.map((track) => renderTimelineTrack(track, duration)),
  );
}

function renderTimelineTrack(track, duration, options = {}) {
  const row = document.createElement("div");
  row.className = `timeline-row ${track.status || ""} ${track.kind === "video" ? "video-row" : ""}`;

  const label = document.createElement("div");
  label.className = "timeline-label";
  const title = document.createElement("strong");
  title.textContent = track.name || track.source_name;
  const detail = document.createElement("span");
  detail.textContent = timelineTrackDetail(track, options);
  label.append(title, detail);

  const lane = document.createElement("div");
  lane.className = "timeline-lane";
  lane.addEventListener("click", () => selectTimeline(track, null));
  lane.append(renderWaveform(track.waveform_peaks));
  lane.append(playheadMarker());

  if (!track.clips || !track.clips.length) {
    const marker = document.createElement("div");
    marker.className = "unmatched-marker";
    marker.textContent = options.local ? "Waiting for sync" : track.kind === "guide_audio" ? "Guide audio" : "No synced regions";
    lane.append(marker);
  } else {
    for (const clip of track.clips) {
      lane.append(renderTimelineClip(track, clip, duration));
    }
  }

  row.append(label, lane);
  return row;
}

function renderTimelineClip(track, clip, duration) {
  const element = document.createElement("button");
  element.type = "button";
  element.className = `timeline-clip ${clip.low_confidence ? "low-confidence" : ""} ${clip.confidence === "reference" ? "reference-clip" : ""} ${isSelectedClip(track, clip) ? "is-selected" : ""}`;
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
  element.addEventListener("click", (event) => {
    event.stopPropagation();
    selectTimeline(track, clip);
  });
  element.append(
    textElement("strong", clip.source_name),
    textElement("span", formatRange(clip.timeline_in_seconds, clip.timeline_out_seconds)),
    textElement("small", `${clip.confidence} | ${Number(clip.score).toFixed(3)}`),
  );
  return element;
}

function renderWaveform(peaks) {
  const waveform = document.createElement("div");
  waveform.className = "waveform";
  for (const peak of peaks && peaks.length ? peaks : placeholderPeaks(64)) {
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
  lane.append(playheadMarker());

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

function emptyTimelineRow(message) {
  const row = document.createElement("div");
  row.className = "timeline-row";
  const label = document.createElement("div");
  label.className = "timeline-label";
  label.append(textElement("strong", "Timeline"), textElement("span", "No tracks yet"));
  const lane = document.createElement("div");
  lane.className = "timeline-lane";
  const marker = document.createElement("div");
  marker.className = "unmatched-marker";
  marker.textContent = message;
  lane.append(marker);
  row.append(label, lane);
  return row;
}

async function runSync() {
  const groups = groupedMedia();
  if (!groups.selectedVideo || !groups.audio.length || state.busy) {
    return;
  }

  state.busy = true;
  state.payload = null;
  state.timeline = null;
  state.outputs = {};
  state.xmlExports = {};
  state.exportError = "";
  state.logs = [
    clientLog("info", "Files received"),
    clientLog("info", "Job created"),
    clientLog("info", "Uploading media to local sync job"),
  ];
  setStatus("Analyzing guide audio and matching source recordings...", "");
  render();

  const formData = new FormData();
  const uploadItems = [
    groups.selectedVideo,
    ...groups.audio,
    ...groups.extraVideos,
    ...groups.unsupported,
  ];
  for (const item of uploadItems) {
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
    state.activeJob = payload.job_id;
    state.payload = payload;
    state.timeline = payload.timeline;
    state.outputs = payload.outputs || {};
    state.xmlExports = payload.xml_exports || {};
    state.logs = payload.logs || state.logs;
    state.backendWarnings = payload.warnings || [];
    render();
    await refreshLogs();
    setStatus("Sync complete", "success");
  } catch (error) {
    state.logs.push(clientLog("error", error.message));
    setStatus(`${error.message}. Check media formats and FFmpeg, then try again.`, "error");
  } finally {
    state.busy = false;
    render();
  }
}

async function exportXml(target) {
  if (!canExportXml(target)) {
    return;
  }

  state.exporting[target] = true;
  state.exportError = "";
  setStatus(`Exporting ${targetLabel(target)}...`, "");
  render();

  try {
    const response = await fetch(`/api/jobs/${state.activeJob}/exports/${target}`, {
      method: "POST",
    });
    const payload = await response.json();
    if (!response.ok || !payload.ok) {
      throw new Error(payload.error || "Export failed");
    }
    state.outputs = payload.outputs || state.outputs;
    state.xmlExports = payload.xml_exports || state.xmlExports;
    state.logs = payload.logs || state.logs;
    setStatus(`${targetLabel(target)} ready`, "success");
  } catch (error) {
    state.exportError = error.message;
    state.logs.push(clientLog("error", error.message));
    setStatus(error.message, "error");
  } finally {
    state.exporting[target] = false;
    render();
  }
}

async function refreshLogs() {
  if (!state.activeJob) {
    return;
  }
  try {
    const response = await fetch(`/api/jobs/${state.activeJob}/logs`);
    const payload = await response.json();
    if (response.ok && payload.ok) {
      state.logs = payload.logs || [];
      renderDiagnostics();
    }
  } catch (error) {
    state.logs.push(clientLog("warning", `Could not refresh job logs: ${error.message}`));
  }
}

function renderDiagnostics() {
  logCount.textContent = String(state.logs.length);
  diagnostics.replaceChildren();
  if (!state.logs.length) {
    const item = document.createElement("div");
    item.className = "diagnostic";
    item.append(textElement("time", "--"), textElement("span", "Job log will appear here."));
    diagnostics.append(item);
    return;
  }

  for (const event of state.logs) {
    const item = document.createElement("div");
    item.className = `diagnostic ${event.level || "info"}`;
    item.append(
      textElement("time", formatTimestamp(event.timestamp)),
      textElement("span", `${event.level || "info"}: ${event.message || ""}`),
    );
    diagnostics.append(item);
  }
}

function renderMatches() {
  matchesBody.replaceChildren();
  if (!state.payload) {
    const row = document.createElement("tr");
    const cell = tableCell("No synced regions yet.");
    cell.colSpan = 4;
    row.append(cell);
    matchesBody.append(row);
    return;
  }

  if (!state.payload.matches.length) {
    const row = document.createElement("tr");
    const cell = tableCell("No matches found.");
    cell.colSpan = 4;
    row.append(cell);
    matchesBody.append(row);
    return;
  }

  for (const match of state.payload.matches) {
    const row = document.createElement("tr");
    row.append(
      tableCell(formatRange(match.reference_start_seconds, match.reference_end_seconds)),
      tableCell(formatRange(match.source_start_seconds, match.source_end_seconds)),
      tableCell(Number(match.score).toFixed(3)),
      tableCell(match.confidence),
    );
    matchesBody.append(row);
  }
}

function renderOutputs() {
  resultsHint.textContent = state.payload
    ? "Review the synced regions below, then export XML for your editor."
    : "Output links appear after a successful sync.";
  setLink(jsonOutputLink, state.outputs.json);
  setLink(markdownOutputLink, state.outputs.markdown);
  setLink(videoOutputLink, state.outputs.synced_video);
  setLink(premiereXmlLink, state.outputs.premiere_xml);
  setLink(resolveXmlLink, state.outputs.resolve_xml);
  exportError.hidden = !state.exportError;
  exportError.textContent = state.exportError;
}

function renderMetrics() {
  if (!state.payload) {
    coverageMetric.textContent = "--";
    matchesMetric.textContent = "--";
    ambiguousMetric.textContent = "--";
    return;
  }

  const summary = state.payload.summary;
  coverageMetric.textContent = `${Number(summary.coverage_percent).toFixed(1)}%`;
  matchesMetric.textContent = String(summary.match_count);
  ambiguousMetric.textContent = String(summary.ambiguous_match_count);
}

function updateExportButtons() {
  const controls = [
    [exportPremiereButton, "premiere"],
    [premiereExportAction, "premiere"],
    [exportResolveButton, "resolve"],
    [resolveExportAction, "resolve"],
  ];

  for (const [button, target] of controls) {
    button.disabled = !canExportXml(target);
    button.textContent = state.exporting[target]
      ? `Exporting ${targetLabel(target)}...`
      : `Export ${targetLabel(target)}`;
    button.title = exportDisabledReason(target);
  }
}

function canExportXml(target) {
  return Boolean(
    state.activeJob
      && state.payload
      && state.payload.summary.match_count > 0
      && !state.busy
      && !state.exporting[target],
  );
}

function exportDisabledReason(target) {
  if (state.exporting[target]) {
    return "Export is running.";
  }
  if (!state.payload) {
    return "Synchronize media before exporting XML.";
  }
  if (!state.payload.summary.match_count) {
    return "XML export needs at least one synced region.";
  }
  return "";
}

function selectMedia(id) {
  state.selectedId = id;
  state.selectedTimeline = null;
  render();
}

function selectTimeline(track, clip) {
  state.selectedTimeline = { track, clip };
  state.selectedId = "";
  render();
}

function isSelectedClip(track, clip) {
  return Boolean(
    state.selectedTimeline
      && state.selectedTimeline.track.id === track.id
      && state.selectedTimeline.clip
      && state.selectedTimeline.clip.id === clip.id,
  );
}

function syncStatusForMedia(item) {
  if (!state.timeline) {
    return "Imported";
  }
  if (item.type === "video") {
    return "Reference";
  }
  const track = state.timeline.audio_tracks.find((candidate) => sameSourceName(candidate.source_name, item.name));
  return track ? track.status : "Not in synced timeline";
}

function confidenceForMedia(item) {
  if (!state.timeline || item.type !== "audio") {
    return "--";
  }
  const track = state.timeline.audio_tracks.find((candidate) => sameSourceName(candidate.source_name, item.name));
  if (!track || !track.clips.length) {
    return "unmatched";
  }
  const best = track.clips.reduce((winner, clip) => (clip.score > winner.score ? clip : winner));
  return `${best.confidence} (${Number(best.score).toFixed(3)})`;
}

function timelineTrackDetail(track, options) {
  if (track.kind === "video") {
    return "Flattened edit";
  }
  if (track.kind === "guide_audio") {
    return options.local ? "Baked-in guide audio after sync" : "Baked-in guide audio";
  }
  return track.status === "matched" ? "Source audio matched" : "Source audio unmatched";
}

function sameSourceName(left, right) {
  return left === right || right.endsWith(left) || left.endsWith(right);
}

function clearWorkspace() {
  for (const item of state.files) {
    URL.revokeObjectURL(item.objectUrl);
  }
  state.files = [];
  state.busy = false;
  state.exporting = { premiere: false, resolve: false };
  state.selectedId = "";
  state.selectedTimeline = null;
  state.activeJob = "";
  state.payload = null;
  state.timeline = null;
  state.outputs = {};
  state.xmlExports = {};
  state.logs = [];
  state.backendWarnings = [];
  state.exportError = "";
  fileInput.value = "";
  folderInput.value = "";
  setStatus("Ready", "");
  render();
}

function setStatus(message, tone) {
  jobStatus.textContent = message;
  jobStatus.className = `job-status ${tone || ""}`;
}

function setLink(link, href) {
  link.hidden = !href;
  if (href) {
    link.href = href;
  }
}

function tableCell(value) {
  const cell = document.createElement("td");
  cell.textContent = value;
  return cell;
}

function textElement(tag, value) {
  const element = document.createElement(tag);
  element.textContent = value;
  return element;
}

function playheadMarker() {
  const marker = document.createElement("div");
  marker.className = "playhead-marker";
  return marker;
}

function placeholderPeaks(count) {
  return Array.from({ length: count }, (_, index) => {
    const value = Math.abs(Math.sin(index * 0.57) * Math.cos(index * 0.21));
    return 0.18 + value * 0.78;
  });
}

function fileTypeLabel(item) {
  if (item.extension) {
    return item.extension.slice(1).toUpperCase();
  }
  return item.type === "video" ? "Video" : item.type === "audio" ? "Audio" : "Unknown";
}

function statusLabel(item) {
  if (item.metadataStatus === "metadata unavailable") {
    return "Metadata unavailable";
  }
  if (item.metadataStatus === "loading") {
    return "Reading";
  }
  if (item.type === "unknown") {
    return "Unsupported";
  }
  return "Ready";
}

function targetLabel(target) {
  return target === "premiere" ? "Premiere XML" : "DaVinci Resolve XML";
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

function formatTimestamp(value) {
  if (!value) {
    return "--";
  }
  const date = new Date(value);
  if (Number.isNaN(date.valueOf())) {
    return value;
  }
  return date.toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

function dedupeFiles(files) {
  const seen = new Set();
  const unique = [];
  for (const file of files) {
    const key = fileKey(file);
    if (seen.has(key)) {
      continue;
    }
    seen.add(key);
    unique.push(file);
  }
  return unique;
}

function fileKey(file) {
  return `${file.name}-${file.size}-${file.lastModified}`;
}

function randomId() {
  return crypto.randomUUID ? crypto.randomUUID() : Math.random().toString(36).slice(2);
}

function clientLog(level, message) {
  return {
    timestamp: new Date().toISOString(),
    level,
    message,
    details: {},
  };
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
