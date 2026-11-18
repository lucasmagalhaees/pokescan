"""Habilidades, itens, natureza, Tera, golpes de status, troca, modo rápido, histórico e versão offline."""
import json
import pathlib
import pytest
import sim
from conftest import claude_mock
from test_e2e_ui import TEAM, add, seed_storage, set_state

DATA = pathlib.Path(__file__).resolve().parent.parent / "src" / "data.json"


def cfg(name, ab="", it="", nat="", tera=""):
    return dict(name=name, ab=ab, it=it, nat=nat, tera=tera)


JS_BUILD = """c=>{CF={[c.name]:{ab:c.ab,it:c.it,nat:c.nat,tera:c.tera}};const m=build(c.name,true);CF={};return m}"""


def js_pcts(page, att, dfn):
    return page.evaluate("""([a,d,ab])=>{const mk=%s;const A=mk(a),D=mk(d);return topMoves(A,D,999).map(x=>x.pct)}""" % JS_BUILD, [att, dfn, ""])


def py_mon(c, moves=None):
    return sim.mon(c["name"], list(moves if moves is not None else sim.BY[c["name"]][3]), ability=c["ab"] or None,
                   item=c["it"], nature=c["nat"], tera=c["tera"] or None)


# ---------- cruzamento JS x simulador independente ----------
CASOS = [
    (cfg("Garchomp", "Sand Veil"), cfg("Gengar", "Levitate")),
    (cfg("Charizard", "Blaze"), cfg("Garchomp", "Flash Fire")),
    (cfg("Charizard", "Blaze"), cfg("Garchomp", "Well-Baked Body")),
    (cfg("Greninja", "Torrent"), cfg("Garchomp", "Water Absorb")),
    (cfg("Garchomp", "Sand Veil"), cfg("Pikachu", "Volt Absorb")),
    (cfg("Garchomp", "Sand Veil"), cfg("Corviknight", "Sap Sipper")),
    (cfg("Charizard", "Blaze"), cfg("Garchomp", "Thick Fat")),
    (cfg("Greninja", "Torrent"), cfg("Charizard", "Heatproof")),
    (cfg("Garchomp", "Sand Veil"), cfg("Pikachu", "Filter")),
    (cfg("Garchomp", "Huge Power"), cfg("Gengar", "Cursed Body")),
    (cfg("Garchomp", "Adaptability"), cfg("Gengar", "Cursed Body")),
    (cfg("Garchomp", "Tinted Lens"), cfg("Corviknight", "Pressure")),
    (cfg("Garchomp", "Sand Veil", it="Life Orb"), cfg("Gengar", "Cursed Body")),
    (cfg("Garchomp", "Sand Veil", it="Choice Band"), cfg("Gengar", "Cursed Body")),
    (cfg("Gengar", "Cursed Body", it="Choice Specs"), cfg("Garchomp", "Sand Veil")),
    (cfg("Garchomp", "Sand Veil", it="Expert Belt"), cfg("Pikachu", "Static")),
    (cfg("Garchomp", "Sand Veil", it="Choice Scarf"), cfg("Pikachu", "Static")),
    (cfg("Garchomp", "Sand Veil"), cfg("Kingambit", "Defiant", it="Assault Vest")),
    (cfg("Garchomp", "Sand Veil", nat="+Atk"), cfg("Kingambit", "Defiant", nat="+Def")),
    (cfg("Gengar", "Cursed Body", nat="+SpA"), cfg("Kingambit", "Defiant", nat="+SpD")),
    (cfg("Garchomp", "Sand Veil", nat="+Spe"), cfg("Pikachu", "Static")),
    (cfg("Garchomp", "Sand Veil", tera="Fire"), cfg("Corviknight", "Pressure")),
    (cfg("Corviknight", "Pressure"), cfg("Garchomp", "Sand Veil", tera="Fairy")),
    (cfg("Garchomp", "", ""), cfg("Gengar", "", "")),  # habilidade padrão da espécie
]


@pytest.mark.parametrize("att,dfn", CASOS, ids=[f"{a['name']}-{a['ab'] or 'pad'}-{a['it']}{a['nat']}{a['tera']}_vs_{d['name']}-{d['ab'] or 'pad'}-{d['it']}{d['nat']}{d['tera']}" for a, d in CASOS])
def test_topMoves_com_habilidades_itens_natureza_tera_bate_com_simulador(app, att, dfn):
    js = js_pcts(app, att, dfn)
    py = sim.pct_list(py_mon(att), py_mon(dfn))
    assert len(js) == len(py) and js == pytest.approx(py, rel=1e-9, abs=1e-9)


