"""Integridade do data.json (espécies, golpes, tabela de tipos)."""
import pytest
import sim

T = {n: i for i, n in enumerate(sim.TYPES)}


def test_tem_18_tipos():
    assert len(sim.TYPES) == 18 and len(set(sim.TYPES)) == 18


def test_quantidade_de_especies_e_megas():
    assert len(sim.SPECIES) >= 900
    assert sum(s[4] for s in sim.SPECIES) >= 60


def test_nomes_unicos():
    names = [s[0] for s in sim.SPECIES]
    assert len(names) == len(set(names))


@pytest.mark.parametrize("name", ["Garchomp", "Gengar", "Corviknight", "Kingambit", "Garchomp-Mega", "Charizard-Mega-X", "Raichu-Alola", "Ho-Oh", "Porygon-Z"])
def test_especies_conhecidas_existem(name):
    assert name in sim.BY


def test_tipos_das_especies_validos():
    for s in sim.SPECIES:
        assert 1 <= len(s[1]) <= 2 and all(0 <= t < 18 for t in s[1])


def test_stats_validos():
    for s in sim.SPECIES:
        assert len(s[2]) == 6 and all(v > 0 for v in s[2])


def test_golpes_referenciados_existem():
    for s in sim.SPECIES:
        assert s[3] and all(0 <= m < len(sim.MOVES) for m in s[3])
        assert len(s[3]) == len(set(s[3]))


def test_golpes_so_de_dano():
    for nm, t, cat, bp in sim.MOVES:
        assert bp > 0 and cat in (0, 1) and 0 <= t < 18 and nm


def test_garchomp_tem_earthquake_e_outrage():
    moves = {sim.MOVES[m][0] for m in sim.BY["Garchomp"][3]}
    assert {"Earthquake", "Outrage"} <= moves


def test_mega_herda_golpes_da_base():
    assert sim.BY["Garchomp-Mega"][3] == sim.BY["Garchomp"][3]


def test_tabela_de_tipos_18x18_e_valores_validos():
    assert len(sim.EFF) == 18 and all(len(r) == 18 for r in sim.EFF)
    assert {v for r in sim.EFF for v in r} <= {0, 0.5, 1, 2}


@pytest.mark.parametrize("atk,dfn,mult", [
    ("Fire", "Grass", 2), ("Water", "Fire", 2), ("Electric", "Ground", 0), ("Normal", "Ghost", 0),
    ("Ground", "Flying", 0), ("Dragon", "Fairy", 0), ("Fairy", "Dragon", 2), ("Poison", "Steel", 0),
    ("Psychic", "Dark", 0), ("Normal", "Rock", 0.5), ("Fighting", "Ghost", 0), ("Ghost", "Normal", 0),
])
def test_tabela_de_tipos_pares(atk, dfn, mult):
    assert sim.EFF[T[atk]][T[dfn]] == mult
