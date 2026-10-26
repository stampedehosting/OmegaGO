// visual-limbs edge router — Cloudflare Worker (module syntax).
// Routes:
//   GET  /token?room=R&agent=N   -> LiveKit access token (LIVEKIT_API_KEY/SECRET, TTL 1h)
//   ANY  /mesh/*                 -> proxy to lowest-latency control node (NODES_JSON / CONTABO_URL)
//   GET  /assets/*               -> R2 bucket (ASSETS binding), HTTP 206 range support
//   GET  /health                 -> liveness JSON
//   OPTIONS *                    -> CORS preflight

import { pickNode } from './latency.js';

const TOKEN_TTL_SECONDS = 3600; // 1h

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    const path = url.pathname;

    try {
      if (request.method === 'OPTIONS') {
        return cors(new Response(null, { status: 204 }));
      }
      if (path === '/health' || path === '/healthz') {
        return handleHealth(request);
      }
      if (path === '/token') {
        return handleToken(request, env, url);
      }
      if (path === '/mesh' || path.startsWith('/mesh/')) {
        return await handleMesh(request, env, url);
      }
      if (path.startsWith('/assets/')) {
        return await handleAssets(request, env, url);
      }
      return json({ error: 'not_found', path }, 404);
    } catch (err) {
      return json({ error: 'internal_error', message: String((err && err.message) || err) }, 500);
    }
  },
};

// ---------- /health ----------

function handleHealth(request) {
  const cf = request.cf || {};
  return cors(
    json({
      ok: true,
      service: 'visual-limbs-edge',
      version: '0.1.0',
      colo: cf.colo || null,
      time: new Date().toISOString(),
    })
  );
}

// ---------- /token ----------

async function handleToken(request, env, url) {
  if (request.method !== 'GET') return json({ error: 'method_not_allowed' }, 405);
  if (!authorized(request, env, url)) return json({ error: 'unauthorized' }, 401);

  const room = url.searchParams.get('room');
  const agent = url.searchParams.get('agent');
  if (!room || !agent) {
    return json({ error: 'bad_request', message: 'required query params: room, agent' }, 400);
  }
  if (env.ROOM_PREFIX && !room.startsWith(env.ROOM_PREFIX)) {
    return json({ error: 'forbidden', message: 'room not permitted' }, 403);
  }
  if (!env.LIVEKIT_API_KEY || !env.LIVEKIT_API_SECRET) {
    return json({ error: 'missing_secrets', message: 'LIVEKIT_API_KEY / LIVEKIT_API_SECRET not configured' }, 503);
  }

  const now = Math.floor(Date.now() / 1000);
  const payload = {
    iss: env.LIVEKIT_API_KEY,
    sub: agent,
    iat: now,
    nbf: now - 10,
    exp: now + TOKEN_TTL_SECONDS,
    video: {
      roomJoin: true,
      room: room,
      canPublish: true,
      canSubscribe: true,
      canPublishData: true,
    },
    metadata: JSON.stringify({ agent: agent }),
  };

  const token = await signJwtHS256(payload, env.LIVEKIT_API_SECRET);
  return cors(
    json({
      token: token,
      room: room,
      agent: agent,
      expires_in: TOKEN_TTL_SECONDS,
      livekit_url: env.LIVEKIT_URL || null,
    })
  );
}

// ---------- /mesh/* ----------