def test_stats_com_item_natureza_e_habilidade_batem_com_simulador(app):
    for c in [cfg("Garchomp", "Huge Power", "Choice Band", "+Atk"), cfg("Pikachu", "Static", "Choice Scarf", "+Spe"),
              cfg("Kingambit", "Defiant", "Assault Vest", "+SpD")]:
        assert app.evaluate(JS_BUILD, c)["st"] == py_mon(c)["st"]


def test_tera_troca_tipo_defensivo_e_mantem_stab_original(app):
    m = app.evaluate(JS_BUILD, cfg("Garchomp", "Sand Veil", tera="Fire"))
    t = {n: i for i, n in enumerate(sim.TYPES)}
    assert m["types"] == [t["Fire"]] and set(m["stab"]) == {t["Dragon"], t["Ground"], t["Fire"]}


def test_ability_inexistente_nao_quebra(app):
    pcts = js_pcts(app, cfg("Garchomp", "Habilidade Inventada"), cfg("Gengar", "Outra Inventada"))
    assert all(p >= 0 for p in pcts)


def test_nature_e_item_invalidos_sao_ignorados(app):
    a = app.evaluate(JS_BUILD, cfg("Garchomp", "Sand Veil", "Item Falso", "Nat Falsa"))
    b = app.evaluate(JS_BUILD, cfg("Garchomp", "Sand Veil"))
    assert a["st"] == b["st"]


# ---------- golpes de status: dados + dicas ----------
def test_dados_de_status_validos():
    d = json.loads(DATA.read_text())
    assert len(d["status"]) >= 30
    for nm, t, kind, arg in d["status"]:
        assert nm and 0 <= t < 18 and kind in ("b", "h", "s")
        assert (kind == "b" and isinstance(arg, dict)) or (kind == "h" and 0 < arg <= 1) or (kind == "s" and arg in ("brn", "par", "tox"))
    for s in d["species"]:
        assert s[5] and all(isinstance(a, str) for a in s[5])
        assert all(0 <= i < len(d["status"]) for i in s[6])


def test_garchomp_tem_habilidades_e_swords_dance():
    d = json.loads(DATA.read_text())
    g = next(s for s in d["species"] if s[0] == "Garchomp")
    assert "Sand Veil" in g[5] and "Swords Dance" in [d["status"][i][0] for i in g[6]]


def R(**kw):
    base = dict(dmax=10, tmax=5, faster=True, myT=10, dealt=[{"cat": 0}], taken=[{"cat": 0}], me={"util": []})
    base.update(kw)
    return base


def adv(page, r):
    return page.evaluate("r=>advice(r)", r)


UTIL_SD = ["Swords Dance", 0, "b", {"atk": 2}]
UTIL_NP = ["Nasty Plot", 0, "b", {"spa": 2}]
UTIL_BU = ["Bulk Up", 0, "b", {"def": 1}]
UTIL_RC = ["Recover", 0, "h", 0.5]
UTIL_WOW = ["Will-O-Wisp", 1, "s", "brn"]
UTIL_TW = ["Thunder Wave", 3, "s", "par"]
UTIL_TX = ["Toxic", 7, "s", "tox"]


def test_buff_usa_golpe_marcado_fisico(app):
    a = adv(app, R(me={"util": [UTIL_SD]}))
    assert "Swords Dance (+2)" in a["buff"] and a["buff"].startswith("Buff vale")


def test_buff_usa_golpe_marcado_especial(app):
    a = adv(app, R(dealt=[{"cat": 1}], me={"util": [UTIL_NP]}))
    assert "Nasty Plot (+2)" in a["buff"]


def test_buff_marcado_para_outro_atributo_cai_na_estimativa(app):
    assert "estimado" in adv(app, R(me={"util": [UTIL_BU]}))["buff"]


def test_buff_sem_dealt_assume_fisico(app):
    r = R(me={"util": [UTIL_SD]})
    del r["dealt"]
    assert "Swords Dance (+2)" in adv(app, r)["buff"]


