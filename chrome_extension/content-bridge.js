const PAYLOAD_TYPE = "application/x-file-browser-file";
const TEXT_PREFIX = "__FILE_BROWSER_PAYLOAD__::";
let pendingDragUntil = 0;

function hasBridgePayload(event) {
  const types = Array.from(event.dataTransfer?.types || []);
  return types.includes(PAYLOAD_TYPE) || types.includes("DownloadURL");
}

function parseDownloadUrl(raw) {
  if (!raw) {
    return null;
  }
  const match = raw.match(/^([^:]*):([^:]*):(.*)$/);
  if (!match) {
    return null;
  }
  return {
    mime: match[1],
    name: match[2],
    url: match[3],
  };
}

function readPayload(event) {
  const custom = event.dataTransfer.getData(PAYLOAD_TYPE);
  if (custom) {
    try {
      return JSON.parse(custom);
    } catch {
      return null;
    }
  }

  const text = event.dataTransfer.getData("text/plain");
  if (text && text.startsWith(TEXT_PREFIX)) {
    try {
      return JSON.parse(text.slice(TEXT_PREFIX.length));
    } catch {
      return null;
    }
  }

  const download = parseDownloadUrl(event.dataTransfer.getData("DownloadURL"));
  if (download?.url) {
    return {
      files: [
        {
          name: download.name || "file",
          downloadUrl: download.url,
        },
      ],
    };
  }

  return null;
}

function findFileInput(target) {
  if (!target) {
    return null;
  }

  if (target instanceof HTMLInputElement && target.type === "file" && !target.disabled) {
    return target;
  }

  if (target instanceof Element) {
    const inTarget = target.querySelector?.('input[type="file"]:not([disabled])');
    if (inTarget instanceof HTMLInputElement) {
      return inTarget;
    }

    const labelRoot = target.closest("label");
    if (labelRoot) {
      const inLabel = labelRoot.querySelector('input[type="file"]:not([disabled])');
      if (inLabel instanceof HTMLInputElement) {
        return inLabel;
      }
    }
  }

  const active = document.activeElement;
  if (active instanceof HTMLInputElement && active.type === "file" && !active.disabled) {
    return active;
  }

  const fallback = document.querySelector('input[type="file"]:not([disabled])');
  return fallback instanceof HTMLInputElement ? fallback : null;
}

async function buildDataTransferFromPayload(payload) {
  const dt = new DataTransfer();

  for (const item of payload.files || []) {
    const url =
      item.downloadUrl ||
      `${payload.serverUrl}/api/download?root=${encodeURIComponent(item.root)}&path=${encodeURIComponent(item.path)}`;
    const res = await fetch(url);
    if (!res.ok) {
      throw new Error(`Failed to fetch ${item.name}`);
    }
    const blob = await res.blob();
    const file = new File([blob], item.name, {
      type: blob.type || "application/octet-stream",
      lastModified: Date.now(),
    });
    dt.items.add(file);
  }

  return dt;
}

function dispatchDrop(target, dataTransfer) {
  const dragEnter = new DragEvent("dragenter", {
    bubbles: true,
    cancelable: true,
    dataTransfer,
  });
  target.dispatchEvent(dragEnter);

  const dragOver = new DragEvent("dragover", {
    bubbles: true,
    cancelable: true,
    dataTransfer,
  });
  target.dispatchEvent(dragOver);

  const drop = new DragEvent("drop", {
    bubbles: true,
    cancelable: true,
    dataTransfer,
  });
  target.dispatchEvent(drop);
}

function setInputFiles(input, dataTransfer) {
  input.files = dataTransfer.files;
  input.dispatchEvent(new Event("input", { bubbles: true }));
  input.dispatchEvent(new Event("change", { bubbles: true }));
}

function base64ToUint8Array(base64) {
  const binary = atob(base64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i += 1) {
    bytes[i] = binary.charCodeAt(i);
  }
  return bytes;
}

function findBestInput() {
  const direct = document.querySelector('input[type="file"]:not([disabled])');
  if (direct instanceof HTMLInputElement) {
    return direct;
  }

  const attachButton =
    document.querySelector('button[aria-label*="Attach" i]') ||
    document.querySelector('button[title*="Attach" i]') ||
    document.querySelector('[data-testid*="upload" i]');

  if (attachButton instanceof HTMLElement) {
    attachButton.click();
  }

  const afterClick = document.querySelector('input[type="file"]:not([disabled])');
  return afterClick instanceof HTMLInputElement ? afterClick : null;
}

async function injectFilesIntoPage(files) {
  const dt = new DataTransfer();

  for (const fileInfo of files) {
    const bytes = base64ToUint8Array(fileInfo.bytesBase64);
    const file = new File([bytes], fileInfo.name, {
      type: fileInfo.type || "application/octet-stream",
      lastModified: Date.now(),
    });
    dt.items.add(file);
  }

  const input = findBestInput();
  if (input) {
    setInputFiles(input, dt);
    return { ok: true, injected: dt.files.length };
  }

  const target = document.activeElement instanceof Element ? document.activeElement : document.body;
  dispatchDrop(target, dt);
  return { ok: true, injected: dt.files.length };
}

async function handleBridgeDrop(event) {
  let payload = readPayload(event);
  if (!payload && Date.now() < pendingDragUntil) {
    payload = await new Promise((resolve) => {
      chrome.runtime.sendMessage({ type: "OPENTOCHROME_DRAG_CONSUME" }, (response) => {
        if (chrome.runtime.lastError) {
          resolve(null);
          return;
        }
        if (response?.ok && Array.isArray(response.files)) {
          resolve({ files: response.files });
          return;
        }
        resolve(null);
      });
    });
  }

  if (!payload) {
    return;
  }

  pendingDragUntil = 0;
  event.preventDefault();
  event.stopPropagation();

  try {
    const dt = await buildDataTransferFromPayload(payload);

    const input = findFileInput(event.target);
    if (input) {
      setInputFiles(input, dt);
      return;
    }

    const target = event.target instanceof Element ? event.target : document.body;
    dispatchDrop(target, dt);
  } catch (err) {
    console.error("File Browser drop bridge error:", err);
  }
}

window.addEventListener(
  "dragover",
  (event) => {
    if (!hasBridgePayload(event) && Date.now() >= pendingDragUntil) {
      return;
    }
    event.preventDefault();
    if (event.dataTransfer) {
      event.dataTransfer.dropEffect = "copy";
    }
  },
  true,
);

window.addEventListener("drop", handleBridgeDrop, true);

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (message?.type === "OPENTOCHROME_PENDING_DRAG_ARMED") {
    pendingDragUntil = typeof message.expiresAt === "number" ? message.expiresAt : Date.now() + 15000;
    sendResponse({ ok: true });
    return false;
  }

  if (message?.type !== "OPENTOCHROME_INJECT_FILES") {
    return false;
  }

  injectFilesIntoPage(message.files || [])
    .then((result) => sendResponse(result))
    .catch((error) => sendResponse({ ok: false, error: error?.message || "Could not inject files" }));

  return true;
});
