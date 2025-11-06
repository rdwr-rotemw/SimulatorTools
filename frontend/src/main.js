// Frontend scaffold entrypoint
// What to implement here:
// - Mount your SPA (React/Vue/etc.)
// - Add API client configuration that points to the backend

// Minimal, framework-free scaffold for quick manual testing and
// to serve as a starting point for a real SPA (React/Vue/Angular).

const API_URL = '/api'; // Use relative path so reverse proxy or docker-compose can route it.

function createRootContent() {
  return `
    <h1>Simulators Tools Frontend (Scaffold)</h1>
    <p>This is a minimal scaffold. Replace with your SPA (React/Vue/etc.).</p>
    <p>API base: <code>${API_URL}</code></p>
    <button id="health-btn">Check Backend Health</button>
    <pre id="health-output" style="white-space:pre-wrap;border:1px solid #ddd;padding:8px;margin-top:8px"></pre>
  `;
}

async function checkHealth() {
  const out = document.getElementById('health-output');
  out.textContent = 'Checking...';
  try {
    const resp = await fetch(`${API_URL}/health`);
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const data = await resp.json();
    out.textContent = JSON.stringify(data, null, 2);
  } catch (err) {
    out.textContent = `Error: ${err.message}`;
  }
}

function initApp() {
  const root = document.getElementById('root') || document.body;
  root.innerHTML = createRootContent();
  const btn = document.getElementById('health-btn');
  if (btn) btn.addEventListener('click', checkHealth);
}

window.addEventListener('DOMContentLoaded', () => {
  console.log('Simulators Tools frontend scaffold loaded');
  initApp();
});
