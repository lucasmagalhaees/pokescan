"""Testes e2e da interface (Chromium real): fluxo do usuário, persistência, golpes, planos, foto e voz."""
import json
import pytest
from conftest import PNG, claude_mock

TEAM = ["Garchomp", "Corviknight", "Gengar", "Kingambit", "Charizard", "Pikachu"]


def hidden(page, sel):
    return page.eval_on_selector(sel, "e=>e.hidden")


def add(page, *names):
    for n in names:
        page.fill("#team-in", n)
        page.press("#team-in", "Enter")


def team(page):
    return page.evaluate("()=>team")


def set_state(page, names=None, opp=None, mode=None, mv=None):
    page.evaluate("([t,o,m,mv])=>{team=t;opp=o;if(m)mode=m;MV=mv||{};render();}", [names or [], opp, mode, mv])


def stub_analyse(page, **r):
    page.evaluate("""r=>{analyse=(me,op)=>({me,dealt:[{nm:'Golpe A',t:0,e:1,pct:r.dmax}],taken:[{nm:'Golpe B',t:1,e:1,pct:r.tmax}],
      dmax:r.dmax,tmax:r.tmax,faster:r.faster,tie:r.tie,myT:r.myT,opT:r.opT,risk:r.risk})}""", r)


def seed_storage(**kv):
    return "(()=>{" + "".join(f"localStorage.setItem({json.dumps(k)},{json.dumps(v)});" for k, v in kv.items()) + "})();"


# ---------- abas ----------
def test_abas_alternam_secoes(app):
    for tab, sec in [("battle", "#sec-battle"), ("plan", "#sec-plan"), ("team", "#sec-team")]:
        app.click(f"#tab-{tab}")
        assert app.is_visible(sec)
        assert app.eval_on_selector(f"#tab-{tab}", "e=>e.classList.contains('on')")
    assert not app.is_visible("#sec-battle") and not app.is_visible("#sec-plan")


def test_titulo_e_estado_inicial(app):
    assert "Pokémon Battle Helper" in app.inner_text("h1")
    assert app.inner_text("#team-n") == "0" and "Adicione até 6" in app.inner_text("#team-list")


# ---------- time ----------
def test_adiciona_por_enter_e_botao(app):
    add(app, "garchomp")
    app.fill("#team-in", "gengar")
    app.click("#team-add")
    assert team(app) == ["Garchomp", "Gengar"] and app.inner_text("#team-n") == "2"


def test_nome_invalido_mostra_aviso(app):
    add(app, "zzzzzz")
    assert "Não achei" in app.inner_text("#team-status") and team(app) == []


def test_sugestoes_clicaveis(app):
    app.fill("#team-in", "garch")
    app.click("#team-sug [data-n='Garchomp']")
    assert team(app) == ["Garchomp"] and app.input_value("#team-in") == ""


def test_clique_fora_das_sugestoes_nao_faz_nada(app):
    app.fill("#team-in", "garch")
    app.click("#team-sug", position={"x": 2, "y": 2}) if app.locator("#team-sug").bounding_box()["width"] > 4 else None
    app.evaluate("()=>document.querySelector('#team-sug').click()")
    assert team(app) == []


def test_tecla_diferente_de_enter_nao_confirma(app):
    app.fill("#team-in", "garchomp")
    app.press("#team-in", "a")
    assert team(app) == []


def test_duplicado_e_ignorado(app):
    add(app, "garchomp", "garchomp")
    assert team(app) == ["Garchomp"]


def test_limite_de_6(app):
    add(app, *TEAM, "Gyarados")
    assert len(team(app)) == 6 and "Time cheio" in app.inner_text("#team-status")


def test_remove_membro_e_limpa_golpes(app):
    add(app, "garchomp", "gengar")
    app.click("[data-sel='Garchomp']")
    app.fill("#mv-in", "earth")
    app.press("#mv-in", "Enter")
    app.click("[data-i='0']")
    assert team(app) == ["Gengar"] and app.evaluate("()=>MV") == {} and app.is_hidden("#mv-panel")


def test_remove_outro_membro_mantem_painel_aberto(app):
    add(app, "garchomp", "gengar")
    app.click("[data-sel='Garchomp']")
    app.click("[data-i='1']")
    assert app.is_visible("#mv-panel") and team(app) == ["Garchomp"]


