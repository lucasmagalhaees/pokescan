"""E2E de eficiência: monta equipes aleatórias, pergunta ao guia (na página real) quem mandar e confere
o resultado num simulador de duelo independente (Python), nível 50 vs nível 50."""
import random
import pytest
import sim

N = 300
META = 0.70


_CACHE = {}


def cenarios(min_bst, seed, n=N):
    """Equipes/oponentes aleatórios + resultado do duelo de cada membro (calculado uma única vez).
    Seu time tem habilidade/item conhecidos (o guia recebe essas informações); o oponente tem habilidade e
    item sorteados que o guia NÃO conhece (ele assume o pior caso de habilidade)."""
    key = (min_bst, seed, n)
    if key not in _CACHE:
        rng, pool, out = random.Random(seed), sim.pool(min_bst), []
        itens = [""] * 3 + list(sim.ITEMS)
        for i in range(n):
            nomes = rng.sample(pool, 6)
            oponente = rng.choice([x for x in pool if x not in nomes])
            golpes = {x: [sim.MOVES[m][0] for m in sim.realistic_moveset(x)] for x in nomes}
            cf = {x: {"ab": rng.choice(sim.BY[x][5]), "it": rng.choice(itens)} for x in nomes}
            op = sim.mon(oponente, list(sim.realistic_moveset(oponente)), ability=rng.choice(sim.BY[oponente][5]), item=rng.choice(itens))
            vit = [sim.duel(sim.mon(x, list(sim.realistic_moveset(x)), ability=cf[x]["ab"], item=cf[x]["it"]), op, random.Random(i)) for x in nomes]
            out.append((nomes, golpes, oponente, vit, cf))
        _CACHE[key] = out
    return _CACHE[key]


def medir(page, modo, min_bst, seed, n=N):
    cs = cenarios(min_bst, seed, n)
    # uma única ida ao navegador: a página real monta cada cenário e devolve o 1º do ranking
    escolhidos = page.evaluate(
        """([cs,m])=>cs.map(([t,mv,o,cf])=>{tab='battle';team=t;MV=mv;CF=cf;opp=o;oppAb='';oppTera=-1;mode=m;render();return document.querySelector('#out .res .name').innerText})""",
        [[[c[0], c[1], c[2], c[4]] for c in cs], modo])
    guia = sum(c[3][c[0].index(e)] for c, e in zip(cs, escolhidos)) / n
    aleatorio = sum(sum(c[3]) / 6 for c in cs) / n
    oraculo = sum(any(c[3]) for c in cs) / n
    return guia, aleatorio, oraculo


@pytest.mark.parametrize("modo", ["def", "agr"])
@pytest.mark.parametrize("min_bst", [450, 0])
def test_guia_vence_pelo_menos_70_por_cento_dos_duelos_nivelados(u, modo, min_bst):
    guia, aleatorio, oraculo = medir(u, modo, min_bst, seed=11)
    print(f"\n[{modo} bst>={min_bst}] guia={guia:.1%} aleatório={aleatorio:.1%} melhor-possível={oraculo:.1%}")
    assert guia >= META


@pytest.mark.parametrize("modo", ["def", "agr"])
def test_guia_supera_escolha_aleatoria_por_larga_margem(u, modo):
    guia, aleatorio, _ = medir(u, modo, 450, seed=23)
    assert guia - aleatorio >= 0.20


def test_simulador_e_deterministico_para_mesma_semente():
    a = sim.mon("Garchomp", sim.realistic_moveset("Garchomp"))
    b = sim.mon("Gengar", sim.realistic_moveset("Gengar"))
    assert [sim.duel(a, b, random.Random(5)) for _ in range(3)] == [sim.duel(a, b, random.Random(5)) for _ in range(3)]


def test_simulador_sanidade_super_efetivo_vence():
    ground = sim.mon("Garchomp", [next(i for i in sim.BY["Garchomp"][3] if sim.MOVES[i][0] == "Earthquake")])
    pika = sim.mon("Pikachu", [next(i for i in sim.BY["Pikachu"][3] if sim.MOVES[i][0] == "Thunderbolt")])
    assert sim.duel(ground, pika, random.Random(1)) is True
