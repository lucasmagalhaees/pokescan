"""Testes unitários das funções do app (executadas no Chromium, comparadas com o simulador em Python)."""
import random
import pytest
import sim

N = sim.TYPES


def tidx(n):
    return N.index(n)


# ---------- norm / lev ----------
@pytest.mark.parametrize("raw,exp", [
    ("Garchomp", "garchomp"), ("Mr. Mime", "mrmime"), ("Flabébé", "flabebe"), ("Ho-Oh", "hooh"),
    ("Farfetch'd", "farfetchd"), ("  X  Y ", "xy"), ("", ""),
])
def test_norm(u, raw, exp):
    assert u.evaluate("s=>norm(s)", raw) == exp


@pytest.mark.parametrize("a,b,exp", [
    ("pikachu", "pikachu", 0), ("pikachu", "pikahcu", 2), ("gengar", "gengarr", 1),
    ("abc", "", 3), ("", "abc", 3), ("a", "abcdefgh", 9),
])
def test_lev(u, a, b, exp):
    assert u.evaluate("([a,b])=>lev(a,b)", [a, b]) == exp


# ---------- resolve ----------
@pytest.mark.parametrize("text,exp", [
    ("garchomp", "Garchomp"), ("GARCHOMP", "Garchomp"), ("   garchomp   ", "Garchomp"),
    ("g a r c h o m p", "Garchomp"), ("g-a-r-c-h-o-m-p", "Garchomp"), ("Flabebe", "Flabébé"),
    ("ho-oh", "Ho-Oh"), ("Porygon-Z", "Porygon-Z"),
    ("mega garchomp", "Garchomp-Mega"), ("garchomp mega", "Garchomp-Mega"),
    ("mega charizard x", "Charizard-Mega-X"), ("charizard mega y", "Charizard-Mega-Y"),
    ("mega alolan garchomp", "Garchomp-Mega"),
    ("alolan raichu", "Raichu-Alola"), ("galarian slowbro", "Slowbro-Galar"),
    ("hisuian zorua", "Zorua-Hisui"), ("paldean wooper", "Wooper-Paldea"),
    ("pikahcu", "Pikachu"), ("garchom", "Garchomp"), ("gengarr", "Gengar"), ("corvknight", "Corviknight"),
])
def test_resolve_acha(u, text, exp):
    got = u.evaluate("t=>resolve(t)", text)
    nfc = lambda x: __import__('unicodedata').normalize('NFC', x)
    assert [nfc(g) for g in got] == [nfc(exp)]


@pytest.mark.parametrize("text", ["", "zzzzzz", "mega", "!!!", "alolan", "qqqqqqqq"])
def test_resolve_nao_acha(u, text):
    assert u.evaluate("t=>resolve(t)", text) == []


def test_resolve_max_devolve_varios_ordenados_por_tamanho(u):
    got = u.evaluate("()=>resolve('char',5)")
    assert len(got) == 5 and all(n.lower().startswith("char") for n in got)
    assert [len(n) for n in got] == sorted(len(n) for n in got)


def test_resolve_alvo_curto_usa_levenshtein(u):
    assert isinstance(u.evaluate("()=>resolve('ab',3)"), list)


# ---------- suggest ----------
def test_suggest_prefixo_vem_primeiro(u):
    got = u.evaluate("()=>suggest('garch')")
    assert got[0].startswith("Garch") and len(got) <= 6


@pytest.mark.parametrize("q", ["", "g", "zzzzzz"])
def test_suggest_vazio(u, q):
    assert u.evaluate("q=>suggest(q)", q) == []


def test_suggest_contem(u):
    assert "Garchomp" in u.evaluate("()=>suggest('rchomp')")


def test_suggest_limite(u):
    assert len(u.evaluate("()=>suggest('char',2)")) == 2


def test_suggest_sem_acento(u):
    assert any(n.startswith("Flab") for n in u.evaluate("()=>suggest('flabebe')"))


