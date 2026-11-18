"""Micro-benchmark (ms por chamada) das operações mais usadas pela UI. Uso: python tests/bench.py"""
import sys, functools, http.server, threading
from playwright.sync_api import sync_playwright
ROOT = __import__("pathlib").Path(__file__).resolve().parent.parent / "src"
h = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(ROOT))
h.log_message = lambda *a: None
srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), h)
threading.Thread(target=srv.serve_forever, daemon=True).start()
JS = """()=>{
  const T=['Garchomp','Corviknight','Gengar','Kingambit','Charizard','Pikachu'];
  team=T;opp='Greninja';MV={};
  const time=(f,n)=>{const t=performance.now();for(let i=0;i<n;i++)f();return +((performance.now()-t)/n).toFixed(3)};
  const out={};
  out.resolve_fuzzy=time(()=>resolve('pikahcu'),30);
  out.suggest=time(()=>suggest('char'),100);
  out.render_time_aba=time(()=>{render()},50);
  document.querySelector('#tab-battle').click();
  out.render_batalha=time(()=>{render()},50);
  document.querySelector('#tab-plan').click();
  out.render_planos=time(()=>{render()},20);
  return out}"""
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page()
    pg.goto(f"http://127.0.0.1:{srv.server_port}/index.html")
    pg.wait_for_function("()=>document.body.dataset.ready==='1'")
    print(pg.evaluate(JS)); b.close()
