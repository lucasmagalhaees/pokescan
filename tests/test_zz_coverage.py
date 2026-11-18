"""Roda por último: exige 100% de cobertura do JS do app (blocos/ramos executados pelos testes acima)."""
from conftest import COVERED, SCRIPT, uncovered_segments


def test_cobertura_de_100_por_cento_do_js():
    segs = uncovered_segments()
    total = sum(1 for c in SCRIPT if not c.isspace())
    cov = sum(1 for i, c in enumerate(SCRIPT) if not c.isspace() and COVERED[i])
    print(f"\nCobertura do JS: {cov / total:.2%} ({cov}/{total} caracteres úteis)")
    assert not segs, "Trechos sem cobertura:\n" + "\n".join(f"  linha {l}: {t}" for l, t in segs)
