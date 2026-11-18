"""Modo Vercel: foto via /api/identify, voz via Web Speech, service worker, instalação e código de acesso."""
import json
import pytest
from conftest import PNG

NO_SPEECH = "delete window.SpeechRecognition;delete window.webkitSpeechRecognition;"
SPEECH = """
window.__rec=null;
window.SpeechRecognition=window.webkitSpeechRecognition=class{
  constructor(){window.__rec=this;this.started=0;this.stopped=0;this.fail=null;}
  start(){if(this.fail==='throw')throw new Error('x');this.started++;setTimeout(()=>{if(this.fail)this.onerror({error:this.fail});else this.onstart&&this.onstart();},0);}
  stop(){this.stopped++;this.onend&&this.onend();}
};
"""


def hidden(p, sel):
    return p.eval_on_selector(sel, "e=>e.hidden")


def api(health=None, ident=None, calls=None):
    """Monta as rotas /api/health e /api/identify."""
    def setup(pg):
        def h(r):
            if health == "fail":
                return r.abort()
            if health == "500":
                return r.fulfill(status=500, body="x")
            r.fulfill(status=200, content_type="application/json", body=json.dumps(health))

        def i(r):
            if calls is not None:
                calls.append((r.request.headers, json.loads(r.request.post_data)))
            st, body = ident or (200, {"text": '{"pokemon":["Gengar"]}'})
            r.fulfill(status=st, content_type="application/json", body=json.dumps(body))
        pg.route("**/api/health", h)
        pg.route("**/api/identify", i)
    return setup


def upload(p):
    p.set_input_files("#file", {"name": "a.png", "mimeType": "image/png", "buffer": PNG})


def test_sem_api_campo_de_codigo_nao_aparece(mk):
    p = mk([NO_SPEECH], route=api("fail"))
    assert not p.is_visible("#code-row")


def test_health_sem_visao_ou_com_falha_esconde_fotos(mk):
    for health in ({"ok": True, "vision": False}, "fail", "500"):
        p = mk([NO_SPEECH], route=api(health))
        assert hidden(p, "#team-photo") and hidden(p, "#opp-photo")
        assert hidden(p, "#code-row")


def test_foto_do_oponente_via_api_envia_codigo_e_modo(mk):
    calls = []
    p = mk([NO_SPEECH, "localStorage.setItem('pbh-code','abc')"], route=api({"ok": True, "vision": True, "needsCode": True}, calls=calls))
    assert not hidden(p, "#opp-photo") and hidden(p, "#code-row")
    p.click("#tab-battle")
    p.click("#opp-photo")
    upload(p)
    p.wait_for_function("()=>document.querySelector('#opp-status').textContent.startsWith('Li:')")
    hdrs, body = calls[0]
    assert hdrs["x-access-code"] == "abc" and body["mode"] == "opp" and len(body["image"]) > 20
    assert p.evaluate("()=>opp") == "Gengar"


def test_foto_do_time_via_api(mk):
    p = mk([NO_SPEECH], route=api({"ok": True, "vision": True}, ident=(200, {"text": '{"pokemon":["Gengar","Garchomp"]}'})))
    p.click("#team-photo")
    upload(p)
    p.wait_for_function("()=>team.length===2")


def test_precisa_de_codigo_mostra_campo_e_salva(mk):
    p = mk([NO_SPEECH], route=api({"ok": True, "vision": True, "needsCode": True}))
    assert not hidden(p, "#code-row")
    p.click("#code-save")  # vazio: ignora
    assert not hidden(p, "#code-row")
    p.fill("#code-in", " segredo ")
    p.click("#code-save")
    assert hidden(p, "#code-row") and p.evaluate("()=>localStorage.getItem('pbh-code')") == "segredo"
    assert not p.is_visible("#code-row")  # visualmente some (display:flex não pode vencer [hidden])


def test_salvar_codigo_sem_localstorage_nao_quebra(mk):
    p = mk([NO_SPEECH], route=api({"ok": True, "vision": True, "needsCode": True}))
    p.evaluate("()=>{Storage.prototype.setItem=()=>{throw new Error('x')}}")
    p.fill("#code-in", "x")
    p.click("#code-save")
    assert hidden(p, "#code-row")


