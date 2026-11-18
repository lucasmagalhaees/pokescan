'use strict';
// Diz ao front quais recursos de servidor estão ativos (sem expor segredos).
module.exports = function health(req, res) {
  res.setHeader('Cache-Control', 'no-store');
  res.status(200).json({ ok: true, vision: Boolean(process.env.ANTHROPIC_API_KEY), needsCode: Boolean(process.env.ACCESS_CODE) });
};
