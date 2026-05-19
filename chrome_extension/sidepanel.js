const DEFAULT_SERVER = "http://127.0.0.1:17650";
const BRIDGE_PAYLOAD_TYPE = "application/x-file-browser-file";
const BRIDGE_TEXT_PREFIX = "__FILE_BROWSER_PAYLOAD__::";

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

const TEXT_EXTS = new Set([
  "txt",
  "md",
  "markdown",
  "json",
  "csv",
  "tsv",
  "log",
  "yaml",
  "yml",
  "js",
  "ts",
  "jsx",
  "tsx",
  "html",
  "css",
  "py",
  "java",
  "c",
  "cpp",
  "h",
  "hpp",
  "rs",
  "go",
  "rb",
  "php",
  "sh",
  "xml",
]);

const state = {
  serverUrl: DEFAULT_SERVER,
  roots: [],
  currentRoot: "",
  currentPath: "",
  entries: [],
  selectedFilePath: "",
  selectedFileFullPath: "",
  previewHidden: false,
  theme: "light",
  accent: "blue",
  lastLocation: { mode: "home", root: "", path: "" },
  selectedFiles: new Set(),
  lastSelectedIndex: -1,
  history: [],
  historyIndex: -1,
  viewMode: "browse",
  searchQuery: "",
};

const ACCENT_OPTIONS = {
  blue: { accent: "#2563eb", soft: "rgba(37, 99, 235, 0.12)" },
  teal: { accent: "#0d9488", soft: "rgba(13, 148, 136, 0.16)" },
  green: { accent: "#16a34a", soft: "rgba(22, 163, 74, 0.16)" },
  amber: { accent: "#d97706", soft: "rgba(217, 119, 6, 0.16)" },
  rose: { accent: "#e11d48", soft: "rgba(225, 29, 72, 0.16)" },
};

