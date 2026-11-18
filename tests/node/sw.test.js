'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');

// mocks do ambiente de service worker
const store = new Map();
const listeners = {};
let netImpl; let lastWait; let skipped = 0; let claimed = 0;
function mkCache(name) {
  if (!store.has(name)) store.set(name, new Map());
  const m = store.get(name);
  return {
    addAll: async (list) => { for (const k of list) m.set(k, `res:${k}`); },
    match: async (req) => { const k = typeof req === 'string' ? req : req.url; return m.get(k) || m.get(k.replace(/^https?:\/\/[^/]+\//, '')); },
    put: async (req, r) => { m.set(req.url, r); },
  };
}
global.caches = { open: async (n) => mkCache(n), keys: async () => [...store.keys()], delete: async (k) => store.delete(k) };
global.Response = { error: () => 'ERR' };
global.fetch = async (req) => netImpl(req);
global.self = { addEventListener: (t, f) => { listeners[t] = f; }, location: { origin: 'https://app.test' }, skipWaiting: () => { skipped++; }, clients: { claim: () => { claimed++; } } };
const sw = require('../../src/sw.js');
const wait = (p) => { lastWait = p; };
const R = (url, over = {}) => ({ url: `https://app.test/${url}`, method: 'GET', mode: 'cors', ...over });
const resp = (ok = true) => ({ ok, clone: () => 'clone' });

test('registra os 3 eventos', () => { assert.deepEqual(Object.keys(listeners).sort(), ['activate', 'fetch', 'install']); });

test('install pré-carrega a casca e ativa na hora', async () => {
  let p; listeners.install({ waitUntil: (x) => { p = x; } }); await p;
  assert.equal(skipped, 1); assert.equal(store.get(sw.CACHE).size, sw.SHELL.length);
});

test('activate apaga só caches antigos do app', async () => {
  store.set('pbh-antigo', new Map()); store.set('outro-app', new Map());
  let p; listeners.activate({ waitUntil: (x) => { p = x; } }); await p;
  assert.ok(!store.has('pbh-antigo')); assert.ok(store.has('outro-app')); assert.ok(store.has(sw.CACHE)); assert.equal(claimed, 1);
});

test('cache primeiro e atualiza em segundo plano', async () => {
  netImpl = async () => resp(true);
  const hit = await sw.respond(R('index.html'), wait);
  assert.equal(hit, 'res:index.html'); await lastWait;
  assert.equal(store.get(sw.CACHE).get('https://app.test/index.html'), 'clone');
});

test('sem cache vai à rede; resposta ruim não é guardada', async () => {
  netImpl = async () => resp(false);
  const r = await sw.respond(R('novo.json'), wait);
  assert.equal(r.ok, false); assert.ok(!store.get(sw.CACHE).has('https://app.test/novo.json'));
});

test('offline: navegação cai no index, outros recursos dão erro', async () => {
  netImpl = async () => { throw new Error('offline'); };
  assert.equal(await sw.respond(R('qualquer', { mode: 'navigate' }), wait), 'res:index.html');
  assert.equal(await sw.respond(R('x.png'), wait), 'ERR');
  netImpl = async () => null;
  assert.equal(await sw.respond(R('y.png'), wait), 'ERR');
});

test('fetch ignora POST, outra origem e /api/', () => {
  let responded = 0;
  const ev = (request) => ({ request, respondWith: () => { responded++; }, waitUntil: () => {} });
  sw.onFetch(ev(R('a', { method: 'POST' })));
  sw.onFetch(ev({ url: 'https://outro.com/a', method: 'GET' }));
  sw.onFetch(ev(R('api/identify')));
  assert.equal(responded, 0);
});

test('fetch responde recursos do próprio app', async () => {
  netImpl = async () => resp(true);
  let promise; let waited = 0;
  sw.onFetch({ request: R('manifest.webmanifest'), respondWith: (p) => { promise = p; }, waitUntil: () => { waited++; } });
  assert.equal(await promise, 'res:manifest.webmanifest'); assert.equal(waited, 1);
});

test('sem ambiente de SW e sem module não quebra', () => {
  delete require.cache[require.resolve('../../src/sw.js')];
  const saved = global.self; delete global.self;
  require('../../src/sw.js');
  global.self = { location: {} };
  delete require.cache[require.resolve('../../src/sw.js')];
  require('../../src/sw.js');
  global.self = saved;
});
