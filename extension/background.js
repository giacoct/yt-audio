// Local Flask server base URL.
const SERVER_BASE = 'http://127.0.0.1:5000';

// Keep local state per URL to avoid repeated click spam.
const localUrlState = new Map();
const pollingTimers = new Map();

// Status-to-badge mapping; badge is the visual overlay on the extension icon.
const STATUS_UI = {
  idle: { text: '', color: '#00000000' },
  queued: { text: 'Q', color: '#808080' },
  downloading: { text: '↓', color: '#1e90ff' },
  completed: { text: '✓', color: '#2e8b57' },
  failed: { text: '!', color: '#d32f2f' }
};

// Lightweight pulse to make "downloading" visually active.
let pulseOn = false;
setInterval(() => {
  pulseOn = !pulseOn;
}, 700);

function isYouTubeUrl(url) {
  try {
    const parsed = new URL(url);
    return /(youtube\.com|youtu\.be)$/.test(parsed.hostname);
  } catch {
    return false;
  }
}

async function setActionStatus(tabId, status) {
  const ui = STATUS_UI[status] || STATUS_UI.idle;
  let color = ui.color;
  if (status === 'downloading') {
    color = pulseOn ? '#1e90ff' : '#0d47a1';
  }

  await chrome.action.setBadgeBackgroundColor({ tabId, color });
  await chrome.action.setBadgeText({ tabId, text: ui.text });
}

async function fetchServerStatus(url) {
  const endpoint = `${SERVER_BASE}/status?url=${encodeURIComponent(url)}`;
  const response = await fetch(endpoint, { method: 'GET' });
  if (!response.ok) {
    throw new Error(`Status request failed: ${response.status}`);
  }
  const body = await response.json();
  return body.status || 'idle';
}

async function enqueueUrl(url) {
  const response = await fetch(`${SERVER_BASE}/url`, {
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

function startPolling(tabId, url) {
  // Ensure only one timer per URL.
  if (pollingTimers.has(url)) {
    clearInterval(pollingTimers.get(url));
  }

  const timer = setInterval(async () => {
    try {
      const status = await fetchServerStatus(url);
      localUrlState.set(url, status);
      await setActionStatus(tabId, status);

      // Stop polling once terminal state reached.
      if (status === 'completed' || status === 'failed' || status === 'idle') {
        clearInterval(timer);
        pollingTimers.delete(url);
      }
    } catch (error) {
      console.error('Polling error:', error);
      localUrlState.set(url, 'failed');
      await setActionStatus(tabId, 'failed');
      clearInterval(timer);
      pollingTimers.delete(url);
    }
  }, 1500);

  pollingTimers.set(url, timer);
}

chrome.action.onClicked.addListener(async (tab) => {
  const tabId = tab.id;
  const url = tab.url || '';

  if (!tabId || !isYouTubeUrl(url)) {
    await setActionStatus(tabId, 'failed');
    return;
  }

  // Prevent repeated submits when same URL is already queued/downloading.
  const currentState = localUrlState.get(url);
  if (currentState === 'queued' || currentState === 'downloading') {
    return;
  }

  try {
    localUrlState.set(url, 'queued');
    await setActionStatus(tabId, 'queued');
    await enqueueUrl(url);
    startPolling(tabId, url);
  } catch (error) {
    console.error('Queue request failed:', error);
    localUrlState.set(url, 'failed');
    await setActionStatus(tabId, 'failed');
  }
});

// Keep icon consistent when switching tabs.
chrome.tabs.onActivated.addListener(async ({ tabId }) => {
  const tab = await chrome.tabs.get(tabId);
  const status = localUrlState.get(tab.url || '') || 'idle';
  await setActionStatus(tabId, status);
});

chrome.tabs.onUpdated.addListener(async (tabId, changeInfo, tab) => {
  if (changeInfo.status === 'complete') {
    const status = localUrlState.get(tab.url || '') || 'idle';
    await setActionStatus(tabId, status);
  }
});