def test_limpar_time(app):
    add(app, "garchomp")
    app.click("[data-sel='Garchomp']")
    app.click("#team-clear")
    assert team(app) == [] and app.is_hidden("#mv-panel")


def test_clique_em_area_vazia_da_lista_nao_faz_nada(app):
    add(app, "garchomp")
    app.evaluate("()=>document.querySelector('#team-list').click()")
    assert app.is_hidden("#mv-panel")


def test_chip_alterna_selecao(app):
    add(app, "garchomp")
    app.click("[data-sel='Garchomp']")
    assert app.is_visible("#mv-panel") and app.inner_text("#mv-title") == "Garchomp"
    app.click("[data-sel='Garchomp']")
    assert app.is_hidden("#mv-panel")


def test_render_com_nome_desconhecido_no_time_nao_quebra(app):
    set_state(app, ["Nope"])
    assert "Nope" in app.inner_text("#team-list")


# ---------- golpes opcionais ----------
def test_marca_golpe_por_sugestao_e_enter(app):
    add(app, "garchomp")
    app.click("[data-sel='Garchomp']")
    app.fill("#mv-in", "earthq")
    app.click("#mv-sug [data-mn='Earthquake']")
    app.fill("#mv-in", "outra")
    app.press("#mv-in", "Enter")
    assert app.evaluate("()=>MV") == {"Garchomp": ["Earthquake", "Outrage"]}
    assert "✎2/4" in app.inner_text("#team-list")


def test_sugestoes_de_golpe_so_do_que_ele_aprende(app):
    add(app, "garchomp")
    app.click("[data-sel='Garchomp']")
    fora = app.evaluate("()=>DB.moves.find((m,i)=>!DB.species[SPI.Garchomp][3].includes(i)&&i<DB.moves.length-18)[0]")
    app.fill("#mv-in", fora)
    chips = app.eval_on_selector_all("#mv-sug [data-mn]", "e=>e.map(x=>x.dataset.mn)")
    assert fora not in chips


def test_golpe_sem_sugestao_ignora_enter_e_outras_teclas(app):
    add(app, "garchomp")
    app.click("[data-sel='Garchomp']")
    app.fill("#mv-in", "zzzz")
    app.press("#mv-in", "Enter")
    app.press("#mv-in", "a")
    assert app.evaluate("()=>MV") == {}


def test_input_de_golpe_sem_selecao_nao_sugere(app):
    assert app.evaluate("()=>{$('#mv-in').value='earth';return moveSug()}") == []


def test_maximo_4_golpes_e_sem_duplicata(app):
    add(app, "garchomp")
    app.click("[data-sel='Garchomp']")
    for q in ["earthq", "outra", "earthq", "stone", "crunch", "dragon cl"]:
        if app.is_enabled("#mv-in"):
            app.fill("#mv-in", q)
            app.press("#mv-in", "Enter")
    mv = app.evaluate("()=>MV.Garchomp")
    assert len(mv) == 4 and len(set(mv)) == 4 and app.is_disabled("#mv-in")


def test_addMove_alem_do_limite_e_ignorado(app):
    add(app, "garchomp")
    app.evaluate("()=>{selMon='Garchomp';MV={Garchomp:['A','B','C','D']};addMove('Earthquake')}")
    assert app.evaluate("()=>MV.Garchomp") == ["A", "B", "C", "D"]


def test_remove_golpe_e_apaga_entrada_quando_vazio(app):
    add(app, "garchomp")
    app.click("[data-sel='Garchomp']")
    for q in ["earthq", "outra"]:
        app.fill("#mv-in", q)
        app.press("#mv-in", "Enter")
    app.click("[data-mi='0']")
    assert app.evaluate("()=>MV.Garchomp") == ["Outrage"]
    app.click("[data-mi='0']")
    assert app.evaluate("()=>MV") == {} and "Nenhum marcado" in app.inner_text("#mv-list")


def test_cliques_em_areas_vazias_do_painel(app):
    add(app, "garchomp")
    app.click("[data-sel='Garchomp']")
    app.evaluate("()=>{document.querySelector('#mv-sug').click();document.querySelector('#mv-list').click()}")
    assert app.evaluate("()=>MV") == {}


