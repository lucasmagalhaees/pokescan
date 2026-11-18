'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const crypto = require('node:crypto');
const { spawnSync } = require('node:child_process');

const root = path.resolve(__dirname, '../..');
const tmp = () => fs.mkdtempSync(path.join(os.tmpdir(), 'pbh-'));

test('build gera public/ com hash do script, data com hash e SW versionado', async () => {
  const { build, csp } = await import('../../scripts/build.mjs');
  const out = tmp();
  const r = build({ src: path.join(root, 'src'), out });
  const html = fs.readFileSync(path.join(out, 'index.html'), 'utf8');
  const script = html.match(/<script>([\s\S]*?)<\/script>/)[1];
  assert.equal(r.scriptHash, crypto.createHash('sha256').update(script).digest('base64'));
  assert.ok(html.includes(csp(r.scriptHash)) && !html.includes('<!--CSP-->'));
  assert.ok(html.includes(`fetch('${r.dataName}')`) && fs.existsSync(path.join(out, r.dataName)));
  assert.match(r.dataName, /^data\.[a-f0-9]{10}\.json$/);
  const sw = fs.readFileSync(path.join(out, 'sw.js'), 'utf8');
  assert.ok(sw.includes(`pbh-${r.version}`) && sw.includes(`'${r.dataName}'`) && !sw.includes('__BUILD__'));
  for (const f of ['manifest.webmanifest', 'icon-192.png', 'icon-512.png', 'icon-maskable-512.png', 'apple-touch-icon.png', 'icon.svg']) assert.ok(fs.existsSync(path.join(out, f)), f);
  assert.ok(!/script-src[^;]*unsafe-inline/.test(csp('x')));
});

test('build recusa index.html fora do formato', async () => {
  const { build } = await import('../../scripts/build.mjs');
  const src = tmp();
  for (const f of fs.readdirSync(path.join(root, 'src'))) fs.copyFileSync(path.join(root, 'src', f), path.join(src, f));
  fs.writeFileSync(path.join(src, 'index.html'), '<html></html>');
  assert.throws(() => build({ src, out: tmp() }), /formato esperado/);
});

test('CLI roda o build padrão a partir da raiz', () => {
  const r = spawnSync('node', ['scripts/build.mjs'], { cwd: root, encoding: 'utf8' });
  assert.equal(r.status, 0, r.stderr); assert.match(r.stdout, /build ok: data\.[a-f0-9]{10}\.json/);
  fs.rmSync(path.join(root, 'public'), { recursive: true, force: true });
});

test('vercel.json é válido e coerente com o build', () => {
  const v = JSON.parse(fs.readFileSync(path.join(root, 'vercel.json'), 'utf8'));
  assert.equal(v.outputDirectory, 'public'); assert.equal(v.buildCommand, 'node scripts/build.mjs');
  const src = v.headers.map((h) => h.source);
  assert.ok(src.includes('/sw.js') && src.some((s) => s.startsWith('/api/')));
  const dataRule = v.headers.find((h) => h.source.includes('data'));
  assert.ok(new RegExp(`^${dataRule.source.replace(/^\//, '').replace(/^\((.*)\)$/, '$1')}$`).test('data.0123456789.json'));
  assert.match(JSON.stringify(v.headers), /immutable/);
});
