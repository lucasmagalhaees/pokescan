// Build estático (sem dependências): src/ -> public/
//  - data.json vira data.<hash>.json (cache imutável de 1 ano)
//  - injeta CSP com o hash SHA-256 do script inline (sem 'unsafe-inline' em scripts)
//  - carimba a versão no service worker e troca o nome do data.json no cache
import { createHash } from 'node:crypto';
import { cpSync, mkdirSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const sha = (buf, enc = 'hex') => createHash('sha256').update(buf).digest(enc);
const STATIC = ['manifest.webmanifest', 'icon.svg', 'icon-192.png', 'icon-512.png', 'icon-maskable-512.png', 'apple-touch-icon.png'];

export function csp(scriptHash) {
  return [
    "default-src 'self'",
    `script-src 'self' 'sha256-${scriptHash}'`,
    "style-src 'self' 'unsafe-inline'",
    "img-src 'self' data: blob:",
    "connect-src 'self'",
    "manifest-src 'self'",
    "worker-src 'self'",
    "object-src 'none'",
    "base-uri 'none'",
    "form-action 'none'",
  ].join('; ');
}

export function build({ src = 'src', out = 'public' } = {}) {
  rmSync(out, { recursive: true, force: true });
  mkdirSync(out, { recursive: true });

  const data = readFileSync(join(src, 'data.json'));
  const dataName = `data.${sha(data).slice(0, 10)}.json`;
  writeFileSync(join(out, dataName), data);

  let html = readFileSync(join(src, 'index.html'), 'utf8');
  if (!html.includes("fetch('data.json')") || !html.includes('<!--CSP-->')) throw new Error('index.html fora do formato esperado');
  html = html.replace("fetch('data.json')", `fetch('${dataName}')`);
  const script = html.match(/<script>([\s\S]*?)<\/script>/)[1];
  const scriptHash = sha(script, 'base64');
  html = html.replace('<!--CSP-->', `<meta http-equiv="Content-Security-Policy" content="${csp(scriptHash)}">`);
  writeFileSync(join(out, 'index.html'), html);

  const version = sha(html + dataName).slice(0, 10);
  const sw = readFileSync(join(src, 'sw.js'), 'utf8').replaceAll('__BUILD__', version).replace("'data.json'", `'${dataName}'`);
  writeFileSync(join(out, 'sw.js'), sw);

  for (const f of STATIC) cpSync(join(src, f), join(out, f));
  return { dataName, scriptHash, version };
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const r = build();
  console.log(`build ok: ${r.dataName} · versão ${r.version}`);
}
