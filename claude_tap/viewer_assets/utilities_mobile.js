
/* ─── Utilities ─── */
function esc(s) { if (!s) return ''; return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;'); }
function fmtDuration(ms) { return ms < 1000 ? ms + 'ms' : (ms / 1000).toFixed(1) + 's'; }
function fmtChars(n) { return n >= 1000 ? (n / 1000).toFixed(1) + 'k' : String(n); }

/* ─── Keyboard nav ─── */
document.addEventListener('keydown', ev => {
  if ((ev.metaKey || ev.ctrlKey) && ev.key.toLowerCase() === 'f') {
    ev.preventDefault();
    openGlobalSearch();
    return;
  }
  if (globalSearchState.open) {
    if (ev.key === 'Escape') {
      ev.preventDefault();
      closeGlobalSearch();
      return;
    }
    if (ev.key === 'Enter') {
      ev.preventDefault();
      navigateGlobalSearch(ev.shiftKey ? -1 : 1);
      return;
    }
  }
  // Ctrl/Cmd+G: jump to turn number
  if ((ev.metaKey || ev.ctrlKey) && ev.key.toLowerCase() === 'g') {
    ev.preventDefault();
    promptJumpToTurn();
    return;
  }
  const tag = ev.target?.tagName;
  if (tag === 'INPUT' || tag === 'TEXTAREA' || ev.target?.isContentEditable) return;
  if (!visualOrder.length) return;
  if (ev.key === 'ArrowDown' || ev.key === 'j') { ev.preventDefault(); visualNavigate(1); }
  if (ev.key === 'ArrowUp' || ev.key === 'k') { ev.preventDefault(); visualNavigate(-1); }
  if (ev.key === 'Home') { ev.preventDefault(); selectEntry(visualOrder[0]); }
  if (ev.key === 'End') { ev.preventDefault(); selectEntry(visualOrder[visualOrder.length - 1]); }
  if (ev.key === 'PageDown') { ev.preventDefault(); visualNavigate(10); }
  if (ev.key === 'PageUp') { ev.preventDefault(); visualNavigate(-10); }
});

function promptJumpToTurn() {
  if (!filtered.length) return;
  const input = prompt('Jump to turn number:');
  if (!input) return;
  const turnNum = parseInt(input, 10);
  if (isNaN(turnNum)) return;
  // Find the filtered entry with matching turn number
  const idx = filtered.findIndex(e => Number(displayTurnValue(e)) === turnNum);
  if (idx >= 0) {
    selectEntry(idx);
  } else {
    // Find closest turn
    let closestIdx = 0, closestDist = Infinity;
    filtered.forEach((e, i) => {
      const dist = Math.abs((Number(displayTurnValue(e)) || 0) - turnNum);
      if (dist < closestDist) { closestDist = dist; closestIdx = i; }
    });
    selectEntry(closestIdx);
  }
}

/* ─── Turn deep links (#turn-<label>) ───
   The viewer URL fragment addresses a turn by its sidebar label so a link
   like /dashboard/session/<id>#turn-15 (or #turn-2.2 for websocket
   sub-responses) opens directly on that turn. Selection changes are written
   back with replaceState, and a framed viewer forwards the hash to the
   embedding dashboard so the address bar stays copyable. */
const TURN_HASH_MESSAGE_TYPE = 'claude-tap:turn-hash';
let pendingTurnHashLabel = turnHashLabel(window.location.hash) || null;

function turnHashLabel(hash) {
  const match = /^#turn-(.+)$/.exec(String(hash || ''));
  if (!match) return '';
  try {
    return decodeURIComponent(match[1]);
  } catch (e) {
    return match[1];
  }
}

function findEntryIdxByTurnLabel(list, label) {
  if (!label || !Array.isArray(list)) return -1;
  return list.findIndex(e => String(displayTurnLabel(e)) === String(label));
}

function applyTurnHashSelection(label) {
  if (!label) return false;
  let idx = findEntryIdxByTurnLabel(filtered, label);
  if (idx < 0) {
    const entryIdx = findEntryIdxByTurnLabel(entries, label);
    if (entryIdx < 0) return false;
    // The target is hidden by the default path filter (e.g. an auxiliary
    // capture) — widen the filter the same way global search does.
    activePaths.add(getPath(entries[entryIdx]));
    applyFilter(true);
    idx = findEntryIdxByTurnLabel(filtered, label);
    if (idx < 0) return false;
  }
  selectEntry(idx);
  return true;
}

function applyInitialTurnHash() {
  const label = pendingTurnHashLabel;
  pendingTurnHashLabel = null;
  if (label) applyTurnHashSelection(label);
}

function updateTurnHash(entry) {
  if (pendingTurnHashLabel) return; // an incoming deep link is not applied yet
  const label = displayTurnLabel(entry);
  if (label === '?') return;
  const hash = '#turn-' + encodeURIComponent(String(label));
  if (window.location.hash === hash) return;
  try {
    history.replaceState(null, '', window.location.pathname + window.location.search + hash);
  } catch (e) {
    return;
  }
  if (window.parent !== window && /^https?:$/.test(window.location.protocol)) {
    try {
      window.parent.postMessage({ type: TURN_HASH_MESSAGE_TYPE, hash }, window.location.origin);
    } catch (e) {
      /* embedding page may be unreachable; the local hash is already set */
    }
  }
}

window.addEventListener('hashchange', () => {
  const label = turnHashLabel(window.location.hash);
  if (label) applyTurnHashSelection(label);
});

/* ─── Mobile sidebar toggle (R1) ─── */
function isMobile() { return window.matchMedia('(max-width: 768px)').matches; }

function mobileShowDetail() {
  if (!isMobile()) return;
  const sidebarWrap = document.getElementById('sidebar-wrap');
  const detail = document.getElementById('detail');
  const backBtn = document.getElementById('mobile-back-btn');
  const navBar = document.getElementById('mobile-nav-bar');
  if (sidebarWrap) sidebarWrap.classList.add('mobile-hidden');
  if (detail) detail.classList.add('mobile-fullwidth');
  if (backBtn) backBtn.style.display = '';
  if (navBar) navBar.style.display = '';
  updateMobileNav();
}

function mobileShowSidebar() {
  const sidebarWrap = document.getElementById('sidebar-wrap');
  const detail = document.getElementById('detail');
  const backBtn = document.getElementById('mobile-back-btn');
  const navBar = document.getElementById('mobile-nav-bar');
  if (sidebarWrap) sidebarWrap.classList.remove('mobile-hidden');
  if (detail) detail.classList.remove('mobile-fullwidth');
  if (backBtn) backBtn.style.display = 'none';
  if (navBar) navBar.style.display = 'none';
}

function updateMobileNav() {
  const prevBtn = document.getElementById('mobile-prev-btn');
  const nextBtn = document.getElementById('mobile-next-btn');
  const pos = document.getElementById('mobile-nav-pos');
  if (!prevBtn || !nextBtn || !pos) return;
  const total = visualOrder.length;
  if (total === 0) {
    prevBtn.disabled = true;
    nextBtn.disabled = true;
    pos.textContent = '';
    return;
  }
  const vPos = visualOrder.indexOf(activeIdx);
  prevBtn.disabled = vPos <= 0;
  nextBtn.disabled = vPos >= total - 1;
  pos.textContent = (vPos + 1) + ' / ' + total;
}

function mobilePrev() {
  visualNavigate(-1);
}

function mobileNext() {
  visualNavigate(1);
}
