const DEFAULT_SERVER = "http://127.0.0.1:5000";
const BRIDGE_PAYLOAD_TYPE = "application/x-file-browser-file";
const BRIDGE_TEXT_PREFIX = "__OPENTOCHROME_PAYLOAD__::";

const IMAGE_EXTS = new Set([
  "apng",
  "png",
  "jpg",
  "jpeg",
  "jfif",
  "gif",
  "webp",
  "bmp",
  "svg",
  "avif",
  "ico",
  "heif",
  "heic",
  "tiff",
  "tif",
]);

const state = {
  serverUrl: DEFAULT_SERVER,
  roots: [],
  currentRoot: "",
  currentPath: "",
  entries: [],
  selectedFilePath: "",
  previewHidden: false,
  history: [],
  historyIndex: -1,
  viewMode: "browse",
  searchQuery: "",
};

const els = {
  homeBtn: document.getElementById("homeBtn"),
  backBtn: document.getElementById("backBtn"),
  forwardBtn: document.getElementById("forwardBtn"),
  configBtn: document.getElementById("configBtn"),
  closeConfigBtn: document.getElementById("closeConfigBtn"),
  configPanel: document.getElementById("configPanel"),
  togglePreviewBtn: document.getElementById("togglePreviewBtn"),
  refreshBtn: document.getElementById("refreshBtn"),
  pathCrumbs: document.getElementById("pathCrumbs"),
  searchInput: document.getElementById("searchInput"),
  statusLine: document.getElementById("statusLine"),
  fileList: document.getElementById("fileList"),
  previewDock: document.getElementById("previewDock"),
  previewType: document.getElementById("previewType"),
  previewMeta: document.getElementById("previewMeta"),
  previewBody: document.getElementById("previewBody"),
  serverUrl: document.getElementById("serverUrl"),
  saveServerBtn: document.getElementById("saveServerBtn"),
  rootSelect: document.getElementById("rootSelect"),
};

function setStatus(message, isError = false) {
  els.statusLine.textContent = message;
  els.statusLine.classList.toggle("error", isError);
}

