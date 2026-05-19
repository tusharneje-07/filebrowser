const DEFAULT_SERVER = "http://127.0.0.1:17650";

const els = {
  serverUrl: document.getElementById("serverUrl"),
  saveBtn: document.getElementById("saveSettingsBtn"),
  closeBtn: document.getElementById("closeSettingsBtn"),
  previewToggle: document.getElementById("previewToggle"),
  previewLabel: document.getElementById("previewLabel"),
  accentGroup: document.getElementById("accentGroup"),
  saveStatus: document.getElementById("saveStatus"),
};

const state = {
  serverUrl: DEFAULT_SERVER,
  previewHidden: false,
  theme: "light",
  accent: "blue",
};

function setPreviewToggle(hidden) {
  const isVisible = !hidden;
  els.previewToggle.setAttribute("aria-pressed", String(isVisible));
  els.previewLabel.textContent = isVisible ? "Visible" : "Hidden";
}

async function loadSettings() {
  return new Promise((resolve) => {
    chrome.storage.local.get(["serverUrl", "previewHidden", "theme", "accent"], (result) => {
      resolve({
        serverUrl: result.serverUrl || DEFAULT_SERVER,
        previewHidden: Boolean(result.previewHidden),
        theme: result.theme || "light",
        accent: result.accent || "blue",
      });
    });
  });
}

function setStatus(message) {
  if (!els.saveStatus) {
    return;
  }
  els.saveStatus.textContent = message;
}

function selectAccentButton(accentKey) {
  if (!els.accentGroup) {
    return;
  }
  els.accentGroup.querySelectorAll(".accent-swatch").forEach((btn) => {
    btn.classList.toggle("is-selected", btn.dataset.accent === accentKey);
  });
}

async function saveSettings() {
  const serverUrl = els.serverUrl.value.trim() || DEFAULT_SERVER;
  const previewHidden = !Boolean(els.previewToggle.getAttribute("aria-pressed") === "true");
  const theme = state.theme;
  const accent = state.accent;

  await new Promise((resolve) => {
    chrome.storage.local.set({ serverUrl, previewHidden, theme, accent }, () => resolve());
  });

  state.serverUrl = serverUrl;
  state.previewHidden = previewHidden;
  state.theme = theme;
  state.accent = accent;
  setPreviewToggle(previewHidden);
  setStatus("Saved successfully");
  setTimeout(() => setStatus(""), 2500);
}

function bindEvents() {
  const themeToggle = document.getElementById("settingsThemeToggle");
  const themeLabel = document.getElementById("settingsThemeLabel");

  if (themeToggle && themeLabel) {
    themeToggle.addEventListener("click", () => {
      state.theme = state.theme === "dark" ? "light" : "dark";
      document.body.classList.toggle("theme-dark", state.theme === "dark");
      themeToggle.setAttribute("aria-pressed", String(state.theme === "dark"));
      themeLabel.textContent = state.theme === "dark" ? "Dark" : "Light";
    });
  }

  if (els.accentGroup) {
    els.accentGroup.addEventListener("click", (event) => {
      const target = event.target;
      if (!(target instanceof HTMLButtonElement)) {
        return;
      }
      const accent = target.dataset.accent;
      if (!accent) {
        return;
      }
      state.accent = accent;
      selectAccentButton(accent);
    });
  }

  els.previewToggle.addEventListener("click", () => {
    const currentlyVisible = els.previewToggle.getAttribute("aria-pressed") === "true";
    setPreviewToggle(!currentlyVisible);
  });

  els.serverUrl.addEventListener("change", () => {
    state.serverUrl = els.serverUrl.value.trim() || DEFAULT_SERVER;
  });

  els.saveBtn.addEventListener("click", () => {
    saveSettings().catch(() => {
      setStatus("Save failed");
    });
  });

  els.closeBtn.addEventListener("click", () => window.close());
}

async function init() {
  const settings = await loadSettings();
  state.serverUrl = settings.serverUrl;
  state.previewHidden = settings.previewHidden;
  state.theme = settings.theme || "light";
  state.accent = settings.accent || "blue";

  els.serverUrl.value = state.serverUrl;
  setPreviewToggle(state.previewHidden);
  document.body.classList.toggle("theme-dark", state.theme === "dark");
  selectAccentButton(state.accent);
  setStatus("");

  const themeToggle = document.getElementById("settingsThemeToggle");
  const themeLabel = document.getElementById("settingsThemeLabel");
  if (themeToggle && themeLabel) {
    themeToggle.setAttribute("aria-pressed", String(state.theme === "dark"));
    themeLabel.textContent = state.theme === "dark" ? "Dark" : "Light";
  }

  bindEvents();
}

init();