def test_golpes_marcados_mudam_o_resultado(app):
    set_state(app, ["Garchomp"], "Corviknight")
    app.click("#tab-battle")
    antes = app.inner_text("#out .res")
    set_state(app, ["Garchomp"], "Corviknight", mv={"Garchomp": ["Earthquake"]})
    depois = app.inner_text("#out .res")
    assert "Earthquake" in depois and antes != depois and "Dá" in depois


# ---------- batalha ----------
def test_batalha_sem_time(app):
    app.click("#tab-battle")
    assert "Monte seu time" in app.inner_text("#out")


def test_batalha_sem_oponente(app):
    add(app, "garchomp")
    app.click("#tab-battle")
    assert "Informe o oponente" in app.inner_text("#out")


def test_oponente_por_texto_e_ranking(app):
    add(app, *TEAM)
    app.click("#tab-battle")
    app.fill("#opp-in", "greninja")
    app.press("#opp-in", "Enter")
    nomes = app.eval_on_selector_all(".res .name", "e=>e.map(x=>x.innerText)")
    assert sorted(nomes) == sorted(TEAM) and app.input_value("#opp-in") == "Greninja"
    assert "MELHOR ESCOLHA" in app.inner_text(".res.top .rank")


def test_oponente_nome_invalido(app):
    app.click("#tab-battle")
    app.fill("#opp-in", "zzzzzz")
    app.press("#opp-in", "Enter")
    assert "Não achei" in app.inner_text("#opp-status")


def test_oponente_sugestoes_e_clique(app):
    app.click("#tab-battle")
    app.fill("#opp-in", "gren")
    app.click("#opp-sug [data-n='Greninja']")
    assert app.evaluate("()=>opp") == "Greninja"


def test_oponente_outra_tecla_e_clique_vazio(app):
    app.click("#tab-battle")
    app.fill("#opp-in", "gren")
    app.press("#opp-in", "a")
    app.evaluate("()=>document.querySelector('#opp-sug').click()")
    assert app.evaluate("()=>opp") is None


@pytest.mark.parametrize("modo", ["def", "agr"])
def test_alternar_modo_em_ambos_os_seletores(app, modo):
    add(app, *TEAM)
    set_state(app, TEAM, "Greninja")
    app.click("#tab-battle")
    app.click(f"#mode [data-m='{modo}']")
    assert app.evaluate("()=>mode") == modo
    assert app.eval_on_selector(f"#mode2 [data-m='{modo}']", "e=>e.classList.contains('on')")
    app.click("#tab-plan")
    app.click(f"#mode2 [data-m='{modo}']")
    assert app.evaluate("()=>mode") == modo


def test_clique_fora_do_seletor_de_modo_ignorado(app):
    app.evaluate("()=>document.body.click()")
    assert app.evaluate("()=>mode") == "def"


def test_modo_muda_a_ajuda(app):
    add(app, "garchomp")
    app.click("#tab-battle")
    d = app.inner_text("#mode-help")
    app.click("#mode [data-m='agr']")
    assert app.inner_text("#mode-help") != d


def test_modos_podem_trazer_ordens_diferentes(app):
    ordens = {}
    for m in ["def", "agr"]:
        set_state(app, TEAM, "Greninja", mode=m)
        app.click("#tab-battle")
        ordens[m] = app.eval_on_selector_all(".res .name", "e=>e.map(x=>x.innerText)")
    assert sorted(ordens["def"]) == sorted(ordens["agr"])


@pytest.mark.parametrize("caso,esperado", [
    (dict(dmax=120, tmax=10, faster=True, tie=False, myT=1, opT=9, risk=False),
     ["Ataca primeiro", "Você mata em 1 golpe", "Ele mata em 9", "color:var(--ok)", "MELHOR ESCOLHA"]),
    (dict(dmax=60, tmax=60, faster=False, tie=True, myT=2, opT=2, risk=False),
     ["Speed empatada", "Você mata em 2 golpes", "color:var(--warn)"]),
    (dict(dmax=20, tmax=120, faster=False, tie=False, myT=99, opT=99, risk=False),
     ["Ele ataca primeiro", "Você mata em —", "Ele mata em —", "color:var(--bad)"]),
    (dict(dmax=30, tmax=60, faster=False, tie=False, myT=5, opT=2, risk=False), ["b-bad"]),
    (dict(dmax=50, tmax=150, faster=False, tie=False, myT=2, opT=1, risk=True), ["morre em 1 golpe", "risk"]),
])
def test_render_cartoes(app, caso, esperado):
    set_state(app, ["Garchomp"], "Gengar")
    app.click("#tab-battle")
    stub_analyse(app, **caso)
    app.evaluate("()=>render()")
    html = app.inner_html("#out")
    for e in esperado:
        assert e in html
    if caso["risk"]:
        assert "MELHOR ESCOLHA" not in html