function humanSize(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function fileExt(name) {
  const idx = name.lastIndexOf(".");
  return idx === -1 ? "" : name.slice(idx + 1).toLowerCase();
}

function isImageFile(name) {
  return IMAGE_EXTS.has(fileExt(name));
}

function downloadUrl(path) {
  return `${state.serverUrl}/api/download?root=${encodeURIComponent(state.currentRoot)}&path=${encodeURIComponent(path)}`;
}

function saveServerUrl(url) {
  chrome.storage.local.set({ serverUrl: url });
}

function savePreviewState(hidden) {
  chrome.storage.local.set({ previewHidden: hidden });
}

function loadServerUrl() {
  return new Promise((resolve) => {
    chrome.storage.local.get(["serverUrl"], (result) => resolve(result.serverUrl || DEFAULT_SERVER));
  });
}

function loadPreviewState() {
  return new Promise((resolve) => {
    chrome.storage.local.get(["previewHidden"], (result) => resolve(Boolean(result.previewHidden)));
  });
}

async function apiFetch(path, options = {}) {
  const response = await fetch(`${state.serverUrl}${path}`, options);
  if (!response.ok) {
    const txt = await response.text();
    throw new Error(txt || `Request failed: ${response.status}`);
  }
  return response.json();
}

function iconSvg(type, variant = 0) {
  if (type === "root") {
    const colors = [
      ["#60a5fa", "#1d4ed8"],
      ["#34d399", "#059669"],
      ["#c084fc", "#9333ea"],
      ["#f59e0b", "#d97706"],
    ];
    const [fill, stroke] = colors[variant % colors.length];
    return `<svg class="file-icon" viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M3 7a2 2 0 012-2h5l2 2h7a2 2 0 012 2v8a2 2 0 01-2 2H5a2 2 0 01-2-2V7z" fill="${fill}"/><path d="M3 9h18" stroke="${stroke}" stroke-width="1.3"/></svg>`;
  }
  if (type === "directory") {
    return `<svg class="file-icon" viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M3 7a2 2 0 012-2h5l2 2h7a2 2 0 012 2v8a2 2 0 01-2 2H5a2 2 0 01-2-2V7z" fill="#60a5fa"/><path d="M3 9h18" stroke="#1d4ed8" stroke-width="1.3"/></svg>`;
  }
  if (type === "image") {
    return `<svg class="file-icon" viewBox="0 0 24 24" fill="none" aria-hidden="true"><rect x="4" y="3" width="16" height="18" rx="2" fill="#a5b4fc"/><path d="M7 16l3-3 2 2 3-4 2 5" stroke="#3730a3" stroke-width="1.4"/><circle cx="9" cy="8" r="1.2" fill="#3730a3"/></svg>`;
  }
  return `<svg class="file-icon" viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M7 3h7l5 5v13H7a2 2 0 01-2-2V5a2 2 0 012-2z" fill="#e2e8f0"/><path d="M14 3v5h5" stroke="#94a3b8" stroke-width="1.4"/></svg>`;
}

function setConfigVisibility(open) {
  els.configPanel.classList.toggle("hidden", !open);
}

function setPreviewVisibility(hidden) {
  state.previewHidden = hidden;
  els.previewDock.classList.toggle("preview-hidden", hidden);
  els.togglePreviewBtn.title = hidden ? "Show Preview" : "Hide Preview";
  savePreviewState(hidden);
}

function clearPreview() {
  els.previewType.textContent = "None";
  els.previewMeta.textContent = "Select a file to preview.";
  els.previewBody.textContent = "";
}

function renderRoots() {
  els.rootSelect.innerHTML = "";
  state.roots.forEach((root) => {
    const option = document.createElement("option");
    option.value = root.id;
    option.textContent = root.label;
    els.rootSelect.appendChild(option);
  });
  if (state.currentRoot) {
    els.rootSelect.value = state.currentRoot;
  }
}

function renderHistoryButtons() {
  els.backBtn.disabled = state.historyIndex <= 0;
  els.forwardBtn.disabled = state.historyIndex === -1 || state.historyIndex >= state.history.length - 1;
}

function pushHistory(record) {
  if (state.historyIndex >= 0) {
    const cur = state.history[state.historyIndex];
    if (cur && cur.mode === record.mode && cur.root === record.root && cur.path === record.path) {
      renderHistoryButtons();
      return;
    }
  }
  state.history = state.history.slice(0, state.historyIndex + 1);
  state.history.push(record);
  state.historyIndex = state.history.length - 1;
  renderHistoryButtons();
}

function renderBreadcrumbs() {
  els.pathCrumbs.innerHTML = "";

  if (state.viewMode === "home") {
    const home = document.createElement("span");
    home.className = "crumb current";
    home.textContent = "Home";
    els.pathCrumbs.appendChild(home);
    return;
  }

  const root = state.roots.find((r) => r.id === state.currentRoot);
  const rootLabel = root ? root.label : "Root";
  const segments = state.currentPath ? state.currentPath.split("/").filter(Boolean) : [];

  const parts = [{ label: rootLabel, path: "" }];
  let acc = "";
  for (const seg of segments) {
    acc = acc ? `${acc}/${seg}` : seg;
    parts.push({ label: seg, path: acc });
  }

  parts.forEach((part, idx) => {
    if (idx > 0) {
      const sep = document.createElement("span");
      sep.className = "crumb-sep";
      sep.textContent = "/";
      els.pathCrumbs.appendChild(sep);
    }
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "crumb";
    if (idx === parts.length - 1) btn.classList.add("current");
    btn.textContent = part.label;
    btn.addEventListener("click", () => openLocation(state.currentRoot, part.path, true));
    els.pathCrumbs.appendChild(btn);
  });
}

function getFilteredEntries() {
  const query = state.searchQuery.trim().toLowerCase();
  if (!query) return state.entries;
  return state.entries.filter((entry) => entry.name.toLowerCase().includes(query));
}

function getFilteredRoots() {
  const query = state.searchQuery.trim().toLowerCase();
  if (!query) return state.roots;
  return state.roots.filter((root) => {
    const haystack = `${root.label} ${root.path}`.toLowerCase();
    return haystack.includes(query);
  });
}

function renderHomeCards() {
  const roots = getFilteredRoots();
  els.fileList.innerHTML = "";

  if (roots.length === 0) {
    const empty = document.createElement("li");
    empty.className = "empty-msg";
    empty.textContent = "No paths match your search";
    els.fileList.appendChild(empty);
    return;
  }

  roots.forEach((root, idx) => {
    const card = document.createElement("li");
    card.className = `file-card root-card root-variant-${idx % 4}`;
    card.innerHTML = `
      <div class="file-icon-wrap">${iconSvg("root", idx)}</div>
      <div class="file-name">${root.label}</div>
      <div class="file-meta">Path Link</div>
    `;
    card.addEventListener("click", () => openLocation(root.id, "", true));
    els.fileList.appendChild(card);
  });
}

function renderBrowseCards() {
  const entries = getFilteredEntries();
  els.fileList.innerHTML = "";

  if (entries.length === 0) {
    const empty = document.createElement("li");
    empty.className = "empty-msg";
    empty.textContent = state.searchQuery ? "No files or folders match your search" : "No files or folders in this location";
    els.fileList.appendChild(empty);
    return;
  }

  entries.forEach((entry) => {
    const card = document.createElement("li");
    card.className = "file-card";
    if (entry.type === "file" && state.selectedFilePath === entry.relative_path) {
      card.classList.add("active");
    }

    const typeForIcon = entry.type === "file" && isImageFile(entry.name) ? "image" : entry.type;
    card.innerHTML = `
      <div class="file-icon-wrap">${iconSvg(typeForIcon)}</div>
      <div class="file-name">${entry.name}</div>
      <div class="file-meta">${entry.type === "directory" ? "Folder" : humanSize(entry.size)}</div>
    `;

    card.addEventListener("click", () => {
      if (entry.type === "directory") {
        openLocation(state.currentRoot, entry.relative_path, true);
      } else {
        previewFile(entry);
      }
    });

    if (entry.type === "file") {
      const sendBtn = document.createElement("button");
      sendBtn.type = "button";
      sendBtn.className = "send-btn";
      sendBtn.textContent = "Send to site";
      sendBtn.addEventListener("click", (event) => {
        event.stopPropagation();
        sendFileToActiveTab(entry);
      });
      card.appendChild(sendBtn);

      card.draggable = true;
      card.addEventListener("dragstart", (event) => {
        if (!event.dataTransfer) return;
        const url = downloadUrl(entry.relative_path);
        const payload = {
          serverUrl: state.serverUrl,
          files: [
            {
              serverUrl: state.serverUrl,
              root: state.currentRoot,
              path: entry.relative_path,
              name: entry.name,
              downloadUrl: url,
            },
          ],
        };

        event.dataTransfer.effectAllowed = "copy";
        event.dataTransfer.setData("DownloadURL", `application/octet-stream:${entry.name}:${url}`);
        event.dataTransfer.setData("text/uri-list", url);
        event.dataTransfer.setData(BRIDGE_PAYLOAD_TYPE, JSON.stringify(payload));
        event.dataTransfer.setData("text/plain", `${BRIDGE_TEXT_PREFIX}${JSON.stringify(payload)}`);
        chrome.runtime.sendMessage({ type: "OPENTOCHROME_DRAG_ARM", files: payload.files });
        setStatus(`Dragging ${entry.name} to website upload area...`);
      });

      card.addEventListener("dragend", () => {
        chrome.runtime.sendMessage({ type: "OPENTOCHROME_DRAG_CLEAR" });
      });
    }

    els.fileList.appendChild(card);
  });
}

function renderFileList() {
  if (state.viewMode === "home") {
    renderHomeCards();
    return;
  }
  renderBrowseCards();
}

async function fetchRoots() {
  const data = await apiFetch("/api/roots");
  state.roots = data.roots || [];
  if (!state.currentRoot && state.roots.length > 0) {
    state.currentRoot = state.roots[0].id;
  }
  renderRoots();
}

async function openHome(addHistory) {
  state.viewMode = "home";
  state.selectedFilePath = "";
  clearPreview();
  renderBreadcrumbs();
  renderFileList();
  setStatus(`Home: ${getFilteredRoots().length} path link(s)`);
  if (addHistory) {
    pushHistory({ mode: "home", root: "", path: "" });
  }
}

async function openLocation(root, path, addHistory) {
  state.viewMode = "browse";
  state.currentRoot = root;
  state.currentPath = path || "";
  setStatus("Loading folder...");

  try {
    const data = await apiFetch(
      `/api/browse?root=${encodeURIComponent(state.currentRoot)}&path=${encodeURIComponent(state.currentPath)}`,
    );
    state.currentPath = data.current_path || "";
    state.entries = data.entries || [];
    state.selectedFilePath = "";
    renderFileList();
    renderBreadcrumbs();
    if (addHistory) {
      pushHistory({ mode: "browse", root: state.currentRoot, path: state.currentPath });
    }
    setStatus(`Loaded ${getFilteredEntries().length} item(s)`);
  } catch (error) {
    state.entries = [];
    renderFileList();
    renderBreadcrumbs();
    setStatus(`Cannot browse from ${state.serverUrl}`, true);
    console.error(error);
  }
}

async function previewFile(entry) {
  state.selectedFilePath = entry.relative_path;
  renderFileList();
  els.previewMeta.textContent = entry.full_path;

  if (isImageFile(entry.name)) {
    els.previewType.textContent = "Image";
    els.previewBody.innerHTML = `<img class="preview-image" src="${downloadUrl(entry.relative_path)}" alt="${entry.name}" />`;
    setStatus(`Image preview loaded: ${entry.name}`);
    return;
  }

  setStatus(`Previewing ${entry.name}...`);
  try {
    const data = await apiFetch(
      `/api/preview?root=${encodeURIComponent(state.currentRoot)}&path=${encodeURIComponent(entry.relative_path)}`,
    );
    els.previewType.textContent = "Text";
    els.previewBody.textContent = data.content || "";
    setStatus(`Preview loaded: ${entry.name}`);
  } catch {
    els.previewType.textContent = "Binary";
    els.previewBody.innerHTML = `Preview unavailable for this file type.<br/><a href="${downloadUrl(entry.relative_path)}" target="_blank" rel="noreferrer">Open file</a>`;
    setStatus("Preview unavailable, fallback link shown", false);
  }
}

function sendFileToActiveTab(entry) {
  setStatus(`Sending ${entry.name} to active tab...`);
  chrome.runtime.sendMessage(
    {
      type: "OPENTOCHROME_SEND_TO_ACTIVE_TAB",
      files: [{ serverUrl: state.serverUrl, root: state.currentRoot, path: entry.relative_path, name: entry.name }],
    },
    (response) => {
      if (chrome.runtime.lastError) {
        setStatus(`Send failed: ${chrome.runtime.lastError.message}`, true);
        return;
      }
      if (response?.ok) {
        setStatus(`Sent to site: ${entry.name}`);
      } else {
        setStatus(`Send failed: ${response?.error || "Unknown error"}`, true);
      }
    },
  );
}

function goBack() {
  if (state.historyIndex <= 0) return;
  state.historyIndex -= 1;
  renderHistoryButtons();
  const target = state.history[state.historyIndex];
  if (target.mode === "home") {
    openHome(false);
    return;
  }
  openLocation(target.root, target.path, false);
}

function goForward() {
  if (state.historyIndex >= state.history.length - 1) return;
  state.historyIndex += 1;
  renderHistoryButtons();
  const target = state.history[state.historyIndex];
  if (target.mode === "home") {
    openHome(false);
    return;
  }
  openLocation(target.root, target.path, false);
}

async function saveConfigAndReload() {
  state.serverUrl = els.serverUrl.value.trim() || DEFAULT_SERVER;
  saveServerUrl(state.serverUrl);
  setStatus("Saved server settings. Reloading...", false);
  state.roots = [];
  state.currentRoot = "";
  state.currentPath = "";
  await fetchRoots();
  await openHome(true);
  setConfigVisibility(false);
}

function applySearch(query) {
  state.searchQuery = query.trim();
  renderFileList();
  if (state.viewMode === "home") {
    setStatus(`Home: ${getFilteredRoots().length} path link(s)`);
  } else {
    setStatus(`Loaded ${getFilteredEntries().length} item(s)`);
  }
}

function bindHotkeys() {
  document.addEventListener("keydown", (event) => {
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
      event.preventDefault();
      els.searchInput.focus();
      els.searchInput.select();
    }
  });
}

