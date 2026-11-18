# Pokémon Battle Helper

Diz qual Pokémon do seu time mandar contra o oponente (Scarlet/Violet e Legends Z-A): modo defensivo e agressivo, velocidade, golpes, Tera, itens, cura/buff, planos e histórico.

## Deploy na Vercel
1. Importe este repositório na Vercel (sem framework; o `vercel.json` já define build e saída `public/`).
2. Em *Settings → Environment Variables*:
   - `ANTHROPIC_API_KEY` — liga a leitura de foto (time/oponente). Sem ela o app funciona normal, só sem foto.
   - `ACCESS_CODE` (opcional) — código exigido nas fotos, para ninguém gastar sua chave.
   - `ANTHROPIC_MODEL` (opcional) — padrão `claude-haiku-5-5`.
3. Cada merge na `main` faz deploy.

Voz usa o reconhecimento do navegador (Chrome/Android/Safari). O app é PWA: dá para instalar e abre offline.

## Desenvolvimento
- `npm run dev` — servidor local em `src/`
- `npm test` — Node (API, SW, build; 100% cobertura) + Python/Playwright (unit, e2e, desempenho, taxa de vitória)
- `npm run build` — gera `public/` (CSP com hash, dados com hash)
- Requer: Node 20+, `pip install pytest playwright pillow && playwright install chromium`
