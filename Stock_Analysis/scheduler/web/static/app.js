/* ═══════════════════════════════════════════════════════
   Stock Analysis Scheduler - Web UI JavaScript
   ═══════════════════════════════════════════════════════ */

/**
 * Add a new watchlist via API
 */
function addWatchlist(event) {
  event.preventDefault();
  const form = event.target;
  const formData = new FormData(form);

  const tickers = formData.get('tickers')
    .split(',')
    .map(t => t.trim().toUpperCase())
    .filter(t => t.length > 0);

  const notifications = [];
  form.querySelectorAll('input[name="notifications"]:checked').forEach(cb => {
    notifications.push(cb.value);
  });

  const data = {
    name: formData.get('name').trim().toLowerCase().replace(/\s+/g, '_'),
    tickers: tickers,
    schedule: formData.get('schedule'),
    analysis_type: formData.get('analysis_type'),
    notifications: notifications,
    enabled: true,
  };

  fetch('/api/watchlists', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
    .then(resp => {
      if (!resp.ok) return resp.json().then(e => { throw new Error(e.detail); });
      return resp.json();
    })
    .then(() => {
      showMessage('Watchlist added successfully!', 'success');
      setTimeout(() => location.reload(), 500);
    })
    .catch(err => {
      showMessage(`Error: ${err.message}`, 'error');
    });

  return false;
}

/**
 * Toggle watchlist enabled/disabled
 */
function toggleWatchlist(name, enabled) {
  fetch(`/api/watchlists/${name}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ enabled: enabled }),
  })
    .then(resp => {
      if (!resp.ok) throw new Error('Failed');
      location.reload();
    })
    .catch(err => showMessage(`Error: ${err.message}`, 'error'));
}

/**
 * Delete a watchlist
 */
function deleteWatchlist(name) {
  if (!confirm(`Delete watchlist "${name}"?`)) return;

  fetch(`/api/watchlists/${name}`, { method: 'DELETE' })
    .then(resp => {
      if (!resp.ok) throw new Error('Failed');
      const row = document.getElementById(`row-${name}`);
      if (row) row.remove();
      showMessage(`Watchlist "${name}" deleted.`, 'success');
    })
    .catch(err => showMessage(`Error: ${err.message}`, 'error'));
}

/**
 * Filter history table
 */
function filterHistory() {
  const watchlist = document.getElementById('filter-watchlist').value;
  const url = `/partials/history-table?watchlist=${watchlist}`;
  htmx.ajax('GET', url, '#history-table-body');
}

/**
 * Show a temporary message
 */
function showMessage(text, type) {
  const el = document.getElementById('form-message');
  if (!el) return;

  const color = type === 'success' ? '#22c55e' : '#ef4444';
  const bg = type === 'success' ? '#f0fdf4' : '#fef2f2';
  el.innerHTML = `<div style="padding:10px;border-radius:6px;background:${bg};color:${color};font-size:13px;margin:10px 0">${text}</div>`;

  setTimeout(() => { el.innerHTML = ''; }, 5000);
}

/* ─── htmx Event Handlers ─── */
document.addEventListener('htmx:afterRequest', function(event) {
  // Handle API test results
  if (event.detail.target && event.detail.target.classList.contains('test-result')) {
    try {
      const data = JSON.parse(event.detail.xhr.responseText);
      const color = data.success ? '#22c55e' : '#ef4444';
      const bg = data.success ? '#f0fdf4' : '#fef2f2';
      event.detail.target.innerHTML =
        `<div style="padding:6px 10px;border-radius:6px;background:${bg};color:${color}">${data.message}</div>`;
    } catch (e) {
      // Non-JSON response, ignore
    }
  }

  // Handle manual run result
  if (event.detail.pathInfo && event.detail.pathInfo.requestPath.startsWith('/api/run/')) {
    try {
      const data = JSON.parse(event.detail.xhr.responseText);
      if (data.status === 'started') {
        event.detail.target.innerHTML = '<span class="text-warning pulse">Started...</span>';
      }
    } catch (e) {
      // ignore
    }
  }
});