@pytest.mark.parametrize("status,texto", [(401, "código de acesso"), (429, "Muitas leituras"), (502, "Falhou")])
def test_erros_da_api_viram_mensagens(mk, status, texto):
    p = mk([NO_SPEECH, "localStorage.setItem('pbh-code','x')"], route=api({"ok": True, "vision": True}, ident=(status, {"error": "e"})))
    p.click("#tab-battle")
    p.click("#opp-photo")
    upload(p)
    p.wait_for_function("t=>document.querySelector('#opp-status').textContent.includes(t)", arg=texto)
    if status == 401:
        assert not hidden(p, "#code-row")


def test_codigo_sem_localstorage_lido_como_vazio(mk):
    p = mk([NO_SPEECH, "Storage.prototype.getItem=()=>{throw new Error('x')}"], route=api({"ok": True, "vision": True, "needsCode": True}))
    assert not hidden(p, "#code-row")


# ---------- voz ----------
def test_sem_speech_esconde_microfone(mk):
    assert hidden(mk([NO_SPEECH]), "#opp-mic")


def test_voz_parcial_final_e_parar(mk):
    p = mk([SPEECH])
    assert not hidden(p, "#opp-mic")
    p.click("#tab-battle")
    p.click("#opp-mic")
    p.wait_for_function("()=>document.querySelector('#opp-mic').textContent==='⏹'")
    p.evaluate("()=>{const r=window.__rec;r.onresult({results:[Object.assign([{transcript:'gen'}],{isFinal:false})]})}")
    assert p.input_value("#opp-in") == "gen"
    p.evaluate("()=>{const r=window.__rec;r.onresult({results:[Object.assign([{transcript:'gengar'}],{isFinal:true})]})}")
    assert p.evaluate("()=>opp") == "Gengar"
    p.click("#opp-mic")  # ainda ouvindo: para
    p.wait_for_function("()=>document.querySelector('#opp-mic').textContent==='🎙️'")
    assert p.evaluate("()=>window.__rec.stopped") == 1


@pytest.mark.parametrize("fail,esconde", [("not-allowed", True), ("service-not-allowed", True), ("network", False), ("throw", False)])
def test_voz_erros(mk, fail, esconde):
    p = mk([SPEECH])
    p.click("#tab-battle")
    p.evaluate("f=>{window.__rec.fail=f}", fail)
    p.click("#opp-mic")
    p.wait_for_timeout(100)
    assert hidden(p, "#opp-mic") == esconde


# ---------- service worker / instalação ----------
def test_registra_service_worker(mk):
    p = mk(["window.__reg=[];navigator.serviceWorker.register=u=>{window.__reg.push(u);return Promise.resolve({})}"], route=api("fail"))
    assert p.evaluate("()=>window.__reg") == ["sw.js"]


def test_falha_no_registro_do_sw_e_silenciosa(mk):
    mk(["navigator.serviceWorker.register=()=>Promise.reject(new Error('x'))"], route=api("fail"))
    mk(["navigator.serviceWorker.register=()=>{throw new Error('x')}"], route=api("fail"))


def test_sem_service_worker_no_navegador(mk):
    mk(["Object.defineProperty(Navigator.prototype,'serviceWorker',{get:()=>undefined});"], route=api("fail"))


def test_botao_instalar(mk):
    p = mk([NO_SPEECH], route=api("fail"))
    assert hidden(p, "#install-btn")
    p.evaluate("""()=>{const e=new Event('beforeinstallprompt',{cancelable:true});
      e.prompt=()=>{window.__prompted=1};e.userChoice=Promise.resolve({outcome:'accepted'});window.dispatchEvent(e)}""")
    assert not hidden(p, "#install-btn")
    p.click("#install-btn")
    p.wait_for_function("()=>document.querySelector('#install-btn').hidden")
    assert p.evaluate("()=>window.__prompted") == 1


def test_pagina_tem_pwa_e_csp_placeholder(mk):
    p = mk([NO_SPEECH], route=api("fail"))
    assert p.get_attribute("link[rel=manifest]", "href") == "manifest.webmanifest"
    assert p.get_attribute("meta[name=theme-color]", "content")