def test_cartao_mostra_cura_e_buff(app):
    app.click("#tab-battle")
    set_state(app, TEAM, "Greninja")
    html = app.evaluate("()=>document.querySelector('#out').textContent")
    assert html.count("💊") == 6 and html.count("⚡") == 6


# ---------- planos ----------
def test_planos_sem_time(app):
    app.click("#tab-plan")
    assert "Monte seu time" in app.inner_text("#plan-out")


def test_planos_ate_5_com_ordem_e_dicas(app):
    add(app, *TEAM)
    app.click("#tab-plan")
    cards = app.locator("#plan-out >> text=/^Plano \\d/").count()
    txt = app.inner_text("#plan-out")
    assert 1 <= cards <= 5 and "💊" in txt and "⚡" in txt and "Mande:" in txt


def test_planos_alertas_de_fraqueza_comum(app):
    add(app, "gengar", "kingambit", "pikachu")
    app.click("#tab-plan")
    assert "Ground" in app.inner_text("#plan-out") and "do time" in app.inner_text("#plan-out")


def test_planos_alerta_com_resistentes_nomeados(app):
    add(app, "gengar", "kingambit", "pikachu", "corviknight")
    app.click("#tab-plan")
    assert "Resistem: Corviknight" in app.inner_text("#plan-out")


def test_planos_sem_alertas_quando_time_resiste_a_tudo(app):
    set_state(app, ["Garchomp"])
    app.evaluate("()=>{DB.eff=DB.eff.map(r=>r.map(()=>0.5))}")
    app.click("#tab-plan")
    t = app.inner_text("#plan-out")
    assert "Nenhum tipo pega vários" in t and "Nenhum cenário preocupante" in t


def test_planos_buracos_ofensivos_pedem_golpes(app):
    add(app, "garchomp")
    app.click("#tab-plan")
    assert "Marque os golpes" in app.inner_text("#plan-out")


def test_planos_buracos_ofensivos_listados(app):
    set_state(app, ["Garchomp"], mv={"Garchomp": ["Earthquake"]})
    app.click("#tab-plan")
    assert "Ninguém acerta super efetivo em" in app.inner_text("#plan-out")


def test_planos_cobertura_completa(app):
    app.evaluate("""()=>{
      const names=['Mew','Garchomp','Gengar','Corviknight','Charizard','Pikachu'];
      const t=names.filter(n=>SPI[n]!=null);team=t;MV={};
      for(let d=0;d<18;d++){let done=false;
        for(const n of t){const sp=DB.species[SPI[n]];
          for(const i of sp[3]){if(effVs(DB.moves[i][1],[d])>=2){(MV[n]=MV[n]||[]).push(DB.moves[i][0]);done=true;break}}
          if(done)break}}
      render();}""")
    app.click("#tab-plan")
    assert "cobrem todos os tipos" in app.inner_text("#plan-out")


def test_planos_time_de_1_nao_tem_reserva_e_marca_nenhum_segura(app):
    set_state(app, ["Pikachu"])
    app.click("#tab-plan")
    t = app.inner_text("#plan-out")
    assert "Reserva" not in t and "nenhum segura bem" in t


def test_planos_modo_agressivo(app):
    add(app, *TEAM)
    app.click("#tab-plan")
    app.click("#mode2 [data-m='agr']")
    assert "Plano 1" in app.inner_text("#plan-out")


# ---------- persistência ----------
def test_time_e_golpes_persistem_apos_reload(app):
    add(app, "garchomp", "gengar")
    app.click("[data-sel='Garchomp']")
    app.fill("#mv-in", "earthq")
    app.press("#mv-in", "Enter")
    app.reload_app()
    assert team(app) == ["Garchomp", "Gengar"] and app.evaluate("()=>MV") == {"Garchomp": ["Earthquake"]}


