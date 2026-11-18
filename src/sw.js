'use strict';
// O marcador de versão e o nome do data.json são substituídos em scripts/build.mjs.
const CACHE = 'pbh-__BUILD__';
const SHELL = ['./', 'index.html', 'data.json', 'manifest.webmanifest', 'icon-192.png', 'icon-512.png'];

async function install() {
  const c = await caches.open(CACHE);
  await c.addAll(SHELL);
}

async function activate() {
  const keys = await caches.keys();
  await Promise.all(keys.filter((k) => k !== CACHE && k.startsWith('pbh-')).map((k) => caches.delete(k)));
}

async function respond(req, wait) {
  const c = await caches.open(CACHE);
  const hit = await c.match(req, { ignoreSearch: true });
  const net = fetch(req)
    .then((r) => {
      if (r && r.ok) c.put(req, r.clone());
      return r;
    })
    .catch(() => null);
  if (hit) {
    wait(net);
    return hit;
  }
  const r = await net;
  if (r) return r;
  return req.mode === 'navigate' ? c.match('index.html') : Response.error();
}

function onFetch(e) {
  const u = new URL(e.request.url);
  if (e.request.method !== 'GET' || u.origin !== self.location.origin || u.pathname.startsWith('/api/')) return;
  e.respondWith(respond(e.request, (p) => e.waitUntil(p)));
}

if (typeof self !== 'undefined' && self.addEventListener) {
  self.addEventListener('install', (e) => e.waitUntil(install().then(() => self.skipWaiting())));
  self.addEventListener('activate', (e) => e.waitUntil(activate().then(() => self.clients.claim())));
  self.addEventListener('fetch', onFetch);
}
if (typeof module !== 'undefined') module.exports = { install, activate, respond, onFetch, CACHE, SHELL };