# ---------- tabela de tipos ----------
@pytest.mark.parametrize("atk,dfn,exp", [
    ("Fire", ["Grass"], 2), ("Water", ["Fire"], 2), ("Electric", ["Ground"], 0), ("Normal", ["Ghost"], 0),
    ("Ground", ["Flying"], 0), ("Dragon", ["Fairy"], 0), ("Fairy", ["Dragon"], 2), ("Steel", ["Fairy"], 2),
    ("Ice", ["Dragon", "Ground"], 4), ("Fire", ["Water", "Rock"], 0.25), ("Electric", ["Water", "Flying"], 4),
    ("Grass", ["Water", "Ground"], 4), ("Normal", ["Rock", "Steel"], 0.25), ("Ground", ["Flying", "Fire"], 0),
    ("Bug", ["Dark"], 2), ("Dark", ["Fairy"], 0.5), ("Fire", [], 1),
])
def test_effVs(u, atk, dfn, exp):
    assert u.evaluate("([a,d])=>effVs(DB.types.indexOf(a),d.map(x=>DB.types.indexOf(x)))", [atk, dfn]) == exp


# ---------- build / stats ----------
def test_build_garchomp_valores_fixos(u):
    b = u.evaluate("()=>build('Garchomp')")
    assert b["st"] == [194, 161, 126, 111, 116, 133] and b["name"] == "Garchomp"


@pytest.mark.parametrize("name", ["Garchomp", "Pikachu", "Blissey", "Dondozo", "Charizard-Mega-X", "Magikarp"])
def test_build_bate_com_simulador(u, name):
    b = u.evaluate("n=>build(n)", name)
    assert b["st"] == sim.stats(sim.BY[name][2]) and b["types"] == sim.BY[name][1]


def test_build_desconhecido_e_null(u):
    assert u.evaluate("()=>build('Nope')") is None


def test_build_own_filtra_golpes_marcados(u):
    r = u.evaluate("""()=>{MV={Garchomp:['Earthquake','Outrage']};const b=build('Garchomp',true);const a=build('Garchomp');MV={};
      return [b.moves.map(i=>DB.moves[i][0]),a.moves.length>2]}""")
    assert sorted(r[0]) == ["Earthquake", "Outrage"] and r[1]


def test_build_sem_own_ignora_golpes_marcados(u):
    n = u.evaluate("()=>{MV={Garchomp:['Earthquake']};const n=build('Garchomp').moves.length;MV={};return n}")
    assert n > 1


@pytest.mark.parametrize("mv", [None, [], ["Golpe Inexistente"]])
def test_build_own_sem_golpes_validos_usa_todos(u, mv):
    n = u.evaluate("""m=>{MV=m?{Garchomp:m}:{};const n=build('Garchomp',true).moves.length;MV={};return n}""", mv)
    assert n == len(sim.BY["Garchomp"][3])