def test_storage_filtra_desconhecidos_e_limita_a_6(mk):
    p = mk([seed_storage(**{"pbh-team": json.dumps(["Garchomp", "Nope"] + TEAM)})])
    assert team(p) == ["Garchomp", "Corviknight", "Gengar", "Kingambit", "Charizard", "Pikachu"]


@pytest.mark.parametrize("team_v,mv_v", [
    ("{\"a\":1}", "{}"), ("{bad json", "{}"), ("[\"Garchomp\"]", "null"), ("[\"Garchomp\"]", "5"),
])
def test_storage_invalido_nao_quebra(mk, team_v, mv_v):
    p = mk([seed_storage(**{"pbh-team": team_v, "pbh-mv": mv_v})])
    assert isinstance(team(p), list) and p.evaluate("()=>typeof MV") == "object"


def test_storage_bloqueado_nao_quebra_ao_salvar(mk):
    p = mk(["Storage.prototype.setItem=function(){throw new Error('quota')}"])
    add(p, "garchomp")
    assert team(p) == ["Garchomp"]


# ---------- falha ao carregar ----------
def test_erro_ao_carregar_dados(mk):
    p = mk(route=lambda pg: pg.route("**/data.json", lambda r: r.fulfill(status=500, body="x")), ready=False)
    assert "Erro ao carregar" in p.text_content("#out")


# ---------- integrações Claude (foto / voz) ----------
NO_SPEECH = "delete window.SpeechRecognition;delete window.webkitSpeechRecognition;"


def test_sem_claude_esconde_foto_e_voz(mk):
    app = mk([NO_SPEECH])
    assert all(hidden(app, s) for s in ["#team-photo", "#opp-photo", "#opp-mic"])


def test_foto_sem_sample_avisa(app):
    app.evaluate("()=>{photoMode='team'}")
    app.set_input_files("#file", {"name": "a.png", "mimeType": "image/png", "buffer": PNG})
    assert "indisponível" in app.inner_text("#team-status")


def test_com_claude_mostra_foto_e_voz(mk):
    p = mk([claude_mock()])
    assert not any(hidden(p, s) for s in ["#team-photo", "#opp-photo", "#opp-mic"])
    p.click("#tab-battle")
    assert p.is_visible("#opp-photo") and p.is_visible("#opp-mic")


@pytest.mark.parametrize("kw,foto,voz", [
    (dict(sample=False), False, True),
    (dict(dictation=False), True, False),
    (dict(limits="none"), True, True),
    (dict(limits="noimages"), False, True),
    (dict(limits="null"), False, True),
    (dict(limits="throws"), False, True),
    (dict(use_throws=True), False, False),
])
def test_capacidades_variadas(mk, kw, foto, voz):
    p = mk([claude_mock(**kw), "delete window.SpeechRecognition;delete window.webkitSpeechRecognition;"])
    assert (not hidden(p, "#team-photo")) == foto and (not hidden(p, "#opp-mic")) == voz


def _upload(p, content=PNG, name="a.png", mime="image/png"):
    p.set_input_files("#file", {"name": name, "mimeType": mime, "buffer": content})


def _sample_returns(p, text):
    p.evaluate("t=>{window.__s.impl=async()=>({text:t})}", text)


def test_foto_do_time_adiciona_ate_6_e_ignora_invalidos(mk):
    p = mk([claude_mock()])
    _sample_returns(p, 'ok {"pokemon":["Garchomp","Gengar","Garchomp","Xyzzyqq","Corviknight","Kingambit","Charizard","Pikachu","Gyarados"]}')
    with p.expect_file_chooser() as fc:
        p.click("#team-photo")
    fc.value.set_files({"name": "t.png", "mimeType": "image/png", "buffer": PNG})
    p.wait_for_function("()=>team.length===6")
    assert team(p) == ["Garchomp", "Gengar", "Corviknight", "Kingambit", "Charizard", "Pikachu"]
    assert "Time lido" in p.inner_text("#team-status")
    call = p.evaluate("()=>window.__calls[0]")
    assert "time/party" in call["p"] and call["o"]["modelTier"] == "quick" and call["o"]["cache"] is False


def test_foto_do_oponente_um_so(mk):
    p = mk([claude_mock()])
    _sample_returns(p, '{"pokemon":["Greninja"]}')
    p.click("#tab-battle")
    with p.expect_file_chooser() as fc:
        p.click("#opp-photo")
    fc.value.set_files({"name": "o.png", "mimeType": "image/png", "buffer": PNG})
    p.wait_for_function("()=>opp==='Greninja'")
    assert p.inner_text("#opp-status") == "Li: Greninja"
    assert "OPONENTE" in p.evaluate("()=>window.__calls[0].p")


