'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const identify = require('../../api/identify.js');
const health = require('../../api/health.js');

function res() {
  const r = { code: 200, headers: {}, body: null };
  r.setHeader = (k, v) => { r.headers[k] = v; };
  r.status = (c) => { r.code = c; return r; };
  r.json = (b) => { r.body = b; return r; };
  return r;
}
const B64 = 'QUJD'; // "ABC"
const req = (over = {}) => ({ method: 'POST', headers: { 'x-forwarded-for': '1.1.1.1' }, body: { mode: 'opp', image: B64 }, ...over });
let calls;
const realFetch = global.fetch;
function mockFetch(impl) { calls = []; global.fetch = async (url, init) => { calls.push({ url, init }); return impl(url, init); }; }
const ok = (content) => ({ ok: true, status: 200, json: async () => ({ content }) });

test.beforeEach(() => {
  identify.hits.clear();
  process.env.ANTHROPIC_API_KEY = 'sk-test';
  delete process.env.ACCESS_CODE;
  delete process.env.ANTHROPIC_MODEL;
});
test.after(() => { global.fetch = realFetch; });

test('health informa recursos sem expor segredos', () => {
  process.env.ANTHROPIC_API_KEY = 'sk-test'; process.env.ACCESS_CODE = 'x';
  const r = res(); health({}, r);
  assert.deepEqual(r.body, { ok: true, vision: true, needsCode: true });
  assert.equal(r.headers['Cache-Control'], 'no-store');
  delete process.env.ANTHROPIC_API_KEY; delete process.env.ACCESS_CODE;
  const r2 = res(); health({}, r2);
  assert.deepEqual(r2.body, { ok: true, vision: false, needsCode: false });
});

test('só aceita POST', async () => {
  const r = res(); await identify(req({ method: 'GET' }), r);
  assert.equal(r.code, 405); assert.equal(r.headers.Allow, 'POST');
});

test('503 sem chave configurada', async () => {
  delete process.env.ANTHROPIC_API_KEY;
  const r = res(); await identify(req(), r);
  assert.equal(r.code, 503);
});

test('código de acesso: exige e aceita o correto', async () => {
  process.env.ACCESS_CODE = 'segredo';
  mockFetch(() => ok([{ type: 'text', text: '{"pokemon":[]}' }]));
  let r = res(); await identify(req(), r); assert.equal(r.code, 401);
  r = res(); await identify(req({ headers: { 'x-access-code': 'errado!' } }), r); assert.equal(r.code, 401);
  r = res(); await identify(req({ headers: { 'x-access-code': 'segredo' } }), r); assert.equal(r.code, 200);
});

test('limite de requisições por IP por minuto', async () => {
  mockFetch(() => ok([{ type: 'text', text: 'x' }]));
  for (let i = 0; i < identify.LIMIT; i++) { const r = res(); await identify(req(), r); assert.equal(r.code, 200); }
  const r = res(); await identify(req(), r); assert.equal(r.code, 429);
  const outro = res(); await identify(req({ headers: { 'x-forwarded-for': '2.2.2.2, 9.9.9.9' } }), outro); assert.equal(outro.code, 200);
  const semIp = res(); await identify(req({ headers: {} }), semIp); assert.equal(semIp.code, 200);
});

test('limpeza de IPs antigos quando o mapa cresce', async () => {
  mockFetch(() => ok([{ type: 'text', text: 'x' }]));
  const old = Date.now() - 120_000;
  for (let i = 0; i < 1001; i++) identify.hits.set(`ip${i}`, [old]);
  identify.hits.set('recente', [Date.now()]);
  const r = res(); await identify(req(), r);
  assert.equal(r.code, 200); assert.ok(identify.hits.size < 10); assert.ok(identify.hits.has('recente'));
});

test('valida o corpo', async () => {
  for (const body of [undefined, {}, { mode: 'x', image: B64 }, { mode: 'opp' }, { mode: 'opp', image: 5 },
    { mode: 'opp', image: 'não é base64!' }, { mode: 'opp', image: 'A'.repeat(2_500_001) }, { mode: 'toString', image: B64 }]) {
    const r = res(); await identify(req({ body }), r);
    assert.equal(r.code, 400, JSON.stringify(body)?.slice(0, 40));
  }
});

test('chama a Anthropic com prompt fixo, chave no servidor e devolve o texto', async () => {
  process.env.ANTHROPIC_MODEL = 'modelo-x';
  mockFetch(() => ok([{ type: 'text', text: '{"pokemon":' }, { type: 'tool_use' }, { type: 'text', text: '["Gengar"]}' }]));
  const r = res(); await identify(req({ body: { mode: 'team', image: B64 + '==' .slice(0, 0) } }), r);
  assert.equal(r.code, 200); assert.equal(r.body.text, '{"pokemon":["Gengar"]}');
  const { url, init } = calls[0]; const sent = JSON.parse(init.body);
  assert.equal(url, 'https://api.anthropic.com/v1/messages');
  assert.equal(init.headers['x-api-key'], 'sk-test'); assert.equal(sent.model, 'modelo-x');
  assert.match(sent.messages[0].content[1].text, /time\/party/); assert.equal(sent.messages[0].content[0].source.data, B64);
});

test('usa o modelo padrão e tolera resposta sem content', async () => {
  mockFetch(() => ({ ok: true, status: 200, json: async () => ({}) }));
  const r = res(); await identify(req(), r);
  assert.equal(r.body.text, ''); assert.equal(JSON.parse(calls[0].init.body).model, 'claude-haiku-5-5');
  assert.match(JSON.parse(calls[0].init.body).messages[0].content[1].text, /OPONENTE/);
});

test('502 quando a Anthropic falha ou fica inacessível', async () => {
  mockFetch(() => ({ ok: false, status: 529, json: async () => ({}) }));
  let r = res(); await identify(req(), r); assert.deepEqual([r.code, r.body.status], [502, 529]);
  mockFetch(() => { throw new Error('rede'); });
  r = res(); await identify(req(), r); assert.deepEqual([r.code, r.body.error], [502, 'upstream_unreachable']);
});
