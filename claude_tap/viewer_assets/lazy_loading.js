/* ─── Lazy loading infrastructure ─── */
const LAZY_THRESHOLD = 50;
let lazyMode = false;
let rawLines = null; // array of raw JSON strings, populated on first access
const entryCache = new Map(); // index -> parsed full entry
const remoteEntryPromises = new Map(); // index -> pending record fetch

function getRawLines() {
  if (rawLines) return rawLines;
  const el = document.getElementById('trace-raw');
  if (!el) return [];
  const text = el.textContent;
  // Free DOM node memory — we no longer need the script element
  el.remove();
  rawLines = text.split('\n').filter(l => l.trim());
  return rawLines;
}

function hasEmbeddedRawLines() {
  return !!rawLines || !!document.getElementById('trace-raw');
}

function buildStubEntry(meta, rawIdx) {
  // Build an entry object with the same shape as real entries so existing
  // sidebar rendering code works unchanged. Nested paths are constructed
  // to satisfy property access patterns (e.g. entry.request.body.model).
  const usage = {};
  if (meta.input_tokens) usage.input_tokens = meta.input_tokens;
  if (meta.output_tokens) usage.output_tokens = meta.output_tokens;
  const hasCacheCreate = meta.cache_creation_input_tokens !== undefined && meta.cache_creation_input_tokens !== null;
  if (meta.cache_read_input_tokens) {
    usage.cache_read_input_tokens = meta.cache_read_input_tokens;
    /* Infer cache embedding style from model name so the cache hit rate
       denominator is correct in lazy/dashboard mode.  Claude/Anthropic and
       Bedrock keep cache_read as a separate bucket; OpenAI/Gemini embed it. */
    const m = (meta.model || '').toLowerCase();
    usage._cache_read_in_input = !(hasCacheCreate || m.includes('claude') || m.includes('anthropic') || m.includes('bedrock'));
  }
  if (meta.cache_creation_input_tokens) usage.cache_creation_input_tokens = meta.cache_creation_input_tokens;

  // Build a minimal system field to support task fingerprinting
  const body = { model: meta.model || '' };
  if (meta.codex_app_session_id) {
    body.metadata = { codex_app_session_id: meta.codex_app_session_id };
  }
  if (typeof meta.request_generate === 'boolean') body.generate = meta.request_generate;
  if (meta.has_system && meta.sys_hint) {
    body.system = meta.sys_hint;
  }
  if (meta.tool_names && meta.tool_names.length) {
    body.tools = meta.tool_names.map(n => ({ name: n }));
  }

  // Build minimal response content for tool filter
  const respContent = [];
  if (meta.response_tool_names && meta.response_tool_names.length) {
    meta.response_tool_names.forEach(n => respContent.push({ type: 'tool_use', name: n }));
  }

  const responseBody = {
    usage: usage,
    content: respContent.length ? respContent : undefined,
    error: meta.error_message ? { message: meta.error_message } : undefined,
  };
  if (typeof meta.response_generate === 'boolean') responseBody.generate = meta.response_generate;
  if (meta.response_output_count) responseBody.output = Array.from({ length: meta.response_output_count }, () => ({}));

  return {
    _isStub: true,
    _rawIdx: rawIdx,
    _entry_index: rawIdx,
    turn: meta.turn,
    request_id: meta.request_id || '',
    timestamp: meta.timestamp || '',
    duration_ms: meta.duration_ms || 0,
    transport: meta.transport || '',
    _session_user_text: meta.session_user_text || '',
    request: {
      method: meta.method || '',
      path: meta.path || '',
      headers: meta.codex_app_session_id ? { 'x-codex-app-session-id': meta.codex_app_session_id } : {},
      body: body,
    },
    response: {
      status: meta.status || 0,
      body: responseBody,
    },
  };
}

function toolDisplayName(td) {
  if (!td || typeof td !== 'object') return '';
  const candidates = [
    td.name,
    td.function && typeof td.function === 'object' ? td.function.name : null,
    td.id,
    td.type
  ];
  for (const value of candidates) {
    if (typeof value === 'string' && value) return value;
  }
  return '';
}

function toolDescription(td) {
  if (!td || typeof td !== 'object') return '';
  const desc = td.description || (td.function && typeof td.function === 'object' ? td.function.description : '');
  return typeof desc === 'string' ? desc : '';
}

