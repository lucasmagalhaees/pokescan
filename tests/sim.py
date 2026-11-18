"""Simulador independente (Python) para medir a eficiência do guia em duelos 1v1 nivelados (nível 50)."""
import functools, json, math, random, pathlib

DATA = json.loads((pathlib.Path(__file__).parent.parent / "src" / "data.json").read_text())
TYPES, MOVES, SPECIES, EFF = DATA["types"], DATA["moves"], DATA["species"], DATA["eff"]
BY = {s[0]: s for s in SPECIES}


def stats(base):
    return [(2 * b + 52) // 2 + (60 if i == 0 else 5) for i, b in enumerate(base)]


def eff(t, types):
    e = 1.0
    for d in types:
        e *= EFF[t][d]
    return e


def dmg(att, dfn, mv, roll=0.925):
    nm, t, cat, bp = MOVES[mv] if isinstance(mv, int) else mv
    a = att["st"][1] if cat == 0 else att["st"][3]
    d = dfn["st"][2] if cat == 0 else dfn["st"][4]
    x = (22 * bp * a // d) // 50 + 2
    if t in att["types"]:
        x *= 1.5
    return int(x * eff(t, dfn["types"]) * roll)


ITEMS = {  # (stat idx -> mult), dano, super-efetivo
    "Choice Band": {"st": {1: 1.5}}, "Choice Specs": {"st": {3: 1.5}}, "Choice Scarf": {"st": {5: 1.5}},
    "Assault Vest": {"st": {4: 1.5}}, "Life Orb": {"dm": 1.3}, "Expert Belt": {"se": 1.2},
}
NATURE = {"+Atk": 1, "+Def": 2, "+SpA": 3, "+SpD": 4, "+Spe": 5}
ABILITIES = {
    "Levitate": {"imm": ["Ground"]}, "Earth Eater": {"imm": ["Ground"]}, "Flash Fire": {"imm": ["Fire"]},
    "Well-Baked Body": {"imm": ["Fire"]}, "Water Absorb": {"imm": ["Water"]}, "Storm Drain": {"imm": ["Water"]},
    "Dry Skin": {"imm": ["Water"]}, "Volt Absorb": {"imm": ["Electric"]}, "Lightning Rod": {"imm": ["Electric"]},
    "Motor Drive": {"imm": ["Electric"]}, "Sap Sipper": {"imm": ["Grass"]},
    "Thick Fat": {"res": {"Fire": 0.5, "Ice": 0.5}}, "Heatproof": {"res": {"Fire": 0.5}}, "Water Bubble": {"res": {"Fire": 0.5}},
    "Filter": {"se": 0.75}, "Solid Rock": {"se": 0.75}, "Prism Armor": {"se": 0.75},
    "Huge Power": {"atk": 2}, "Pure Power": {"atk": 2}, "Adaptability": {"stab": 2}, "Tinted Lens": {"nve": 2},
}


def mon(name, moves, ability=None, item="", nature="", tera=None):
    s = BY[name]
    st = stats(s[2])
    for k, m in ITEMS.get(item, {}).get("st", {}).items():
        st[k] = math.floor(st[k] * m)
    if nature in NATURE:
        st[NATURE[nature]] = math.floor(st[NATURE[nature]] * 1.1)
    ab = ability if ability is not None else (s[5][0] if s[5] else "")
    if ABILITIES.get(ab, {}).get("atk"):
        st[1] = math.floor(st[1] * ABILITIES[ab]["atk"])
    types, stab = list(s[1]), list(s[1])
    if tera is not None:
        stab = sorted(set(types) | {TYPES.index(tera)})
        types = [TYPES.index(tera)]
    return {"name": name, "types": types, "stab": stab, "st": st, "moves": moves, "ab": ab, "it": item}


def pct_list(att, dfn):
    """% do HP do alvo que cada golpe tira (fórmula independente da do app), em ordem decrescente."""
    return sorted((_base(att, dfn, m) * 0.925 / dfn["st"][0] * 100 for m in att["moves"]), reverse=True)


@functools.lru_cache(maxsize=None)
def realistic_moveset(name):
    """4 golpes 'competentes': melhor poder (com STAB) priorizando tipos diferentes."""
    s = BY[name]
    cand = []
    for mi in s[3]:
        nm, t, cat, bp = MOVES[mi]
        stat = s[2][1] if cat == 0 else s[2][3]
        cand.append((bp * (1.5 if t in s[1] else 1.0) * (stat / 100 + 0.5), mi, t))
    cand.sort(reverse=True)
    out, used = [], set()
    for _, mi, t in cand:
        if t in used:
            continue
        out.append(mi)
        used.add(t)
        if len(out) == 4:
            break
    return tuple(out)


def _base(att, dfn, mv):
    """Dano antes do sorteio (roll), já com STAB, tipos, habilidades e itens."""
    nm, t, cat, bp = MOVES[mv] if isinstance(mv, int) else mv
    a = att["st"][1] if cat == 0 else att["st"][3]
    d = dfn["st"][2] if cat == 0 else dfn["st"][4]
    x = (22 * bp * a // d) // 50 + 2
    A, D = ABILITIES.get(att.get("ab", ""), {}), ABILITIES.get(dfn.get("ab", ""), {})
    I = ITEMS.get(att.get("it", ""), {})
    e = eff(t, dfn["types"])
    if TYPES[t] in D.get("imm", []):
        e = 0
    else:
        e *= D.get("res", {}).get(TYPES[t], 1)
        if D.get("se") and e >= 2:
            e *= D["se"]
    if A.get("nve") and 0 < e < 1:
        e *= A["nve"]
    if t in att.get("stab", att["types"]):
        x *= A.get("stab", 1.5)
    x *= I.get("dm", 1)
    if I.get("se") and e >= 2:
        x *= I["se"]
    return x * e


def duel(me, op, rng):
    """True se 'me' vence. Cada lado usa, a cada turno, o golpe que mais tira do alvo."""
    hp = {"me": me["st"][0], "op": op["st"][0]}
    power = {"me": max((_base(me, op, m) for m in me["moves"]), default=0),
             "op": max((_base(op, me, m) for m in op["moves"]), default=0)}
    first = "me" if me["st"][5] > op["st"][5] else "op" if op["st"][5] > me["st"][5] else rng.choice(["me", "op"])
    order = [first, "op" if first == "me" else "me"]
    for _ in range(60):
        for k in order:
            tgt = "op" if k == "me" else "me"
            hp[tgt] -= int(power[k] * (rng.randint(85, 100) / 100))
            if hp[tgt] <= 0:
                return k == "me"
    return False


def bst(name):
    return sum(BY[name][2])


def pool(min_bst=450, megas=False):
    return [s[0] for s in SPECIES if (megas or not s[4]) and sum(s[2]) >= min_bst]