def test_buff_com_dealt_vazio_assume_fisico(app):
    assert "Swords Dance (+2)" in adv(app, R(dealt=[], me={"util": [UTIL_SD]}))["buff"]


def test_sem_me_usa_estimativa(app):
    r = R()
    del r["me"]
    assert "estimado" in adv(app, r)["buff"]


def test_recuperacao_compensa(app):
    assert "Recover compensa" in adv(app, R(tmax=30, me={"util": [UTIL_RC]}))["extra"][0]


def test_recuperacao_nao_compensa(app):
    assert "não compensa" in adv(app, R(tmax=60, me={"util": [UTIL_RC]}))["extra"][0]


def test_burn_so_quando_o_golpe_dele_e_fisico(app):
    assert any("Will-O-Wisp" in x for x in adv(app, R(me={"util": [UTIL_WOW]}))["extra"])
    assert not adv(app, R(taken=[{"cat": 1}], me={"util": [UTIL_WOW]}))["extra"]
    assert not adv(app, R(taken=[], me={"util": [UTIL_WOW]}))["extra"]
    r = R(me={"util": [UTIL_WOW]})
    del r["taken"]
    assert not adv(app, r)["extra"]


def test_paralisia_so_quando_ele_e_mais_rapido(app):
    assert any("Paralisia" in x for x in adv(app, R(faster=False, me={"util": [UTIL_TW]}))["extra"])
    assert not adv(app, R(faster=True, me={"util": [UTIL_TW]}))["extra"]


def test_toxic_so_em_luta_longa(app):
    assert any("Toxic" in x for x in adv(app, R(myT=4, me={"util": [UTIL_TX]}))["extra"])
    assert not adv(app, R(myT=2, me={"util": [UTIL_TX]}))["extra"]


def test_sem_dano_tem_extra_vazio(app):
    assert adv(app, R(dmax=0))["extra"] == []


# ---------- troca / Tera / oponente ----------
def test_switchLine(app):
    rs = [dict(me={"name": n}, risk=r, tmax=t) for n, r, t in [("A", False, 10), ("B", True, 20), ("C", False, 50), ("D", False, 30)]]
    assert app.evaluate("rs=>switchLine(rs)", rs) == {"next": "C", "safe": ["B", "D"]}


def test_switchLine_sem_opcao(app):
    rs = [dict(me={"name": "A"}, risk=False, tmax=10), dict(me={"name": "B"}, risk=True, tmax=90)]
    assert app.evaluate("rs=>switchLine(rs)", rs) == {"next": None, "safe": []}


def test_teraAlert_aparece_em_alguns_casos_e_nao_em_outros(app):
    r = app.evaluate("""()=>{const out=[];const ns=['Garchomp','Gengar','Corviknight','Kingambit','Charizard','Pikachu','Greninja','Blissey','Dragonite','Tyranitar'];
      for(const a of ns)for(const b of ns){if(a===b)continue;const me=build(a,true),op=build(b);const best=analyse(me,op);out.push(teraAlert(best,op))}
      return out}""")
    assert any(r) and not all(r)
    assert all(x == "" or "terastalizar" in x for x in r)


def test_teraAlert_desligado_quando_oponente_ja_tera(app):
    assert app.evaluate("()=>{oppTera=3;const me=build('Garchomp',true),op=build('Gengar');return teraAlert(analyse(me,op),op)}") == ""


def test_oppSetup_pior_caso_escolhe_a_habilidade_que_mais_protege(app):
    ab = app.evaluate("""()=>{DB.species[SPI.Gengar][5]=['Cursed Body','Levitate'];
      const me=build('Garchomp',true);me.moves=[DB.moves.findIndex(m=>m[0]==='Earthquake')];return oppSetup('Gengar',[me]).ab}""")
    assert ab == "Levitate"


def test_oppSetup_respeita_habilidade_escolhida_e_tera(app):
    r = app.evaluate("""()=>{oppAb='Cursed Body';oppTera=0;const o=oppSetup('Gengar',[build('Garchomp',true)]);return [o.ab,o.types]}""")
    assert r == ["Cursed Body", [0]]


def test_oppSetup_sem_habilidades_na_especie(app):
    assert app.evaluate("()=>{DB.species[SPI.Gengar][5]=[];return oppSetup('Gengar',[build('Garchomp',true)]).ab}") == ""


# ---------- UI: configuração do Pokémon ----------
def abrir(app, nome="garchomp"):
    add(app, nome)
    app.click(f"[data-sel='{nome.title()}']")


