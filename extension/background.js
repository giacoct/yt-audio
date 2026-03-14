// Track URL-level state to prevent repeated submissions for in-flight items.
const localUrlState = new Map();

const DEFAULT_SERVER_HOST = '127.0.0.1';
const DEFAULT_SERVER_PORT = 5000;
const POLL_INTERVAL_MS = 1200;

let progressTimer = null;
let cachedBaseIcon = null;

async function getServerBase() {
  const stored = await chrome.storage.local.get({
    serverHost: DEFAULT_SERVER_HOST,
    serverPort: DEFAULT_SERVER_PORT
  });
  return `http://${stored.serverHost}:${stored.serverPort}`;
}

function isYouTubeUrl(url) {
  try {
    const parsed = new URL(url);
    return /(youtube\.com|youtu\.be)$/.test(parsed.hostname);
  } catch {
    return false;
  }
}

async function enqueueUrl(url) {
  const serverBase = await getServerBase();
  const response = await fetch(`${serverBase}/url`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ url })
  });

  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    const message = body.error || `Server error: ${response.status}`;
    throw new Error(message);
  }
  return body;
}

async function fetchOverallProgress() {
  const serverBase = await getServerBase();
  const response = await fetch(`${serverBase}/progress`, { method: 'GET' });
  if (!response.ok) {
    throw new Error(`Progress request failed: ${response.status}`);
  }
  return response.json();
}

function getRingColor(status) {
  if (status === 'failed') {
    return '#d32f2f';
  }
  if (status === 'completed') {
    return '#2e8b57';
  }
  if (status === 'queued') {
    return '#808080';
  }
  return '#1e90ff';
}

async function loadBaseIcon() {
  if (cachedBaseIcon) {
    return cachedBaseIcon;
  }

  try {
    const response = await fetch(chrome.runtime.getURL('icons/icon128.png'));
    const blob = await response.blob();
    cachedBaseIcon = await createImageBitmap(blob);
  } catch (error) {
    console.warn('Base icon not available yet; drawing progress ring only.', error);
    cachedBaseIcon = null;
  }

  return cachedBaseIcon;
}

async function setCircularProgressIcon(progress) {
  const size = 128;
  const canvas = new OffscreenCanvas(size, size);
  const ctx = canvas.getContext('2d');
  const iconImage = await loadBaseIcon();

  // Draw base icon if present (user can manually provide icon files later).
  if (iconImage) {
    ctx.drawImage(iconImage, 0, 0, size, size);
  }

  if (!progress || progress.total === 0) {
    const imageData = ctx.getImageData(0, 0, size, size);
    await chrome.action.setIcon({ imageData: { 128: imageData } });
    await chrome.action.setTitle({ title: 'Queue YouTube audio download' });
    return;
  }

  const center = size / 2;
  const radius = 60;
  const thickness = 10;
  const pct = Math.max(0, Math.min(100, Number(progress.percent || 0)));
  const sweep = (Math.PI * 2 * pct) / 100;

  // Background ring.
  ctx.strokeStyle = 'rgba(120, 120, 120, 0.45)';
  ctx.lineWidth = thickness;
  ctx.beginPath();
  ctx.arc(center, center, radius, -Math.PI / 2, Math.PI * 1.5);
  ctx.stroke();

  // Progress ring.
  ctx.strokeStyle = getRingColor(progress.status);
  ctx.lineCap = 'round';
  ctx.lineWidth = thickness;
  ctx.beginPath();
  ctx.arc(center, center, radius, -Math.PI / 2, -Math.PI / 2 + sweep);
  ctx.stroke();

  const title = `Downloads: ${pct}% (${progress.completed + progress.failed}/${progress.total})`;
  await chrome.action.setTitle({ title });
  const imageData = ctx.getImageData(0, 0, size, size);
  await chrome.action.setIcon({ imageData: { 128: imageData } });
}

function startGlobalProgressPolling() {
  if (progressTimer) {
    return;
  }

  progressTimer = setInterval(async () => {
    try {
      const progress = await fetchOverallProgress();
      await setCircularProgressIcon(progress);
    } catch (error) {
      console.error('Progress polling error:', error);
    }
  }, POLL_INTERVAL_MS);
}

chrome.action.onClicked.addListener(async (tab) => {
  const url = tab.url || '';
  if (!isYouTubeUrl(url)) {
    return;
  }

  const currentState = localUrlState.get(url);
  if (currentState === 'queued' || currentState === 'downloading') {
    return;
  }

  try {
    localUrlState.set(url, 'queued');
    const response = await enqueueUrl(url);

    // Deduped URLs may return empty queued list; treat as still active if the source is in progress.
    if (response.source_status === 'queued' || response.source_status === 'downloading') {
      localUrlState.set(url, response.source_status);
    }

    startGlobalProgressPolling();
    const progress = await fetchOverallProgress();
    await setCircularProgressIcon(progress);
  } catch (error) {
    console.error('Queue request failed:', error);
  }
});

// Keep global progress ring refreshed on lifecycle events.
chrome.runtime.onStartup.addListener(startGlobalProgressPolling);
chrome.runtime.onInstalled.addListener(startGlobalProgressPolling);
chrome.tabs.onActivated.addListener(async () => {
  try {
    await setCircularProgressIcon(await fetchOverallProgress());
  } catch {
    // Ignore transient server errors.
  }
});
chrome.tabs.onUpdated.addListener(async (_tabId, changeInfo) => {
  if (changeInfo.status === 'complete') {
    try {
      await setCircularProgressIcon(await fetchOverallProgress());
    } catch {
      // Ignore transient server errors.
    }
  }
});