# ---------- topMoves vs. simulador ----------
def _py_pct(att, dfn, mv):
    nm, t, cat, bp = sim.MOVES[mv]
    a = att["st"][1] if cat == 0 else att["st"][3]
    d = dfn["st"][2] if cat == 0 else dfn["st"][4]
    x = (22 * bp * a // d) // 50 + 2
    if t in att["types"]:
        x *= 1.5
    return x * sim.eff(t, dfn["types"]) * 0.925 / dfn["st"][0] * 100


@pytest.mark.parametrize("seed", range(8))
def test_topMoves_bate_com_formula_independente(u, seed):
    rng = random.Random(seed)
    a, d = rng.choice(sim.SPECIES), rng.choice(sim.SPECIES)
    js = u.evaluate("([a,d])=>topMoves(build(a),build(d),999).map(x=>[x.nm,x.pct])", [a[0], d[0]])
    A, D = sim.mon(a[0], a[3]), sim.mon(d[0], d[3])
    exp = sorted(((sim.MOVES[m][0], _py_pct(A, D, m)) for m in a[3]), key=lambda x: -x[1])
    assert len(js) == len(exp)
    assert [round(x[1], 6) for x in js] == [round(x[1], 6) for x in exp]


def test_topMoves_limite_k_e_ordem(u):
    r = u.evaluate("()=>topMoves(build('Garchomp'),build('Gengar'))")
    assert len(r) == 3 and r[0]["pct"] >= r[1]["pct"] >= r[2]["pct"]


def test_topMoves_imunidade_zera_dano(u):
    pct = u.evaluate("""()=>{const a=build('Garchomp');a.moves=[DB.moves.findIndex(m=>m[0]==='Earthquake')];
      return topMoves(a,build('Corviknight'))[0].pct}""")
    assert pct == 0


def test_topMoves_stab_vale_1_5x(u):
    r = u.evaluate("""()=>{const mk=ty=>({st:[100,100,100,100,100,100],types:ty,moves:[GEN[0]]});
      const d={st:[100,100,100,100,100,100],types:[1]};
      return [topMoves(mk([0]),d)[0].pct,topMoves(mk([5]),d)[0].pct]}""")
    assert r[0] == pytest.approx(r[1] * 1.5)


def test_topMoves_fisico_usa_atk_especial_usa_spa(u):
    r = u.evaluate("""()=>{const sp=DB.moves.findIndex(m=>m[2]===1&&m[1]===0);
      const phys=GEN[0];
      const d={st:[100,100,100,100,100,100],types:[1]};
      const hi_atk={st:[100,300,100,50,100,100],types:[1],moves:[phys]};
      const hi_spa={st:[100,50,100,300,100,100],types:[1],moves:[sp]};
      const lo_atk={st:[100,50,100,300,100,100],types:[1],moves:[phys]};
      return [topMoves(hi_atk,d)[0].pct>topMoves(lo_atk,d)[0].pct,topMoves(hi_spa,d)[0].pct>0,DB.moves[sp][2]]}""")
    assert r == [True, True, 1]


# ---------- analyse ----------
MON = "(t,spe,mv,atk=100,hp=100)=>({types:[t],st:[hp,atk,100,atk,100,spe],moves:mv,name:'m'})"


def _an(u, spe_me, spe_op, me_moves=True, op_moves=True, atk_me=100, atk_op=100):
    return u.evaluate(f"""([sm,so,mm,om,am,ao])=>{{const mk={MON};
      return analyse(mk(0,sm,mm?[GEN[0]]:[],am),mk(1,so,om?[GEN[1]]:[],ao))}}""",
                      [spe_me, spe_op, me_moves, op_moves, atk_me, atk_op])


def test_analyse_mais_rapido(u):
    r = _an(u, 100, 50)
    assert r["faster"] and not r["tie"]


def test_analyse_empate_de_speed(u):
    r = _an(u, 80, 80)
    assert r["tie"] and not r["faster"]


def test_analyse_mais_lento(u):
    r = _an(u, 50, 100)
    assert not r["faster"] and not r["tie"]


def test_analyse_sem_golpes_meus(u):
    r = _an(u, 100, 50, me_moves=False)
    assert r["dmax"] == 0 and r["myT"] == 99


def test_analyse_oponente_sem_golpes(u):
    r = _an(u, 100, 50, op_moves=False)
    assert r["tmax"] == 0 and r["opT"] == 99 and not r["risk"]


def test_analyse_risco_so_se_morre_em_1_golpe_e_e_mais_lento(u):
    assert _an(u, 50, 100, atk_op=2000)["risk"]
    assert not _an(u, 100, 50, atk_op=2000)["risk"]
    assert not _an(u, 50, 100, atk_op=100)["risk"]


def test_analyse_golpes_para_matar(u):
    r = _an(u, 100, 50, atk_me=600)
    assert r["myT"] == -(-100 // r["dmax"]) if False else r["myT"] == __import__("math").ceil(100 / r["dmax"])


# ---------- advice ----------
def _adv(u, **r):
    base = dict(dmax=50, tmax=30, faster=True, myT=2)
    base.update(r)
    return u.evaluate("r=>advice(r)", base)


def test_advice_sem_dano_manda_trocar(u):
    a = _adv(u, dmax=0)
    assert "troque" in a["heal"] and "troque" in a["buff"]


def test_advice_cura_quando_nao_machuca(u):
    assert "Não precisa curar" in _adv(u, tmax=0.5)["heal"]


def test_advice_cura_inutil_se_tira_tudo(u):
    assert "Curar não adianta" in _adv(u, tmax=120)["heal"]


def test_advice_cura_limiar(u):
    assert "≤ 41%" in _adv(u, tmax=40.2)["heal"]


def test_advice_buff_mata_em_1(u):
    assert "já mata em 1 golpe" in _adv(u, myT=1, dmax=150)["buff"]


def test_advice_buff_vale(u):
    b = _adv(u, dmax=10, tmax=5, faster=True, myT=10)["buff"]
    assert b.startswith("Buff vale") and "em 7" in b


def test_advice_buff_nao_salva(u):
    assert "Buff não salva" in _adv(u, dmax=10, tmax=20, faster=False, myT=10)["buff"]


def test_advice_buff_sem_ganho(u):
    assert "Sem buff: gasta turno" in _adv(u, dmax=40, tmax=10, faster=True, myT=3)["buff"]


def test_advice_mais_lento_leva_um_golpe_a_mais(u):
    f = _adv(u, dmax=10, tmax=14, faster=True, myT=10)["buff"]
    s = _adv(u, dmax=10, tmax=14, faster=False, myT=10)["buff"]
    assert f.startswith("Buff vale") and not s.startswith("Buff vale")


# ---------- rank ----------
def _rank(u, rs, m):
    return u.evaluate("([rs,m])=>rank(rs,m).map(r=>r.n)", [[{"risk": False, **r} for r in rs], m])


A = dict(n="A", tmax=10, dmax=50)
B = dict(n="B", tmax=20, dmax=90)
C = dict(n="C", tmax=60, dmax=100)


def test_rank_defensivo_filtra_quem_toma_menos_e_ordena_por_dano(u):
    assert _rank(u, [A, B, C], "def") == ["B", "A", "C"]


def test_rank_agressivo_filtra_quem_bate_mais_e_ordena_por_dano_tomado(u):
    assert _rank(u, [A, B, C], "agr") == ["B", "C", "A"]


def test_rank_vazio(u):
    assert _rank(u, [], "def") == [] and _rank(u, [], "agr") == []


def test_rank_arriscados_vao_para_o_fim(u):
    r = dict(n="R", tmax=0, dmax=999, risk=True)
    assert _rank(u, [r, A, B, C], "def")[-1] == "R"
    assert _rank(u, [r, A, B, C], "agr")[-1] == "R"


def test_rank_so_arriscados_ainda_ordena(u):
    r1, r2 = dict(n="R1", tmax=50, dmax=10, risk=True), dict(n="R2", tmax=5, dmax=10, risk=True)
    assert u.evaluate("([a,b])=>rank([a,b],'def').map(r=>r.n)", [r1, r2]) == ["R2", "R1"]


def test_rank_defensivo_desempata_por_tomado(u):
    x, y = dict(n="X", tmax=10, dmax=50), dict(n="Y", tmax=5, dmax=50)
    assert _rank(u, [x, y], "def") == ["Y", "X"]


def test_rank_agressivo_desempata_por_dano(u):
    x, y = dict(n="X", tmax=10, dmax=50), dict(n="Y", tmax=10, dmax=70)
    assert _rank(u, [x, y], "agr") == ["Y", "X"]


# ---------- genOpp ----------
@pytest.mark.parametrize("t", [0, 8, 17])
def test_genOpp(u, t):
    g = u.evaluate("t=>genOpp(t)", t)
    assert g["types"] == [t] and g["st"] == [176, 121, 121, 121, 121, 121]
    assert u.evaluate("t=>DB.moves[genOpp(t).moves[0]]", t)[3] == 90