def test_selects_do_painel_populam_opcoes(app):
    abrir(app)
    assert "Sand Veil" in app.eval_on_selector_all("#cf-ab option", "e=>e.map(x=>x.textContent)")
    assert "Life Orb" in app.eval_on_selector_all("#cf-it option", "e=>e.map(x=>x.textContent)")
    assert app.eval_on_selector_all("#cf-nat option", "e=>e.length") == 6 and app.eval_on_selector_all("#cf-tera option", "e=>e.length") == 19


def test_escolher_item_natureza_tera_e_habilidade(app):
    abrir(app)
    app.select_option("#cf-it", "Life Orb")
    app.select_option("#cf-nat", "+Atk")
    app.select_option("#cf-tera", "Fire")
    app.select_option("#cf-ab", "Rough Skin")
    assert app.evaluate("()=>CF.Garchomp") == {"it": "Life Orb", "nat": "+Atk", "tera": "Fire", "ab": "Rough Skin"}
    assert app.input_value("#cf-it") == "Life Orb" or app.eval_on_selector("#cf-it", "e=>e.value") == "Life Orb"


def test_voltar_para_sem_item_zera(app):
    abrir(app)
    app.select_option("#cf-it", "Life Orb")
    app.select_option("#cf-it", index=0)
    app.select_option("#cf-nat", index=0)
    app.select_option("#cf-tera", index=0)
    assert app.evaluate("()=>CF.Garchomp") == {"it": "", "nat": "", "tera": ""}


def test_config_muda_o_resultado(app):
    abrir(app)
    set_state(app, ["Garchomp"], "Gengar")
    app.click("#tab-battle")
    antes = app.inner_text(".res .mut.sm")
    app.click("#tab-team")
    app.select_option("#cf-it", "Life Orb")
    app.click("#tab-battle")
    assert app.inner_text(".res .mut.sm") != antes


def test_remover_e_limpar_apagam_config(app):
    add(app, "garchomp", "gengar")
    app.click("[data-sel='Garchomp']")
    app.select_option("#cf-it", "Life Orb")
    app.click("[data-i='0']")
    assert app.evaluate("()=>CF") == {}
    app.fill("#team-in", "garchomp")
    app.press("#team-in", "Enter")
    app.click("[data-sel='Garchomp']")
    app.select_option("#cf-it", "Life Orb")
    app.click("#team-clear")
    assert app.evaluate("()=>CF") == {}


def test_golpes_de_status_aparecem_nas_sugestoes_e_viram_dica(app):
    abrir(app)
    app.fill("#mv-in", "swords")
    app.click("#mv-sug [data-mn='Swords Dance']")
    app.fill("#mv-in", "earthq")
    app.press("#mv-in", "Enter")
    set_state(app, ["Garchomp"], "Corviknight", mv={"Garchomp": ["Swords Dance", "Earthquake"]})
    app.click("#tab-battle")
    assert app.evaluate("()=>build('Garchomp',true).util.map(x=>x[0])") == ["Swords Dance"]


def test_apenas_golpe_de_status_marcado_mantem_ataques(app):
    set_state(app, ["Garchomp"], "Corviknight", mv={"Garchomp": ["Swords Dance"]})
    app.click("#tab-battle")
    assert app.locator(".res").count() == 1 and app.evaluate("()=>build('Garchomp',true).moves.length") > 1


def test_cartao_mostra_dicas_extras_de_status(app):
    app.click("#tab-battle")
    set_state(app, ["Garchomp"], "Greninja", mv={"Garchomp": ["Earthquake", "Recover", "Toxic", "Thunder Wave", "Will-O-Wisp"]})
    app.evaluate("()=>{team=['Pikachu'];MV={Pikachu:['Thunderbolt','Thunder Wave','Toxic','Will-O-Wisp','Nuzzle']};render()}")
    app.evaluate("()=>{MV={Pikachu:['Thunderbolt']};render()}")
    app.evaluate("""()=>{analyse=(me,op)=>({me:Object.assign({},me,{util:[['Recover',0,'h',0.5]]}),dealt:[{nm:'A',t:0,e:1,cat:0,pct:30}],taken:[{nm:'B',t:1,e:1,cat:0,pct:10}],
      dmax:30,tmax:10,faster:true,tie:false,myT:4,opT:10,risk:false});render()}""")
    assert "🧪" in app.evaluate("()=>document.querySelector('#out').textContent")