function toolSchema(td) {
  if (!td || typeof td !== 'object') return {};
  return td.input_schema || td.parameters || (td.function && typeof td.function === 'object' ? td.function.parameters : null) || {};
}

function getFullEntry(entry) {
  if (!entry._isStub) return entry;
  const idx = entry._rawIdx;
  if (entryCache.has(idx)) return entryCache.get(idx);
  const lines = getRawLines();
  if (idx < 0 || idx >= lines.length) return entry;
  try {
    const full = JSON.parse(lines[idx]);
    entryCache.set(idx, full);
    return full;
  } catch (e) {
    console.error('Failed to parse entry at index', idx, e);
    return entry;
  }
}

function shouldFetchRemoteEntry(entry) {
  return !!(entry && entry._isStub && TRACE_RECORDS_API && !hasEmbeddedRawLines());
}

function remoteRecordUrl(idx) {
  const sep = TRACE_RECORDS_API.includes('?') ? '&' : '?';
  return `${TRACE_RECORDS_API}${sep}offset=${encodeURIComponent(idx)}&limit=1`;
}

async function fetchRemoteEntry(entry) {
  if (!shouldFetchRemoteEntry(entry)) return getFullEntry(entry);
  const idx = entry._rawIdx;
  if (entryCache.has(idx)) return entryCache.get(idx);
  if (!remoteEntryPromises.has(idx)) {
    remoteEntryPromises.set(idx, fetch(remoteRecordUrl(idx))
      .then(async resp => {
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        const payload = await resp.json();
        const record = Array.isArray(payload.records) ? payload.records[0] : null;
        if (!record || typeof record !== 'object') return entry;
        entryCache.set(idx, record);
        return record;
      })
      .catch(err => {
        remoteEntryPromises.delete(idx);
        throw err;
      }));
  }
  return remoteEntryPromises.get(idx);
}

function withDisplayFields(full, entry) {
  return {
    ...full,
    _entry_index: entry._entry_index,
    display_turn: entry.display_turn,
    capture_turn: entry.capture_turn,
    record_index: entry.record_index,
    websocket_response_index: entry.websocket_response_index,
  };
}

function resolveEntryForDetail(entry) {
  if (!entry || !entry._isStub) return entry;
  return withDisplayFields(getFullEntry(entry), entry);
}

async function resolveEntryForDetailAsync(entry) {
  if (!entry || !entry._isStub) return entry;
  return withDisplayFields(await fetchRemoteEntry(entry), entry);
}

/* ─── Incremental detail rendering ───
   Heavy turns (e.g. merged Codex chains where every call re-serializes the
   full history) can produce megabytes of detail DOM whose style/layout pass
   blocks the main thread for seconds. Render only the head of long message
   lists eagerly, materialize the rest from an IntersectionObserver as they
   scroll near the viewport, and build collapsed sections (Tools / SSE /
   Full JSON) only when they are first opened. Turns below the thresholds
   render exactly as before. */
const DETAIL_DEFER_MSG_THRESHOLD = 40;
const DETAIL_EAGER_MSG_HEAD = 20;
const DETAIL_DEFER_JSON_BYTES = 256 * 1024;

const deferredDetail = {
  sections: new Map(), // id -> { render: () => html, copyText: null | () => string }
  messages: null, // msgs array backing [data-deferred-msg] placeholders
  observer: null,
  seq: 0,
};

function detailRenderPlan(msgCount, jsonBytes) {
  const deferMessages = msgCount > DETAIL_DEFER_MSG_THRESHOLD;
  const deferSections = deferMessages || jsonBytes > DETAIL_DEFER_JSON_BYTES;
  return {
    deferMessages,
    eagerMsgHead: deferMessages ? DETAIL_EAGER_MSG_HEAD : msgCount,
    deferSections,
  };
}

function estimateEntryJsonBytes(entry) {
  try {
    return JSON.stringify(entry).length;
  } catch (e) {
    return 0;
  }
}

function resetDeferredDetail() {
  deferredDetail.sections.clear();
  deferredDetail.messages = null;
  if (deferredDetail.observer) {
    deferredDetail.observer.disconnect();
    deferredDetail.observer = null;
  }
}