def test_foto_do_oponente_varios_mostra_os_outros(mk):
    p = mk([claude_mock()])
    _sample_returns(p, '{"pokemon":["Greninja","Gengar"]}')
    p.evaluate("()=>{photoMode='opp'}")
    _upload(p)
    p.wait_for_function("()=>opp==='Greninja'")
    assert "também vi Gengar" in p.inner_text("#opp-status")


@pytest.mark.parametrize("text", ["sem json nenhum", '{"outro":1}', '{"pokemon":["Xyzzyqq"]}', '{"pokemon":[]}'])
def test_foto_sem_resultado_util(mk, text):
    p = mk([claude_mock()])
    _sample_returns(p, text)
    p.evaluate("()=>{photoMode='opp'}")
    _upload(p)
    p.wait_for_function("()=>document.querySelector('#opp-status').textContent.includes('Não consegui')")


def test_foto_resposta_sem_texto(mk):
    p = mk([claude_mock()])
    p.evaluate("()=>{window.__s.impl=async()=>({})}")
    p.evaluate("()=>{photoMode='opp'}")
    _upload(p)
    p.wait_for_function("()=>document.querySelector('#opp-status').textContent.includes('Não consegui')")


@pytest.mark.parametrize("err,msg", [
    ("{code:'not_granted'}", "Permissão negada"),
    ("{code:'rate_limited'}", "Muitas leituras"),
    ("new Error('x')", "Falhou ao ler"),
    ("null", "Falhou ao ler"),
])
def test_foto_erros_do_claude(mk, err, msg):
    p = mk([claude_mock()])
    p.evaluate(f"()=>{{window.__s.impl=async()=>{{throw {err}}}}}")
    p.evaluate("()=>{photoMode='opp'}")
    _upload(p)
    p.wait_for_function("m=>document.querySelector('#opp-status').textContent.includes(m)", arg=msg)


def test_foto_arquivo_invalido(mk):
    p = mk([claude_mock()])
    p.evaluate("()=>{photoMode='opp'}")
    _upload(p, b"isto nao e imagem")
    p.wait_for_function("()=>document.querySelector('#opp-status').textContent.includes('Falhou')")


def test_foto_canvas_sem_blob(mk):
    p = mk([claude_mock(), "HTMLCanvasElement.prototype.toBlob=function(cb){cb(null)}"])
    p.evaluate("()=>{photoMode='opp'}")
    _upload(p)
    p.wait_for_function("()=>document.querySelector('#opp-status').textContent.includes('Falhou')")


def test_selecionar_arquivo_vazio_nao_faz_nada(mk):
    p = mk([claude_mock()])
    p.evaluate("()=>document.querySelector('#file').dispatchEvent(new Event('change'))")
    assert p.evaluate("()=>window.__calls.length") == 0


def _dict(p):
    p.wait_for_function("()=>window.__d.final!==null")
    p.click("#tab-battle")


def test_voz_final_reconhecida(mk):
    p = mk([claude_mock()])
    _dict(p)
    p.evaluate("()=>window.__d.partial({text:'gren'})")
    assert p.input_value("#opp-in") == "gren"
    p.evaluate("()=>window.__d.final({text:'greninja'})")
    assert p.evaluate("()=>opp") == "Greninja"


def test_voz_final_nao_reconhecida(mk):
    p = mk([claude_mock()])
    _dict(p)
    p.evaluate("()=>window.__d.final({text:'zzzzzz'})")
    assert "Ouvi" in p.inner_text("#opp-status") and p.evaluate("()=>opp") is None


def test_voz_botao_inicia_e_para(mk):
    p = mk([claude_mock()])
    _dict(p)
    p.click("#opp-mic")
    assert p.evaluate("()=>window.__d.starts") == 1
    p.evaluate("()=>window.__d.state({state:'listening'})")
    assert p.inner_text("#opp-mic") == "⏹" and p.eval_on_selector("#opp-mic", "e=>e.classList.contains('on')")
    p.click("#opp-mic")
    assert p.evaluate("()=>window.__d.stops") == 1
    p.evaluate("()=>window.__d.state({state:'idle'})")
    assert p.inner_text("#opp-mic") == "🎙️"


