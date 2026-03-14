const statusEl = document.getElementById('status');
const form = document.getElementById('settingsForm');
const reloadBtn = document.getElementById('reloadBtn');

function getServerBase(host, port) {
  return `http://${host}:${port}`;
}

function setStatus(message, ok = true) {
  statusEl.textContent = message;
  statusEl.style.color = ok ? '#2e7d32' : '#c62828';
}

async function loadFromServer() {
  const stored = await chrome.storage.local.get({ serverHost: '127.0.0.1', serverPort: 5000 });
  const base = getServerBase(stored.serverHost, stored.serverPort);

  const response = await fetch(`${base}/settings`);
  if (!response.ok) {
    throw new Error(`HTTP ${response.status}`);
  }
  const data = await response.json();

  form.host.value = data.host;
  form.port.value = data.port;
  form.audio_quality.value = data.audio_quality;
  form.download_dir.value = data.download_dir;
  form.retries.value = data.retries;
  form.fragment_retries.value = data.fragment_retries;

  await chrome.storage.local.set({ serverHost: data.host, serverPort: Number(data.port) });
  setStatus('Loaded server settings.');
}

async function saveToServer(event) {
  event.preventDefault();

  const payload = {
    host: form.host.value.trim(),
    port: Number(form.port.value),
    audio_quality: String(form.audio_quality.value),
    download_dir: form.download_dir.value.trim(),
    retries: Number(form.retries.value),
    fragment_retries: Number(form.fragment_retries.value)
  };

  const base = getServerBase(payload.host, payload.port);
  const response = await fetch(`${base}/settings`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  });

  if (!response.ok) {
    throw new Error(`Save failed HTTP ${response.status}`);
  }

  await chrome.storage.local.set({ serverHost: payload.host, serverPort: payload.port });
  setStatus('Settings saved to server.');
}

form.addEventListener('submit', async (event) => {
  try {
    await saveToServer(event);
  } catch (error) {
    setStatus(`Failed to save settings: ${error.message}`, false);
  }
});

reloadBtn.addEventListener('click', async () => {
  try {
    await loadFromServer();
  } catch (error) {
    setStatus(`Failed to load settings: ${error.message}`, false);
  }
});

loadFromServer().catch((error) => setStatus(`Failed to load settings: ${error.message}`, false));
