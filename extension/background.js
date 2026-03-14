// Track URL-level state to prevent repeated submissions for in-flight items.
const localUrlState = new Map();

const DEFAULT_SERVER_HOST = '127.0.0.1';
const DEFAULT_SERVER_PORT = 5000;
const POLL_INTERVAL_MS = 1200;

let progressTimer = null;

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

async function setDotIndicator(status) {
  // Badge is displayed at top-right and acts as the requested status dot.
  const colorByStatus = {
    queued: '#f4c430',
    downloading: '#f4c430',
    completed: '#2e8b57'
  };

  if (!status || status === 'idle' || status === 'failed') {
    await chrome.action.setBadgeText({ text: '' });
    await chrome.action.setTitle({ title: 'Queue YouTube audio download' });
    return;
  }

  await chrome.action.setBadgeText({ text: '●' });
  await chrome.action.setBadgeBackgroundColor({ color: colorByStatus[status] || '#f4c430' });
  await chrome.action.setTitle({ title: `Downloads status: ${status}` });
}

async function refreshGlobalIndicator() {
  try {
    const progress = await fetchOverallProgress();
    await setDotIndicator(progress.status);
  } catch (error) {
    console.error('Progress polling error:', error);
  }
}

function startGlobalProgressPolling() {
  if (progressTimer) {
    return;
  }

  progressTimer = setInterval(refreshGlobalIndicator, POLL_INTERVAL_MS);
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
    // Immediate visual feedback as requested.
    localUrlState.set(url, 'queued');
    await setDotIndicator('queued');

    const response = await enqueueUrl(url);

    if (response.source_status === 'queued' || response.source_status === 'downloading') {
      localUrlState.set(url, response.source_status);
    }

    startGlobalProgressPolling();
    await refreshGlobalIndicator();
  } catch (error) {
    console.error('Queue request failed:', error);
  }
});

// Keep global status dot refreshed on lifecycle events.
chrome.runtime.onStartup.addListener(startGlobalProgressPolling);
chrome.runtime.onInstalled.addListener(startGlobalProgressPolling);
chrome.tabs.onActivated.addListener(async () => {
  await refreshGlobalIndicator();
});
chrome.tabs.onUpdated.addListener(async (_tabId, changeInfo) => {
  if (changeInfo.status === 'complete') {
    await refreshGlobalIndicator();
  }
});