def test_voz_parar_com_erro_e_ignorado(mk):
    p = mk([claude_mock()])
    _dict(p)
    p.evaluate("()=>{window.__d.stopImpl=async()=>{throw new Error('x')};window.__d.state({state:'listening'})}")
    p.click("#opp-mic")
    assert p.evaluate("()=>window.__d.stops") == 1


def test_voz_negada_esconde_botao(mk):
    p = mk([claude_mock()])
    _dict(p)
    p.evaluate("()=>{window.__d.startImpl=async()=>{throw {code:'not_granted'}}}")
    p.click("#opp-mic")
    p.wait_for_function("()=>document.querySelector('#opp-mic').hidden")
    assert "Microfone negado" in p.inner_text("#opp-status")


@pytest.mark.parametrize("err", ["{code:'dismissed'}", "undefined"])
def test_voz_outros_erros_mantem_botao(mk, err):
    p = mk([claude_mock()])
    _dict(p)
    p.evaluate(f"()=>{{window.__d.startImpl=()=>Promise.reject({err})}}")
    p.click("#opp-mic")
    p.wait_for_function("()=>window.__d.starts===1")
    assert p.is_visible("#opp-mic")


# ---------- jornada completa ----------
def test_jornada_completa(mk):
    p = mk([claude_mock()])
    add(p, "garchomp", "corviknight", "gengar")
    p.click("[data-sel='Garchomp']")
    p.fill("#mv-in", "earthq")
    p.press("#mv-in", "Enter")
    p.click("#tab-battle")
    p.fill("#opp-in", "greninja")
    p.press("#opp-in", "Enter")
    assert p.locator(".res").count() == 3
    p.click("#mode [data-m='agr']")
    assert p.locator(".res.top").count() == 1
    p.click("#tab-plan")
    assert "Plano 1" in p.inner_text("#plan-out")
    p.reload_app()
    assert team(p) == ["Garchomp", "Corviknight", "Gengar"]


# ---------- UX: veredito, fraquezas, recentes, limpar, modo salvo, abas acessíveis ----------
def test_veredito_indica_quem_mandar(app):
    add(app, *TEAM)
    app.click("#tab-battle")
    set_state(app, TEAM, "Greninja")
    melhor = app.inner_text(".res.top .name")
    assert melhor in app.inner_text(".verdict") and "Mande" in app.inner_text(".verdict")


def test_veredito_quando_todos_arriscam(app):
    set_state(app, ["Garchomp", "Gengar"], "Greninja")
    app.click("#tab-battle")
    stub_analyse(app, dmax=50, tmax=150, faster=False, tie=False, myT=2, opT=1, risk=True)
    app.evaluate("()=>render()")
    assert "Todos correm risco" in app.inner_text(".verdict") and app.locator(".res.top").count() == 0


def test_cartoes_secundarios_comecam_recolhidos(app):
    set_state(app, TEAM, "Greninja")
    app.click("#tab-battle")
    abertos = app.eval_on_selector_all(".res", "e=>e.map(x=>x.open)")
    assert abertos == [True] + [False] * 5
    app.click(".res:nth-of-type(3) summary") if False else app.locator(".res").nth(2).locator("summary").click()
    assert app.locator(".res").nth(2).evaluate("e=>e.open")


def test_fraquezas_do_oponente_com_multiplicador(app):
    set_state(app, ["Garchomp"], "Garchomp")
    app.click("#tab-battle")
    txt = app.inner_text("#out .card")
    assert "Fraco a:" in txt and "Ice ×4" in txt


def test_oponente_sem_fraquezas(app):
    set_state(app, ["Garchomp"], "Garchomp")
    app.evaluate("()=>{DB.eff=DB.eff.map(r=>r.map(()=>1))}")
    app.click("#tab-battle")
    assert "Sem fraquezas" in app.inner_text("#out .card")


def test_ir_para_meu_time_no_estado_vazio(app):
    app.click("#tab-battle")
    app.click("#go-team")
    assert app.is_visible("#sec-team") and app.is_hidden("#sec-battle")


def test_clique_em_outro_lugar_do_resultado_nao_muda_de_aba(app):
    add(app, "garchomp")
    app.click("#tab-battle")
    app.evaluate("()=>document.querySelector('#out').click()")
    assert app.is_visible("#sec-battle")