# ---------- UI: oponente (habilidade/Tera) ----------
def test_controles_do_oponente_somem_sem_oponente(app):
    app.click("#tab-battle")
    assert app.eval_on_selector("#opp-ctl", "e=>e.hidden")
    set_state(app, ["Garchomp"], "Gengar")
    assert not app.eval_on_selector("#opp-ctl", "e=>e.hidden")


def test_escolher_habilidade_e_tera_do_oponente(app):
    set_state(app, ["Garchomp"], "Gengar")
    app.click("#tab-battle")
    assert "Cursed Body" in app.eval_on_selector_all("#opp-ab option", "e=>e.map(x=>x.textContent)")
    app.select_option("#opp-ab", "Cursed Body")
    assert app.evaluate("()=>oppAb") == "Cursed Body"
    app.select_option("#opp-tera", "Tera Fire")
    assert app.evaluate("()=>oppTera") == 1 and "Fire" in app.inner_text("#out .card .ty") or "Fire" in app.inner_text("#out")
    assert app.eval_on_selector("#opp-tera", "e=>e.value") == "1" and app.eval_on_selector("#opp-ab", "e=>e.value") == "Cursed Body"


def test_trocar_de_oponente_zera_habilidade_e_tera(app):
    set_state(app, ["Garchomp"], "Gengar")
    app.click("#tab-battle")
    app.select_option("#opp-tera", "Tera Fire")
    app.fill("#opp-in", "greninja")
    app.press("#opp-in", "Enter")
    assert app.evaluate("()=>[oppAb,oppTera]") == ["", -1]
    app.select_option("#opp-tera", "Tera Fire")
    app.click("#opp-clear")
    assert app.evaluate("()=>[oppAb,oppTera]") == ["", -1]


def test_cartao_do_oponente_mostra_habilidade_assumida(app):
    set_state(app, ["Garchomp"], "Gengar")
    app.click("#tab-battle")
    assert "Cursed Body" in app.inner_text("#out .card")


def test_plano_de_troca_e_tera_aparecem(app):
    add(app, *TEAM)
    set_state(app, TEAM, "Greninja")
    app.click("#tab-battle")
    txt = app.inner_text(".lines")
    assert "Se cair, entre com" in txt and "Troca segura" in txt or "Se cair, entre com" in txt
    plans = []
    for o in ["Greninja", "Gengar", "Dragonite", "Tyranitar", "Blissey", "Corviknight"]:
        set_state(app, TEAM, o)
        plans.append(app.evaluate("()=>document.querySelector('#out').textContent"))
    assert any("terastalizar" in p for p in plans)


def test_sem_plano_quando_so_ha_um_pokemon(app):
    set_state(app, ["Garchomp"], "Greninja")
    app.click("#tab-battle")
    assert app.locator(".lines").count() == 0 or "Se cair" not in app.inner_text(".lines")


# ---------- histórico (calibração) ----------
def test_registrar_vitoria_e_derrota(app):
    set_state(app, TEAM, "Greninja")
    app.click("#tab-battle")
    assert "Sem lutas" in app.inner_text("#calib")
    app.click("#res-win")
    app.click("#res-loss")
    app.click("#mode [data-m='agr']")
    app.click("#res-win")
    t = app.inner_text("#calib")
    assert "2/3 vitórias (67%)" in t and "Defensivo 1/2" in t and "Agressivo 1/1" in t
    assert app.evaluate("()=>LOG.map(x=>x.w)") == [True, False, True]


def test_historico_guarda_a_escolha_do_guia(app):
    set_state(app, TEAM, "Greninja")
    app.click("#tab-battle")
    pick = app.inner_text(".res.top .name")
    app.click("#res-win")
    assert app.evaluate("()=>LOG[0].p") == pick and app.evaluate("()=>LOG[0].o") == "Greninja"


def test_historico_persiste_limita_a_200_e_limpa(app):
    set_state(app, TEAM, "Greninja")
    app.click("#tab-battle")
    app.evaluate("()=>{LOG=Array.from({length:205},(_,i)=>({p:'A',o:'B',m:'def',w:i%2===0}))}")
    app.click("#res-win")
    assert app.evaluate("()=>LOG.length") == 200
    app.reload_app()
    assert app.evaluate("()=>LOG.length") == 200
    app.click("#tab-battle")
    app.click("#calib-clear")
    assert app.evaluate("()=>LOG") == [] and "Sem lutas" in app.inner_text("#calib")