async function handleMesh(request, env, url) {
  if (!authorized(request, env, url)) return json({ error: 'unauthorized' }, 401);

  const node = await pickNode(env.NODES_JSON, env.CONTABO_URL, {
    timeoutMs: num(env.PROBE_TIMEOUT_MS, 1500),
    cacheMs: num(env.PROBE_CACHE_MS, 10000),
    probePath: env.PROBE_PATH || '/probe',
  });
  if (!node) return json({ error: 'no_upstream', message: 'no control nodes configured' }, 503);

  const target = new URL(node.url);
  const suffix = url.pathname.replace(/^\/mesh/, '');
  target.pathname = joinPath(target.pathname, suffix === '' ? '/' : suffix);
  target.search = url.search;

  const wantsWebSocket = (request.headers.get('upgrade') || '').toLowerCase() === 'websocket';
  const headers = new Headers(request.headers);
  const strip = ['host', 'content-length', 'cdn-loop', 'cf-worker', 'cf-ew-via', 'cf-ray', 'cf-visitor', 'cf-connecting-ip', 'x-forwarded-proto', 'x-real-ip'];
  if (!wantsWebSocket) strip.push('connection', 'upgrade');
  for (const h of strip) headers.delete(h);
  const clientIp = request.headers.get('cf-connecting-ip');
  if (clientIp) headers.set('x-forwarded-for', clientIp);
  headers.set('x-mesh-edge', 'visual-limbs-edge');

  const init = { method: request.method, headers: headers, redirect: 'manual' };
  if (request.method !== 'GET' && request.method !== 'HEAD') {
    init.body = request.body;
    init.duplex = 'half'; // required when forwarding a streamed request body
  }

  const upstream = await fetch(new Request(target.toString(), init));

  // WebSocket upgrade: the fetched response carries a webSocket handle and
  // status 101, which the Response constructor cannot rebuild — pass it on.
  if (upstream.webSocket) {
    const wsHeaders = new Headers();
    wsHeaders.set('x-mesh-node', node.name);
    return new Response(null, { status: 101, webSocket: upstream.webSocket, headers: wsHeaders });
  }

  const resHeaders = new Headers(upstream.headers);
  resHeaders.set('x-mesh-node', node.name);
  if (node.latencyMs != null) resHeaders.set('x-mesh-latency-ms', String(node.latencyMs));

  return cors(
    new Response(upstream.body, {
      status: upstream.status,
      statusText: upstream.statusText,
      headers: resHeaders,
    })
  );
}

// ---------- /assets/* ----------

