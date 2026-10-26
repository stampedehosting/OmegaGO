// latency.js — pick the lowest-latency control node from the CF edge colo.
//
// Nodes come from the NODES_JSON env var, either as a map {"name": "url"} or an
// array [{"name": "...", "url": "..."}]. Each candidate is raced with a small
// GET {url}/probe; the first to answer 2xx wins. Results are cached briefly
// per isolate (each colo re-probes, so "nearest" is per edge location, which
// is the point). Falls back to CONTABO_URL, then the first configured node.

const DEFAULT_TIMEOUT_MS = 1500;
const DEFAULT_CACHE_MS = 10000;
const DEFAULT_PROBE_PATH = '/probe';

// Module-scope: persists for the life of the isolate in this colo.
let cached = { winner: null, expiresAt: 0 };

export async function pickNode(nodesJson, fallbackUrl, opts) {
  const o = opts || {};
  const timeoutMs = o.timeoutMs || DEFAULT_TIMEOUT_MS;
  const cacheMs = o.cacheMs != null ? o.cacheMs : DEFAULT_CACHE_MS;
  const probePath = o.probePath || DEFAULT_PROBE_PATH;

  const nodes = parseNodes(nodesJson);
  const now = Date.now();

  if (cached.winner && now < cached.expiresAt && isConfigured(cached.winner, nodes, fallbackUrl)) {
    return cached.winner;
  }

  let winner = null;
  if (nodes.length) {
    winner = await Promise.any(nodes.map((n) => probeNode(n, probePath, timeoutMs))).catch(() => null);
  }

  const chosen =
    winner ||
    (fallbackUrl ? { name: 'contabo', url: fallbackUrl, latencyMs: null } : nodes[0] || null);

  cached = { winner: chosen, expiresAt: now + cacheMs };
  return chosen;
}

// Diagnostics: probe every node and report all latencies (not used on hot path).
export async function probeAll(nodesJson, opts) {
  const o = opts || {};
  const timeoutMs = o.timeoutMs || DEFAULT_TIMEOUT_MS;
  const probePath = o.probePath || DEFAULT_PROBE_PATH;
  const nodes = parseNodes(nodesJson);
  return Promise.all(
    nodes.map((n) =>
      probeNode(n, probePath, timeoutMs).then(
        (r) => r,
        (err) => ({ name: n.name, url: n.url, latencyMs: null, error: String((err && err.message) || err) })
      )
    )
  );
}

export function parseNodes(nodesJson) {
  if (!nodesJson) return [];
  let raw = nodesJson;
  if (typeof raw === 'string') {
    try {
      raw = JSON.parse(raw);
    } catch (e) {
      return [];
    }
  }
  if (Array.isArray(raw)) {
    return raw
      .filter((n) => n && n.url)
      .map((n) => ({ name: n.name || n.url, url: trimSlash(n.url) }));
  }
  if (raw && typeof raw === 'object') {
    return Object.keys(raw)
      .filter((k) => raw[k])
      .map((k) => ({ name: k, url: trimSlash(raw[k]) }));
  }
  return [];
}

async function probeNode(node, probePath, timeoutMs) {
  const t0 = Date.now();
  const res = await fetch(node.url + probePath, {
    method: 'GET',
    signal: AbortSignal.timeout(timeoutMs),
    cf: { cacheTtl: 0, cacheEverything: false },
    headers: { 'user-agent': 'visual-limbs-edge-probe/0.1' },
  });
  if (res.body) res.body.cancel();
  if (!res.ok) throw new Error('probe_status_' + res.status);
  return { name: node.name, url: node.url, latencyMs: Date.now() - t0 };
}

function isConfigured(winner, nodes, fallbackUrl) {
  return nodes.some((n) => n.url === winner.url) || winner.url === trimSlash(fallbackUrl || '');
}

function trimSlash(u) {
  return typeof u === 'string' && u.endsWith('/') ? u.slice(0, -1) : u;
}
