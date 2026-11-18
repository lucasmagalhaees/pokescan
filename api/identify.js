'use strict';
// Função serverless (Vercel): identifica Pokémon numa imagem usando a API da Anthropic.
// A chave fica só no servidor (ANTHROPIC_API_KEY). O prompt é fixo aqui, o cliente só escolhe o "mode".
const crypto = require('node:crypto');

const API_URL = 'https://api.anthropic.com/v1/messages';
const PROMPTS = {
  team: 'A imagem é de um jogo de Pokémon (Scarlet/Violet ou Legends Z-A) mostrando o time/party do jogador. Liste todos os Pokémon visíveis, na ordem. Use o nome oficial em inglês (formas especiais como "Garchomp-Mega" ou "Raichu-Alola"). Responda APENAS JSON: {"pokemon":["Nome1","Nome2"]}',
  opp: 'A imagem é de um jogo de Pokémon (Scarlet/Violet ou Legends Z-A) ou foto de uma tela. Identifique o Pokémon OPONENTE (o que está do lado do adversário; se só houver um Pokémon, é ele). Use o nome oficial em inglês (ex: "Garchomp-Mega"). Responda APENAS JSON: {"pokemon":["Nome"]}',
};
const MAX_B64 = 2_500_000; // ~1.8 MB de imagem
const WINDOW_MS = 60_000;
const LIMIT = 20; // requisições por IP por minuto (por instância; use o Firewall da Vercel para limite global)
const hits = new Map();

function same(a, b) {
  const x = Buffer.from(String(a));
  const y = Buffer.from(String(b));
  return x.length === y.length && crypto.timingSafeEqual(x, y);
}

function limited(ip, now) {
  if (hits.size > 1000) {
    for (const [k, v] of hits) if (!v.some((t) => now - t < WINDOW_MS)) hits.delete(k);
  }
  const list = (hits.get(ip) || []).filter((t) => now - t < WINDOW_MS);
  list.push(now);
  hits.set(ip, list);
  return list.length > LIMIT;
}

async function handler(req, res) {
  res.setHeader('Cache-Control', 'no-store');
  if (req.method !== 'POST') {
    res.setHeader('Allow', 'POST');
    return res.status(405).json({ error: 'method_not_allowed' });
  }
  const key = process.env.ANTHROPIC_API_KEY;
  if (!key) return res.status(503).json({ error: 'not_configured' });
  const code = process.env.ACCESS_CODE;
  if (code && !same(req.headers['x-access-code'] || '', code)) return res.status(401).json({ error: 'unauthorized' });
  const ip = String(req.headers['x-forwarded-for'] || 'unknown').split(',')[0].trim();
  if (limited(ip, Date.now())) return res.status(429).json({ error: 'rate_limited' });

  const { mode, image } = req.body || {};
  if (!Object.hasOwn(PROMPTS, mode) || typeof image !== 'string' || image.length > MAX_B64 || !/^[A-Za-z0-9+/]+={0,2}$/.test(image)) {
    return res.status(400).json({ error: 'bad_request' });
  }

  let upstream;
  try {
    upstream = await fetch(API_URL, {
      method: 'POST',
      headers: { 'content-type': 'application/json', 'x-api-key': key, 'anthropic-version': '2023-06-01' },
      body: JSON.stringify({
        model: process.env.ANTHROPIC_MODEL || 'claude-haiku-5-5',
        max_tokens: 300,
        messages: [{ role: 'user', content: [
          { type: 'image', source: { type: 'base64', media_type: 'image/jpeg', data: image } },
          { type: 'text', text: PROMPTS[mode] },
        ] }],
      }),
      signal: AbortSignal.timeout(15_000),
    });
  } catch {
    return res.status(502).json({ error: 'upstream_unreachable' });
  }
  if (!upstream.ok) return res.status(502).json({ error: 'upstream_error', status: upstream.status });
  const data = await upstream.json();
  const text = (data.content || []).filter((b) => b.type === 'text').map((b) => b.text).join('');
  return res.status(200).json({ text });
}

module.exports = handler;
module.exports.hits = hits;
module.exports.LIMIT = LIMIT;
