chrome.runtime.onInstalled.addListener(() => {
  chrome.sidePanel.setPanelBehavior({ openPanelOnActionClick: true });
});

chrome.runtime.onStartup.addListener(() => {
  chrome.sidePanel.setPanelBehavior({ openPanelOnActionClick: true });
});

const pendingDragByTab = new Map();
const PENDING_TTL_MS = 20000;

function uint8ToBase64(bytes) {
  let binary = "";
  const chunkSize = 0x8000;
  for (let i = 0; i < bytes.length; i += chunkSize) {
    const chunk = bytes.subarray(i, i + chunkSize);
    binary += String.fromCharCode(...chunk);
  }
  return btoa(binary);
}

async function fetchFileAsPayload(fileRef) {
  const downloadUrl =
    fileRef.downloadUrl ||
    `${fileRef.serverUrl}/api/download?root=${encodeURIComponent(fileRef.root)}&path=${encodeURIComponent(fileRef.path)}`;

  const response = await fetch(downloadUrl);
  if (!response.ok) {
    throw new Error(`Failed to fetch ${fileRef.name}`);
  }

  const blob = await response.blob();
  const bytes = new Uint8Array(await blob.arrayBuffer());

  return {
    name: fileRef.name,
    type: blob.type || "application/octet-stream",
    bytesBase64: uint8ToBase64(bytes),
  };
}

async function sendFilesToActiveTab(files) {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!tab || typeof tab.id !== "number") {
    return { ok: false, error: "No active tab found" };
  }

  try {
    const payloadFiles = await Promise.all(files.map((f) => fetchFileAsPayload(f)));
    const response = await chrome.tabs.sendMessage(tab.id, {
      type: "OPENTOCHROME_INJECT_FILES",
      files: payloadFiles,
    });

    if (response?.ok) {
      return { ok: true, injected: response.injected || payloadFiles.length };
    }
    return { ok: false, error: response?.error || "Injection failed in page" };
  } catch (error) {
    return { ok: false, error: error?.message || "Could not inject into active tab" };
  }
}

async function getActiveTabId() {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!tab || typeof tab.id !== "number") {
    throw new Error("No active tab found");
  }
  return tab.id;
}

async function armPendingDrag(files) {
  const tabId = await getActiveTabId();
  const expiresAt = Date.now() + PENDING_TTL_MS;
  pendingDragByTab.set(tabId, { files, expiresAt });

  try {
    await chrome.tabs.sendMessage(tabId, {
      type: "OPENTOCHROME_PENDING_DRAG_ARMED",
      expiresAt,
    });
  } catch {
    // Content script may not be ready; drop handler can still consume from background.
  }

  return { ok: true };
}

async function clearPendingDrag() {
  const tabId = await getActiveTabId();
  pendingDragByTab.delete(tabId);
  return { ok: true };
}

function consumePendingDrag(senderTabId) {
  if (typeof senderTabId !== "number") {
    return { ok: false, error: "Missing sender tab id" };
  }

  const entry = pendingDragByTab.get(senderTabId);
  if (!entry) {
    return { ok: false, error: "No pending drag" };
  }

  if (Date.now() > entry.expiresAt) {
    pendingDragByTab.delete(senderTabId);
    return { ok: false, error: "Pending drag expired" };
  }

  pendingDragByTab.delete(senderTabId);
  return { ok: true, files: entry.files };
}

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message?.type === "OPENTOCHROME_SEND_TO_ACTIVE_TAB") {
    sendFilesToActiveTab(message.files || [])
      .then((result) => sendResponse(result))
      .catch((error) => sendResponse({ ok: false, error: error?.message || "Unexpected error" }));
    return true;
  }

  if (message?.type === "OPENTOCHROME_DRAG_ARM") {
    armPendingDrag(message.files || [])
      .then((result) => sendResponse(result))
      .catch((error) => sendResponse({ ok: false, error: error?.message || "Unexpected error" }));
    return true;
  }

  if (message?.type === "OPENTOCHROME_DRAG_CLEAR") {
    clearPendingDrag()
      .then((result) => sendResponse(result))
      .catch((error) => sendResponse({ ok: false, error: error?.message || "Unexpected error" }));
    return true;
  }

  if (message?.type === "OPENTOCHROME_DRAG_CONSUME") {
    sendResponse(consumePendingDrag(sender.tab?.id));
    return false;
  }

  return false;
});