async function handleAssets(request, env, url) {
  if (request.method !== 'GET' && request.method !== 'HEAD') {
    return json({ error: 'method_not_allowed' }, 405);
  }
  if (!env.ASSETS || typeof env.ASSETS.get !== 'function') {
    return json({ error: 'r2_binding_missing', binding: 'ASSETS' }, 503);
  }

  const key = decodeURIComponent(url.pathname.replace(/^\/assets\//, ''));
  if (!key) return json({ error: 'bad_request', message: 'asset key required' }, 400);

  // Parse a single "bytes=a-b" / "bytes=a-" / "bytes=-n" range (multi-range unsupported).
  let range = null;
  let meta = null;
  const rangeHeader = request.headers.get('Range');
  if (rangeHeader) {
    const m = /^bytes=(\d*)-(\d*)$/.exec(rangeHeader.trim());
    if (!m || (m[1] === '' && m[2] === '')) {
      return new Response(null, { status: 416, headers: { 'content-range': 'bytes */*' } });
    }
    meta = await env.ASSETS.head(key);
    if (!meta) return json({ error: 'not_found', key: key }, 404);

    const size = meta.size;
    let offset;
    let length;
    if (m[1] === '') {
      const n = Math.min(parseInt(m[2], 10), size);
      offset = size - n;
      length = n;
    } else {
      offset = parseInt(m[1], 10);
      if (offset >= size) {
        return new Response(null, { status: 416, headers: { 'content-range': 'bytes */' + size } });
      }
      const end = m[2] === '' ? size - 1 : Math.min(parseInt(m[2], 10), size - 1);
      length = end - offset + 1;
    }
    // Reversed (bytes=10-5) or empty (bytes=-0) ranges are unsatisfiable.
    if (!Number.isFinite(length) || length <= 0) {
      return new Response(null, { status: 416, headers: { 'content-range': 'bytes */' + size } });
    }
    // If-Range: serve the partial only if the client's validator still matches.
    const ifRange = (request.headers.get('if-range') || '').trim();
    if (!ifRange || ifRangeSatisfied(ifRange, meta)) {
      range = { offset: offset, length: length, total: size };
    }
  }

  const obj = await env.ASSETS.get(key, {
    onlyIf: request.headers,
    range: range ? { offset: range.offset, length: range.length } : undefined,
  });
  if (!obj) return json({ error: 'not_found', key: key }, 404);

  // Condition failed: R2 returns the object without a body.
  // If-Match / If-Unmodified-Since failures are 412; revalidation failures are 304.
  if (obj.body === undefined) {
    const status = request.headers.get('if-match') || request.headers.get('if-unmodified-since') ? 412 : 304;
    return new Response(null, { status: status, headers: { etag: obj.httpEtag, 'accept-ranges': 'bytes' } });
  }

  const headers = new Headers();
  obj.writeHttpMetadata(headers);
  headers.set('etag', obj.httpEtag);
  headers.set('accept-ranges', 'bytes');
  if (!headers.get('content-type')) headers.set('content-type', guessType(key));

  let status = 200;
  if (range) {
    status = 206;
    const end = range.offset + range.length - 1;
    headers.set('content-range', 'bytes ' + range.offset + '-' + end + '/' + range.total);
    headers.set('content-length', String(range.length));
  }

  return cors(new Response(obj.body, { status: status, headers: headers }));
}

// ---------- helpers ----------

function json(body, status) {
  return new Response(JSON.stringify(body), {
    status: status || 200,
    headers: { 'content-type': 'application/json; charset=utf-8' },
  });
}

function cors(res) {
  const headers = new Headers(res.headers);
  headers.set('access-control-allow-origin', '*');
  headers.set('access-control-allow-methods', 'GET, HEAD, POST, PUT, PATCH, DELETE, OPTIONS');
  headers.set('access-control-allow-headers', 'authorization, content-type, range, x-requested-with');
  headers.set('access-control-expose-headers', 'content-range, content-length, etag, x-mesh-node, x-mesh-latency-ms');
  return new Response(res.body, { status: res.status, statusText: res.statusText, headers: headers });
}

// EDGE_AUTH_TOKEN unset -> open edge (dev). When set, requires
// `Authorization: Bearer <token>` or `?access_token=<token>` (query form
// exists for browser WebSocket clients, which cannot set headers).
function authorized(request, env, url) {
  if (!env.EDGE_AUTH_TOKEN) return true;
  if (request.headers.get('authorization') === 'Bearer ' + env.EDGE_AUTH_TOKEN) return true;
  return url.searchParams.get('access_token') === env.EDGE_AUTH_TOKEN;
}

// If-Range is either an etag or an HTTP-date; satisfied means the client's
// saved version is still current, so a 206 is safe.
function ifRangeSatisfied(ifRange, meta) {
  if (ifRange.charAt(0) === '"' || ifRange.slice(0, 2) === 'W/') {
    return meta.httpEtag === ifRange;
  }
  const t = Date.parse(ifRange);
  if (!Number.isFinite(t) || !meta.uploaded) return false;
  return new Date(meta.uploaded).getTime() <= t;
}

function num(v, dflt) {
  if (v === undefined || v === null || v === '') return dflt;
  const n = Number(v);
  return Number.isFinite(n) && n >= 0 ? n : dflt;
}

function joinPath(base, suffix) {
  const b = base.endsWith('/') ? base.slice(0, -1) : base;
  const s = suffix.startsWith('/') ? suffix : '/' + suffix;
  return b + s;
}

function b64url(bytes) {
  const arr = bytes instanceof Uint8Array ? bytes : new Uint8Array(bytes);
  let bin = '';
  for (let i = 0; i < arr.length; i++) bin += String.fromCharCode(arr[i]);
  return btoa(bin).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}

function b64urlStr(s) {
  return b64url(new TextEncoder().encode(s));
}

async function signJwtHS256(payload, secret) {
  const header = { alg: 'HS256', typ: 'JWT' };
  const data = b64urlStr(JSON.stringify(header)) + '.' + b64urlStr(JSON.stringify(payload));
  const key = await crypto.subtle.importKey(
    'raw',
    new TextEncoder().encode(secret),
    { name: 'HMAC', hash: 'SHA-256' },
    false,
    ['sign']
  );
  const sig = await crypto.subtle.sign('HMAC', key, new TextEncoder().encode(data));
  return data + '.' + b64url(sig);
}

const MIME = {
  html: 'text/html; charset=utf-8',
  js: 'text/javascript; charset=utf-8',
  mjs: 'text/javascript; charset=utf-8',
  css: 'text/css; charset=utf-8',
  json: 'application/json',
  png: 'image/png',
  jpg: 'image/jpeg',
  jpeg: 'image/jpeg',
  gif: 'image/gif',
  webp: 'image/webp',
  svg: 'image/svg+xml',
  mp4: 'video/mp4',
  webm: 'video/webm',
  mp3: 'audio/mpeg',
  wav: 'audio/wav',
  wasm: 'application/wasm',
  pdf: 'application/pdf',
  txt: 'text/plain; charset=utf-8',
};

function guessType(key) {
  const ext = key.slice(key.lastIndexOf('.') + 1).toLowerCase();
  return MIME[ext] || 'application/octet-stream';
}