async function init() {
  const [serverUrl, previewHidden] = await Promise.all([loadServerUrl(), loadPreviewState()]);
  state.serverUrl = serverUrl;
  els.serverUrl.value = state.serverUrl;
  setPreviewVisibility(previewHidden);
  clearPreview();

  bindHotkeys();

  els.refreshBtn.addEventListener("click", () => {
    if (state.viewMode === "home") {
      openHome(false);
      return;
    }
    openLocation(state.currentRoot, state.currentPath, false);
  });

  els.homeBtn.addEventListener("click", () => openHome(true));
  els.togglePreviewBtn.addEventListener("click", () => setPreviewVisibility(!state.previewHidden));
  els.backBtn.addEventListener("click", goBack);
  els.forwardBtn.addEventListener("click", goForward);
  els.configBtn.addEventListener("click", () => {
    setConfigVisibility(els.configPanel.classList.contains("hidden"));
  });
  els.closeConfigBtn.addEventListener("click", () => setConfigVisibility(false));
  els.saveServerBtn.addEventListener("click", saveConfigAndReload);

  els.rootSelect.addEventListener("change", () => openLocation(els.rootSelect.value, "", true));
  els.searchInput.addEventListener("input", () => applySearch(els.searchInput.value));

  document.addEventListener("click", (event) => {
    const target = event.target;
    if (!(target instanceof Node)) return;
    if (els.configPanel.classList.contains("hidden")) return;
    if (els.configPanel.contains(target) || els.configBtn.contains(target)) return;
    setConfigVisibility(false);
  });

  await fetchRoots();
  await openHome(true);
  renderHistoryButtons();
  setConfigVisibility(false);
}

init();