const els = {
  homeBtn: document.getElementById("homeBtn"),
  backBtn: document.getElementById("backBtn"),
  forwardBtn: document.getElementById("forwardBtn"),
  configBtn: document.getElementById("configBtn"),
  togglePreviewBtn: document.getElementById("togglePreviewBtn"),
  refreshBtn: document.getElementById("refreshBtn"),
  pathText: document.getElementById("pathText"),
  copyPathBtn: document.getElementById("copyPathBtn"),
  previewToggleLabel: document.getElementById("previewToggleLabel"),
  previewIcon: document.getElementById("previewIcon"),
  themeToggleBtn: document.getElementById("themeToggleBtn"),
  themeIcon: document.getElementById("themeIcon"),
  multiSendBar: document.getElementById("multiSendBar"),
  multiSendText: document.getElementById("multiSendText"),
  multiSendBtn: document.getElementById("multiSendBtn"),
  searchInput: document.getElementById("searchInput"),
  statusLine: document.getElementById("statusLine"),
  fileList: document.getElementById("fileList"),
  previewDock: document.getElementById("previewDock"),
  previewType: document.getElementById("previewType"),
  previewMeta: document.getElementById("previewMeta"),
  previewBody: document.getElementById("previewBody"),
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

function isPdfFile(name) {
  return fileExt(name) === "pdf";
}

function isTextFile(name) {
  return TEXT_EXTS.has(fileExt(name));
}

function downloadUrl(path) {
  return `${state.serverUrl}/api/download?root=${encodeURIComponent(state.currentRoot)}&path=${encodeURIComponent(path)}`;
}

function savePreviewState(hidden) {
  chrome.storage.local.set({ previewHidden: hidden });
}

function loadSettings() {
  return new Promise((resolve) => {
    chrome.storage.local.get(
      ["serverUrl", "previewHidden", "theme", "accent", "lastMode", "lastRootId", "lastPath"],
      (result) =>
        resolve({
          serverUrl: result.serverUrl || DEFAULT_SERVER,
          previewHidden: Boolean(result.previewHidden),
          theme: result.theme || "light",
          accent: result.accent || "blue",
          lastMode: result.lastMode || "home",
          lastRootId: result.lastRootId || "",
          lastPath: result.lastPath || "",
        }),
    );
  });
}

function saveTheme(theme) {
  chrome.storage.local.set({ theme });
}

function saveAccent(accentKey) {
  chrome.storage.local.set({ accent: accentKey });
}

function saveLastLocation(mode, root, path) {
  const safeMode = mode === "browse" ? "browse" : "home";
  const safeRoot = root || "";
  const safePath = path || "";
  state.lastLocation = { mode: safeMode, root: safeRoot, path: safePath };
  chrome.storage.local.set({ lastMode: safeMode, lastRootId: safeRoot, lastPath: safePath });
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

function setPreviewVisibility(hidden) {
  state.previewHidden = hidden;
  els.previewDock.classList.toggle("preview-hidden", hidden);
  els.togglePreviewBtn.title = hidden ? "View" : "Hide";
  if (els.previewToggleLabel) {
    els.previewToggleLabel.textContent = hidden ? "View" : "Hide";
  }
  if (els.previewIcon) {
    els.previewIcon.textContent = hidden ? "visibility" : "visibility_off";
  }
  savePreviewState(hidden);
}

function applyTheme(theme) {
  state.theme = theme === "dark" ? "dark" : "light";
  document.body.classList.toggle("theme-dark", state.theme === "dark");
  if (els.themeIcon) {
    els.themeIcon.textContent = state.theme === "dark" ? "light_mode" : "dark_mode";
  }
  if (els.themeToggleBtn) {
    els.themeToggleBtn.title = state.theme === "dark" ? "Switch to light theme" : "Switch to dark theme";
  }
  saveTheme(state.theme);
}

function applyAccent(accentKey) {
  const chosen = ACCENT_OPTIONS[accentKey] || ACCENT_OPTIONS.blue;
  state.accent = accentKey in ACCENT_OPTIONS ? accentKey : "blue";
  document.body.style.setProperty("--accent", chosen.accent);
  document.body.style.setProperty("--accent-soft", chosen.soft);
  saveAccent(state.accent);
}

function clearPreview() {
  els.previewType.textContent = "None";
  els.previewMeta.textContent = "Select a file to preview.";
  els.previewBody.textContent = "";
  els.previewBody.classList.remove("pdf-preview");
  els.previewBody.classList.remove("preview-unsupported");
  state.selectedFileFullPath = "";
  updatePathText();
}

function updateMultiSendBar() {
  if (!els.multiSendBar || !els.multiSendText || !els.multiSendBtn) {
    return;
  }
  const count = state.selectedFiles.size;
  if (count <= 1) {
    els.multiSendBar.classList.add("hidden");
    return;
  }
  els.multiSendText.textContent = `${count} files selected`;
  els.multiSendBtn.textContent = `Send (${count}) files to site`;
  els.multiSendBar.classList.remove("hidden");
}

function clearMultiSelection() {
  state.selectedFiles.clear();
  state.lastSelectedIndex = -1;
  updateMultiSendBar();
  applySelectionStyles();
}

function applySelectionStyles() {
  if (!els.fileList) {
    return;
  }
  const cards = els.fileList.querySelectorAll(".file-card[data-path]");
  cards.forEach((card) => {
    const path = card.dataset.path;
    const isActive = Boolean(path && (state.selectedFiles.has(path) || state.selectedFilePath === path));
    card.classList.toggle("active", isActive);
  });
}

function toggleSelection(entry, idx, event) {
  if (entry.type !== "file") {
    clearMultiSelection();
    return false;
  }

  const isMulti = event?.ctrlKey || event?.metaKey || event?.shiftKey;
  if (!isMulti) {
    state.selectedFiles.clear();
    state.selectedFiles.add(entry.relative_path);
    state.lastSelectedIndex = idx;
    updateMultiSendBar();
    applySelectionStyles();
    return true;
  }

  if (event.shiftKey && state.lastSelectedIndex !== -1) {
    const entries = getFilteredEntries().filter((item) => item.type === "file");
    const lastEntry = entries[state.lastSelectedIndex];
    const currentEntry = entries.find((item) => item.relative_path === entry.relative_path);
    if (lastEntry && currentEntry) {
      const lastIndex = entries.indexOf(lastEntry);
      const currentIndex = entries.indexOf(currentEntry);
      const [start, end] = lastIndex < currentIndex ? [lastIndex, currentIndex] : [currentIndex, lastIndex];
      for (let i = start; i <= end; i += 1) {
        state.selectedFiles.add(entries[i].relative_path);
      }
      updateMultiSendBar();
      applySelectionStyles();
      return true;
    }
  }

  if (state.selectedFiles.has(entry.relative_path)) {
    state.selectedFiles.delete(entry.relative_path);
  } else {
    state.selectedFiles.add(entry.relative_path);
  }
  state.lastSelectedIndex = idx;
  updateMultiSendBar();
  applySelectionStyles();
  return true;
}

function sendSelectedFilesToActiveTab() {
  const selected = state.entries.filter((entry) => state.selectedFiles.has(entry.relative_path));
  if (selected.length === 0) {
    return;
  }

  setStatus(`Sending ${selected.length} files to active tab...`);
  chrome.runtime.sendMessage(
    {
      type: "OPENTOCHROME_SEND_TO_ACTIVE_TAB",
      files: selected.map((entry) => ({
        serverUrl: state.serverUrl,
        root: state.currentRoot,
        path: entry.relative_path,
        name: entry.name,
      })),
    },
    (response) => {
      if (chrome.runtime.lastError) {
        setStatus(`Send failed: ${chrome.runtime.lastError.message}`, true);
        return;
      }
      if (response?.ok) {
        setStatus(`Sent ${selected.length} files to site`);
      } else {
        setStatus(`Send failed: ${response?.error || "Unknown error"}`, true);
      }
    },
  );
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

function updatePathText() {
  if (!els.pathText) {
    return;
  }

  if (state.viewMode === "home") {
    els.pathText.textContent = "Home";
    els.pathText.title = "Home";
    return;
  }

  const root = state.roots.find((r) => r.id === state.currentRoot);
  const rootPath = root ? root.path : "";
  const base = rootPath ? rootPath.replace(/\\/g, "/") : "";
  const relative = state.currentPath ? state.currentPath.replace(/\\/g, "/") : "";
  const folderPath = relative ? `${base}/${relative}` : base || "";

  if (state.selectedFileFullPath) {
    els.pathText.textContent = state.selectedFileFullPath;
    els.pathText.title = state.selectedFileFullPath;
    return;
  }

  const display = folderPath || root?.label || "Root";
  els.pathText.textContent = display;
  els.pathText.title = display;
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

  const fileEntries = entries.filter((entry) => entry.type === "file");

  entries.forEach((entry, index) => {
    const card = document.createElement("li");
    card.className = "file-card";
    if (entry.type === "file") {
      card.dataset.path = entry.relative_path;
    }
    const isSelected = entry.type === "file" && state.selectedFiles.has(entry.relative_path);
    if (entry.type === "file" && (state.selectedFilePath === entry.relative_path || isSelected)) {
      card.classList.add("active");
    }

    const typeForIcon = entry.type === "file" && isImageFile(entry.name) ? "image" : entry.type;
    card.innerHTML = `
      <div class="file-icon-wrap">${iconSvg(typeForIcon)}</div>
      <div class="file-name">${entry.name}</div>
      <div class="file-meta">${entry.type === "directory" ? "Folder" : humanSize(entry.size)}</div>
    `;

    card.addEventListener("click", (event) => {
      if (entry.type === "directory") {
        openLocation(state.currentRoot, entry.relative_path, true);
        clearMultiSelection();
      } else {
        const fileIndex = fileEntries.findIndex((item) => item.relative_path === entry.relative_path);
        const didSelect = toggleSelection(entry, fileIndex, event);
        if (didSelect && state.selectedFiles.size === 1) {
          previewFile(entry);
        } else if (state.selectedFiles.size > 1) {
          els.previewType.textContent = "Multiple";
          els.previewBody.classList.remove("pdf-preview");
          els.previewBody.classList.add("preview-unsupported");
          els.previewBody.textContent = "Multiple files selected. Use the Send button.";
          updatePathText();
        } else {
          updatePathText();
        }
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
      card.addEventListener("dragenter", () => {
        if (!state.selectedFiles.has(entry.relative_path)) {
          state.selectedFiles.clear();
          state.selectedFiles.add(entry.relative_path);
          updateMultiSendBar();
          renderFileList();
        }
      });
      card.addEventListener("dragstart", (event) => {
        if (!event.dataTransfer) return;
        const selectedEntries = state.selectedFiles.size > 1 && state.selectedFiles.has(entry.relative_path)
          ? state.entries.filter((item) => state.selectedFiles.has(item.relative_path))
          : [entry];
        const payloadFiles = selectedEntries.map((item) => ({
          serverUrl: state.serverUrl,
          root: state.currentRoot,
          path: item.relative_path,
          name: item.name,
          downloadUrl: downloadUrl(item.relative_path),
        }));
        const payload = { serverUrl: state.serverUrl, files: payloadFiles };
        const label = payloadFiles.length === 1 ? payloadFiles[0].name : `${payloadFiles.length} files`;

        event.dataTransfer.effectAllowed = "copy";
        const firstUrl = payloadFiles[0]?.downloadUrl;
        if (firstUrl) {
          event.dataTransfer.setData("DownloadURL", `application/octet-stream:${payloadFiles[0].name}:${firstUrl}`);
          event.dataTransfer.setData("text/uri-list", firstUrl);
        }
        event.dataTransfer.setData(BRIDGE_PAYLOAD_TYPE, JSON.stringify(payload));
        event.dataTransfer.setData("text/plain", `${BRIDGE_TEXT_PREFIX}${JSON.stringify(payload)}`);
        chrome.runtime.sendMessage({ type: "OPENTOCHROME_DRAG_ARM", files: payload.files });
        setStatus(`Dragging ${label} to website upload area...`);
      });

      card.addEventListener("dragend", () => {
        chrome.runtime.sendMessage({ type: "OPENTOCHROME_DRAG_CLEAR" });
      });
    }

    els.fileList.appendChild(card);
  });

  applySelectionStyles();
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
}

async function openHome(addHistory) {
  state.viewMode = "home";
  state.selectedFilePath = "";
  state.selectedFileFullPath = "";
  clearMultiSelection();
  clearPreview();
  updatePathText();
  renderFileList();
  setStatus(`Home: ${getFilteredRoots().length} path link(s)`);
  saveLastLocation("home", "", "");
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
    state.selectedFileFullPath = "";
    clearMultiSelection();
    renderFileList();
    updatePathText();
    saveLastLocation("browse", state.currentRoot, state.currentPath);
    if (addHistory) {
      pushHistory({ mode: "browse", root: state.currentRoot, path: state.currentPath });
    }
    setStatus(`Loaded ${getFilteredEntries().length} item(s)`);
  } catch (error) {
    state.entries = [];
    renderFileList();
    updatePathText();
    setStatus(`Cannot browse from ${state.serverUrl}`, true);
    console.error(error);
  }
}

async function previewFile(entry) {
  state.selectedFilePath = entry.relative_path;
  state.selectedFileFullPath = entry.full_path || "";
  renderFileList();
  els.previewMeta.textContent = entry.full_path;
  updatePathText();

  if (isPdfFile(entry.name)) {
    els.previewType.textContent = "PDF";
    els.previewBody.classList.add("pdf-preview");
    els.previewBody.classList.remove("preview-unsupported");
    const url = downloadUrl(entry.relative_path);
    els.previewBody.innerHTML = `<iframe class="preview-embed" src="${url}" title="${entry.name}"></iframe>`;
    setStatus(`PDF preview loaded: ${entry.name}`);
    return;
  }

  els.previewBody.classList.remove("pdf-preview");
  els.previewBody.classList.remove("preview-unsupported");

  if (isImageFile(entry.name)) {
    els.previewType.textContent = "Image";
    els.previewBody.innerHTML = `<img class="preview-image" src="${downloadUrl(entry.relative_path)}" alt="${entry.name}" />`;
    setStatus(`Image preview loaded: ${entry.name}`);
    return;
  }

  if (isTextFile(entry.name)) {
    setStatus(`Previewing ${entry.name}...`);
    try {
      const data = await apiFetch(
        `/api/preview?root=${encodeURIComponent(state.currentRoot)}&path=${encodeURIComponent(entry.relative_path)}`,
      );
      els.previewType.textContent = "Text";
      els.previewBody.textContent = data.content || "";
      setStatus(`Preview loaded: ${entry.name}`);
      return;
    } catch {
      els.previewType.textContent = "Unsupported";
      els.previewBody.classList.add("preview-unsupported");
      els.previewBody.textContent = "File type not supported for preview.";
      setStatus(`Preview unavailable: ${entry.name}`);
      return;
    }
  }

  els.previewType.textContent = "Unsupported";
  els.previewBody.classList.add("preview-unsupported");
  els.previewBody.textContent = "File type not supported for preview.";
  setStatus(`Preview unavailable: ${entry.name}`);
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

function applySearch(query) {
  state.searchQuery = query.trim();
  renderFileList();
  if (state.viewMode === "home") {
    setStatus(`Home: ${getFilteredRoots().length} path link(s)`);
  } else {
    setStatus(`Loaded ${getFilteredEntries().length} item(s)`);
  }
}

function openSettingsPage() {
  if (chrome.runtime.openOptionsPage) {
    chrome.runtime.openOptionsPage();
    return;
  }
  chrome.tabs.create({ url: chrome.runtime.getURL("settings.html") });
}

function buildCopyPathText() {
  if (state.viewMode === "home") {
    return "Home";
  }
  if (state.selectedFileFullPath) {
    return state.selectedFileFullPath;
  }
  const root = state.roots.find((r) => r.id === state.currentRoot);
  const rootPath = root ? root.path : "";
  if (!rootPath) {
    return state.currentPath || root?.label || "";
  }
  if (!state.currentPath) {
    return rootPath;
  }
  return `${rootPath.replace(/\\/g, "/")}/${state.currentPath.replace(/\\/g, "/")}`;
}

async function copyPath() {
  const text = buildCopyPathText();
  if (!text) {
    return;
  }
  try {
    await navigator.clipboard.writeText(text);
    setStatus("Path copied to clipboard");
  } catch (error) {
    setStatus("Copy failed. Grant clipboard permissions.", true);
    console.error(error);
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
  const settings = await loadSettings();
  state.serverUrl = settings.serverUrl;
  state.lastLocation = {
    mode: settings.lastMode === "browse" ? "browse" : "home",
    root: settings.lastRootId || "",
    path: settings.lastPath || "",
  };
  setPreviewVisibility(settings.previewHidden);
  applyTheme(settings.theme || "light");
  applyAccent(settings.accent || "blue");
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
  els.configBtn.addEventListener("click", openSettingsPage);
  if (els.themeToggleBtn) {
    els.themeToggleBtn.addEventListener("click", () =>
      applyTheme(state.theme === "dark" ? "light" : "dark"),
    );
  }
  if (els.copyPathBtn) {
    els.copyPathBtn.addEventListener("click", copyPath);
  }
  if (els.multiSendBtn) {
    els.multiSendBtn.addEventListener("click", sendSelectedFilesToActiveTab);
  }
  els.searchInput.addEventListener("input", () => applySearch(els.searchInput.value));

  await fetchRoots();
  const hasLastRoot = state.lastLocation.root && state.roots.some((root) => root.id === state.lastLocation.root);
  if (state.lastLocation.mode === "browse" && hasLastRoot) {
    await openLocation(state.lastLocation.root, state.lastLocation.path || "", true);
  } else {
    await openHome(true);
  }
  renderHistoryButtons();
}

init();