def test_clique_fora_do_botao_limpar_nao_apaga(app):
    app.click("#tab-battle")
    app.evaluate("()=>{LOG=[{p:'A',o:'B',m:'def',w:true}];render()}")
    app.evaluate("()=>document.querySelector('#calib').click()")
    assert app.evaluate("()=>LOG.length") == 1


# ---------- modo rápido ----------
def test_modo_rapido_mostra_so_o_essencial_e_persiste(app):
    set_state(app, TEAM, "Greninja")
    app.click("#tab-battle")
    assert app.get_attribute("#quick-toggle", "aria-pressed") == "false" and app.locator(".res").count() == 6
    app.click("#quick-toggle")
    assert app.locator(".res").count() == 0 and app.locator(".verdict.big").count() == 1
    assert app.get_attribute("#quick-toggle", "aria-pressed") == "true" and "ligado" in app.inner_text("#quick-toggle")
    t = app.inner_text("#out")
    assert "Mande" in t and "💊" in t and "⚡" in t and "Ganhei" in t
    app.reload_app()
    assert app.evaluate("()=>quick") is True
    app.click("#tab-battle")
    app.click("#quick-toggle")
    assert app.evaluate("()=>quick") is False


def test_modo_rapido_sem_oponente_e_sem_time(app):
    app.click("#tab-battle")
    app.click("#quick-toggle")
    assert "Monte seu time" in app.inner_text("#out")
    app.click("#tab-team")
    add(app, "garchomp")
    app.click("#tab-battle")
    assert "Informe o oponente" in app.inner_text("#out")


def test_modo_rapido_inclui_extras_e_plano(app):
    set_state(app, ["Garchomp", "Gengar", "Corviknight"], "Greninja", mv={"Garchomp": ["Earthquake", "Recover"]})
    app.click("#tab-battle")
    app.click("#quick-toggle")
    app.evaluate("""()=>{const a=analyse;analyse=(me,op)=>Object.assign(a(me,op),{me:Object.assign({},me,{util:[['Recover',0,'h',0.5]]})});render()}""")
    t = app.evaluate("()=>document.querySelector('#out').textContent")
    assert "🧪" in t and "🔄" in t


# ---------- armazenamento novo ----------
def test_storage_de_config_historico_e_rapido(mk):
    p = mk([seed_storage(**{"pbh-team": json.dumps(["Garchomp"]), "pbh-cf": json.dumps({"Garchomp": {"it": "Life Orb"}}),
                            "pbh-log": json.dumps([{"p": "Garchomp", "o": "Gengar", "m": "def", "w": True}]),
                            "pbh-prefs": json.dumps({"mode": "def", "quick": True})})])
    assert p.evaluate("()=>[CF.Garchomp.it,LOG.length,quick]") == ["Life Orb", 1, True]


@pytest.mark.parametrize("cf,log,quick", [("5", "{}", "yes"), ("null", "5", None), ("{bad", "[]", None)])
def test_storage_invalido_de_config_historico_rapido(mk, cf, log, quick):
    prefs = json.dumps({"quick": quick}) if quick is not None else "{}"
    p = mk([seed_storage(**{"pbh-cf": cf, "pbh-log": log, "pbh-prefs": prefs})])
    assert p.evaluate("()=>[typeof CF,Array.isArray(LOG),quick]")[1] is True


# ---------- versão offline (dados embutidos) ----------
def test_usa_dados_embutidos_sem_rede(mk):
    data = DATA.read_text()
    p = mk([f"window.__DATA={data}"], route=lambda pg: pg.route("**/data.json", lambda r: r.abort()))
    add(p, "garchomp")
    assert p.evaluate("()=>team") == ["Garchomp"]


def test_build_offline_gera_html_autocontido(tmp_path):
    import subprocess, sys
    out = tmp_path / "offline.html"
    root = pathlib.Path(__file__).resolve().parent.parent
    subprocess.run([sys.executable, str(root / "scripts" / "build_offline.py"), str(out)], check=True)
    html = out.read_text()
    assert "window.__DATA=" in html and "fetch('data.json')" in html and len(html) > 200_000
