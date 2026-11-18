"""Orçamentos de performance (ms por chamada, medidos no Chromium). Margens generosas p/ não ficar instável."""
import pytest

JS = """([expr,n])=>{const f=new Function('return ('+expr+')');const t=performance.now();for(let i=0;i<n;i++)f();return (performance.now()-t)/n}"""


def ms(page, expr, n=30):
    return page.evaluate(JS, [expr, n])


@pytest.fixture
def quente(mk):
    p = mk()
    p.evaluate("()=>{team=['Garchomp','Corviknight','Gengar','Kingambit','Charizard','Pikachu'];opp='Greninja';MV={};}")
    return p


def test_resolve_fuzzy_rapido(quente):
    assert ms(quente, "resolve('pikahcu')") < 5


def test_suggest_rapido(quente):
    assert ms(quente, "suggest('char')", 100) < 1


def test_render_na_aba_do_time_nao_monta_batalha(quente):
    assert ms(quente, "render()", 50) < 1.5


def test_render_batalha_6_pokemon(quente):
    quente.evaluate("()=>{tab='battle'}")
    assert ms(quente, "render()", 30) < 10


def test_render_planos(quente):
    quente.evaluate("()=>{tab='plan'}")
    assert ms(quente, "render()", 20) < 20


def test_pagina_e_dados_leves(server):
    import pathlib
    root = pathlib.Path(__file__).resolve().parent.parent
    assert (root / "src" / "index.html").stat().st_size < 48_000 and (root / "src" / "data.json").stat().st_size < 260_000