function deferredSection(title, renderBody, opts = {}) {
  const id = 'ds' + (deferredDetail.seq++);
  deferredDetail.sections.set(id, { render: renderBody, copyText: opts.copyText || null });
  let extra = '';
  if (opts.badge) extra += `<span class="badge">${esc(opts.badge)}</span>`;
  if (opts.copyText) extra += `<button class="copy-btn" data-copy-deferred="${id}">${t('copy')}</button>`;
  const placeholder = `<div class="content-block" style="color:var(--text-tertiary)">…</div>`;
  return `<div class="section"><div class="section-header"><span class="chevron">&#9654;</span><span class="title">${title}</span>${extra}</div><div class="section-body" data-deferred-section="${id}">${placeholder}</div></div>`;
}

function materializeDeferredSection(bodyEl) {
  const id = bodyEl && bodyEl.dataset ? bodyEl.dataset.deferredSection : '';
  if (!id || bodyEl.dataset.deferredRendered) return false;
  const spec = deferredDetail.sections.get(id);
  if (!spec) return false;
  bodyEl.innerHTML = spec.render();
  bodyEl.dataset.deferredRendered = 'true';
  return true;
}

function deferredSectionCopyText(id) {
  const spec = deferredDetail.sections.get(id);
  if (!spec || typeof spec.copyText !== 'function') return '';
  return spec.copyText();
}

function materializeDeferredMessage(el) {
  const msgs = deferredDetail.messages;
  const idx = el && el.dataset ? Number(el.dataset.deferredMsg) : NaN;
  if (!msgs || !Number.isInteger(idx) || idx < 0 || idx >= msgs.length) return false;
  if (deferredDetail.observer) deferredDetail.observer.unobserve(el);
  const html = renderMessageHtml(msgs[idx], { deferLayout: true });
  if (!html) {
    el.remove();
    return true;
  }
  const tpl = document.createElement('template');
  tpl.innerHTML = html;
  el.replaceWith(tpl.content);
  return true;
}

function materializeAllDeferredDetail(container) {
  const root = container || $('#detail');
  if (!root) return 0;
  let count = 0;
  root.querySelectorAll('[data-deferred-section]').forEach(el => {
    if (materializeDeferredSection(el)) count++;
  });
  root.querySelectorAll('[data-deferred-msg]').forEach(el => {
    if (materializeDeferredMessage(el)) count++;
  });
  return count;
}

function handleDeferredMessageIntersections(items) {
  for (const item of items) {
    if (item.isIntersecting) materializeDeferredMessage(item.target);
  }
}

function observeDeferredMessages(container) {
  const targets = container.querySelectorAll('[data-deferred-msg]');
  if (!targets.length) return;
  if (typeof IntersectionObserver === 'undefined') {
    targets.forEach(el => materializeDeferredMessage(el));
    return;
  }
  /* root: null works for both layouts: desktop clips placeholders via the
     .detail inner scroller, mobile scrolls the document itself. */
  deferredDetail.observer = new IntersectionObserver(handleDeferredMessageIntersections, {
    root: null,
    rootMargin: '600px 0px',
  });
  targets.forEach(el => deferredDetail.observer.observe(el));
}

/* ─── Virtual scroll state ─── */
let virtualMode = false;
const VS_ITEM_HEIGHT = 68;
const VS_BUFFER = 10;
let vsFilteredItems = []; // {entry, idx} pairs for virtual scroll

const globalSearchState = {
  open: false,
  query: '',
  queries: [],
  matchCounts: [],
  totalMatches: 0,
  currentMatch: -1,
  textCache: new Map(),
  recalcTimer: 0,
};
const TRACE_JSONL_PATH = typeof __TRACE_JSONL_PATH__ !== 'undefined' ? __TRACE_JSONL_PATH__ : '';
const TRACE_HTML_PATH = typeof __TRACE_HTML_PATH__ !== 'undefined' ? __TRACE_HTML_PATH__ : '';
const TRACE_RECORDS_API = typeof __TRACE_RECORDS_API__ !== 'undefined' ? __TRACE_RECORDS_API__ : '';
const CLAUDE_TAP_VERSION = typeof __CLAUDE_TAP_VERSION__ !== 'undefined' ? __CLAUDE_TAP_VERSION__ : '';
const TRACE_SESSION_EXPORTS = typeof __TRACE_SESSION_EXPORTS__ !== 'undefined' ? __TRACE_SESSION_EXPORTS__ : null;
