"""Infra de testes: servidor estático, Chromium (Playwright) e medição de cobertura do JS via CDP."""
import functools, http.server, json, pathlib, re, socket, threading

import pytest
from playwright.sync_api import sync_playwright

ROOT = pathlib.Path(__file__).resolve().parent.parent / "src"
HTML = (ROOT / "index.html").read_text(encoding="utf-8")
SCRIPT = re.search(r"<script>(.*?)</script>", HTML, re.S).group(1)
COVERED = bytearray(len(SCRIPT))  # 1 = executado em algum teste

def _png(w=4, h=2):
    import struct, zlib
    def chunk(t, d):
        c = struct.pack(">I", len(d)) + t + d
        return c + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)
    raw = b"".join(b"\x00" + b"\xff\x80\x00" * w for _ in range(h))
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b"")


PNG = _png()


class _Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


@pytest.fixture(scope="session")
def server():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", port), functools.partial(_Quiet, directory=str(ROOT)))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{port}"
    srv.shutdown()


@pytest.fixture(scope="session")
def browser():
    with sync_playwright() as p:
        b = p.chromium.launch()
        yield b
        b.close()


def _merge(entries):
    ranges = []
    for e in entries:
        if not e["url"].endswith("/index.html"):
            continue
        for fn in e["functions"]:
            for r in fn["ranges"]:
                ranges.append((r["startOffset"], -r["endOffset"], r["count"] > 0))
    ranges.sort()
    mask = bytearray(len(SCRIPT))
    for start, neg_end, hit in ranges:  # externos primeiro, internos sobrescrevem
        end = min(-neg_end, len(SCRIPT))
        mask[start:end] = bytes([1 if hit else 0]) * max(0, end - start)
    for i, v in enumerate(mask):
        if v:
            COVERED[i] = 1


def claude_mock(sample=True, dictation=True, limits="images", use_throws=False):
    cfg = json.dumps(dict(sample=sample, dict=dictation, limits=limits, use_throws=use_throws))
    return """(()=>{
 const cfg=%s;
 window.__calls=[];
 window.__s={impl:async()=>({text:'{"pokemon":[]}'})};
 window.__d={partial:null,final:null,state:null,starts:0,stops:0,startImpl:async()=>{},stopImpl:async()=>{}};
 const sample=async(p,o)=>{window.__calls.push({p,o});return window.__s.impl(p,o)};
 if(cfg.limits==='images')sample.limits=async()=>({images:true});
 else if(cfg.limits==='noimages')sample.limits=async()=>({images:false});
 else if(cfg.limits==='null')sample.limits=async()=>null;
 else if(cfg.limits==='throws')sample.limits=async()=>{throw new Error('x')};
 const dict={onPartial:f=>{window.__d.partial=f},onFinal:f=>{window.__d.final=f},onState:f=>{window.__d.state=f},
   start:()=>{window.__d.starts++;return window.__d.startImpl()},stop:()=>{window.__d.stops++;return window.__d.stopImpl()}};
 window.claude={use:async n=>{if(cfg.use_throws)throw new Error('boom');
   if(n==='sample')return cfg.sample?sample:null; if(n==='dictation')return cfg.dict?dict:null; return null;}};
})();""" % cfg


def open_page(browser, server, init=(), route=None, ready=True):
    ctx = browser.new_context(viewport={"width": 390, "height": 844})
    for s in init:
        ctx.add_init_script(s)
    page = ctx.new_page()
    page.errors = []
    page.on("pageerror", lambda e: page.errors.append(str(e)))
    if route:
        route(page)
    url = server + "/index.html"
    page.goto(url)
    cdp = ctx.new_cdp_session(page)
    cdp.send("Profiler.enable")
    cdp.send("Profiler.startPreciseCoverage", {"callCount": True, "detailed": True})

    def snap():
        _merge(cdp.send("Profiler.takePreciseCoverage")["result"])

    def wait():
        if ready:
            page.wait_for_function("()=>document.body.dataset.ready==='1'")
        else:
            page.wait_for_function("()=>document.querySelector('#out').textContent.includes('Erro')")

    def reload():
        snap()
        page.reload()
        wait()

    page.snap, page.reload_app, page.wait_app = snap, reload, wait
    page.reload_app()
    return ctx, page


@pytest.fixture
def mk(browser, server):
    opened = []

    def make(init=(), route=None, ready=True):
        ctx, page = open_page(browser, server, init, route, ready)
        opened.append((ctx, page))
        return page

    yield make
    for ctx, page in opened:
        page.snap()
        errors = page.errors
        ctx.close()
        assert not errors, errors


@pytest.fixture
def app(mk):
    return mk()


@pytest.fixture(scope="module")
def u(browser, server):
    """Página compartilhada por testes de funções puras (não alteram estado global)."""
    ctx, page = open_page(browser, server)
    yield page
    page.snap()
    ctx.close()


def uncovered_segments():
    """Trechos relevantes (com letras/dígitos) que nenhum teste executou."""
    segs, i, n = [], 0, len(SCRIPT)
    comments = [(m.start(), m.end()) for m in re.finditer(r"/\*.*?\*/|//[^\n]*", SCRIPT, re.S)]
    skip = bytearray(n)
    for a, b in comments:
        skip[a:b] = b"\x01" * (b - a)
    while i < n:
        if not COVERED[i] and not skip[i]:
            j = i
            while j < n and not COVERED[j] and not skip[j]:
                j += 1
            txt = SCRIPT[i:j]
            if re.search(r"[A-Za-z0-9_$'`\"]", txt.replace("\n", " ")):
                line = SCRIPT.count("\n", 0, i) + 1
                segs.append((line, txt.strip()[:120]))
            i = j
        else:
            i += 1
    return segs