def test_recentes_ordem_dedupe_e_limite(app):
    app.click("#tab-battle")
    for n in ["Greninja", "Gengar", "Garchomp", "Pikachu", "Kingambit", "Charizard", "Gengar"]:
        app.fill("#opp-in", n)
        app.press("#opp-in", "Enter")
    r = app.eval_on_selector_all("#opp-recent [data-r]", "e=>e.map(x=>x.dataset.r)")
    assert r == ["Gengar", "Charizard", "Kingambit", "Pikachu", "Garchomp"]


def test_clicar_recente_define_oponente(app):
    app.click("#tab-battle")
    for n in ["Greninja", "Gengar"]:
        app.fill("#opp-in", n)
        app.press("#opp-in", "Enter")
    app.click("#opp-recent [data-r='Greninja']")
    assert app.evaluate("()=>opp") == "Greninja"
    app.evaluate("()=>document.querySelector('#opp-recent').click()")
    assert app.evaluate("()=>opp") == "Greninja"


def test_recentes_persistem_e_invalidos_sao_filtrados(mk):
    p = mk([seed_storage(**{"pbh-prefs": json.dumps({"mode": "agr", "recent": ["Gengar", "Nope", "Garchomp"]})})])
    assert p.evaluate("()=>RECENT") == ["Gengar", "Garchomp"] and p.evaluate("()=>mode") == "agr"
    assert p.eval_on_selector("#mode [data-m='agr']", "e=>e.classList.contains('on')")


@pytest.mark.parametrize("prefs", [{"mode": "xyz", "recent": "naolista"}, {}])
def test_preferencias_invalidas_usam_padrao(mk, prefs):
    p = mk([seed_storage(**{"pbh-prefs": json.dumps(prefs)})])
    assert p.evaluate("()=>mode") == "def" and p.evaluate("()=>RECENT") == []


def test_modo_escolhido_persiste_apos_reload(app):
    app.click("#tab-battle")
    app.click("#mode [data-m='agr']")
    app.reload_app()
    assert app.evaluate("()=>mode") == "agr"
    assert app.eval_on_selector("#mode2 [data-m='agr']", "e=>e.classList.contains('on')")


def test_limpar_oponente(app):
    add(app, "garchomp")
    app.click("#tab-battle")
    app.fill("#opp-in", "greninja")
    app.press("#opp-in", "Enter")
    app.click("#opp-clear")
    assert app.evaluate("()=>opp") is None and app.input_value("#opp-in") == "" and "Informe o oponente" in app.inner_text("#out")


def test_abas_acessiveis(app):
    assert app.get_attribute("#tab-team", "aria-selected") == "true"
    app.click("#tab-plan")
    assert app.get_attribute("#tab-plan", "aria-selected") == "true" and app.get_attribute("#tab-team", "aria-selected") == "false"
    assert app.get_attribute("[role=tablist]", "role") == "tablist"


def test_botoes_de_icone_tem_rotulo(mk):
    p = mk([claude_mock()])
    for sel in ["#opp-mic", "#opp-photo", "#opp-clear", "#team-add", "#team-photo"]:
        assert p.get_attribute(sel, "aria-label")
    assert p.get_attribute("#opp-status", "aria-live") == "polite"


def test_alvos_de_toque_com_pelo_menos_44px(app):
    app.click("#tab-battle")
    for sel in ["#tab-team", "#tab-battle", "#tab-plan", "#opp-clear"]:
        assert app.locator(sel).bounding_box()["height"] >= 43.5


def test_abas_ficam_fixas_no_topo(app):
    assert app.eval_on_selector(".tabs", "e=>getComputedStyle(e).position") == "sticky"


def test_renderiza_so_a_aba_ativa(app):
    set_state(app, TEAM, "Greninja")
    assert app.locator(".res").count() == 0 and app.inner_text("#plan-out").strip() == ""
    app.click("#tab-battle")
    assert app.locator(".res").count() == 6


def test_sugestao_de_golpe_por_trecho_do_meio(app):
    add(app, "garchomp")
    app.click("[data-sel='Garchomp']")
    app.fill("#mv-in", "quake")
    assert "Earthquake" in app.eval_on_selector_all("#mv-sug [data-mn]", "e=>e.map(x=>x.dataset.mn)")
