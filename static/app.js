// Modal management
function openModal(id) {
  document.getElementById(id).classList.add('open');
}

function closeModal(id) {
  document.getElementById(id).classList.remove('open');
}

// Close modal on overlay click
document.addEventListener('click', (e) => {
  if (e.target.classList.contains('modal-overlay')) {
    e.target.classList.remove('open');
  }
});

// Close modal on Escape
document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') {
    document.querySelectorAll('.modal-overlay.open').forEach(m => m.classList.remove('open'));
  }
});

// Run audit for a framework via API
async function runAudit(framework) {
  const btn = document.getElementById(`audit-btn-${framework}`);
  if (btn) {
    btn.disabled = true;
    btn.textContent = 'Running…';
  }
  try {
    const res = await fetch(`/api/audit/run/${framework}`, { method: 'POST' });
    const data = await res.json();
    showToast(`Audit complete — ${framework}: Score ${data.average_score} (${data.grade})`, 'success');
    setTimeout(() => location.reload(), 1500);
  } catch (err) {
    showToast('Audit failed: ' + err.message, 'error');
    if (btn) { btn.disabled = false; btn.textContent = 'Run Audit'; }
  }
}

// Simple toast notification
function showToast(message, type = 'info') {
  const toast = document.createElement('div');
  toast.className = `toast toast-${type}`;
  toast.textContent = message;
  toast.style.cssText = `
    position: fixed; bottom: 24px; right: 24px;
    background: var(--bg2); border: 1px solid var(--border);
    color: var(--text); padding: 12px 18px; border-radius: 8px;
    font-size: 13px; z-index: 9999; box-shadow: var(--shadow);
    max-width: 360px; animation: slideIn 0.2s ease;
  `;
  if (type === 'success') toast.style.borderColor = 'var(--success)';
  if (type === 'error') toast.style.borderColor = 'var(--danger)';

  document.body.appendChild(toast);
  setTimeout(() => toast.remove(), 4000);
}

// Confirm delete actions
function confirmDelete(form) {
  return confirm('Delete this item? This cannot be undone.');
}

// Filter table rows by search input
function filterTable(inputId, tableId) {
  const input = document.getElementById(inputId);
  if (!input) return;
  input.addEventListener('input', () => {
    const q = input.value.toLowerCase();
    const rows = document.querySelectorAll(`#${tableId} tbody tr`);
    rows.forEach(row => {
      row.style.display = row.textContent.toLowerCase().includes(q) ? '' : 'none';
    });
  });
}

// Animate score bars on load
document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('.progress-fill[data-pct]').forEach(el => {
    const pct = parseInt(el.dataset.pct);
    el.style.width = '0%';
    requestAnimationFrame(() => {
      el.style.transition = 'width 0.6s ease';
      el.style.width = pct + '%';
    });
    const colorClass = pct >= 75 ? 'success' : pct >= 50 ? 'warning' : 'danger';
    el.classList.add(colorClass);
  });

  // Auto-connect inline filter inputs
  const searchInput = document.getElementById('table-search');
  if (searchInput) {
    searchInput.addEventListener('input', () => {
      const q = searchInput.value.toLowerCase();
      document.querySelectorAll('.filterable-row').forEach(row => {
        row.style.display = row.textContent.toLowerCase().includes(q) ? '' : 'none';
      });
    });
  }
});

// Copy code blocks to clipboard
document.querySelectorAll('pre code').forEach(block => {
  const btn = document.createElement('button');
  btn.textContent = 'Copy';
  btn.className = 'btn btn-sm btn-secondary';
  btn.style.cssText = 'position:absolute;top:8px;right:8px;';
  block.parentElement.style.position = 'relative';
  block.parentElement.appendChild(btn);
  btn.addEventListener('click', () => {
    navigator.clipboard.writeText(block.textContent).then(() => {
      btn.textContent = 'Copied!';
      setTimeout(() => (btn.textContent = 'Copy'), 2000);
    });
  });
});
