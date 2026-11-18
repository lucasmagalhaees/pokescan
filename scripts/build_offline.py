"""Gera um único .html com os dados embutidos (abre offline; foto/voz só funcionam com internet no Claude)."""
import pathlib, sys

root = pathlib.Path(__file__).resolve().parent.parent / "src"
out = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else root / "pokebattle-offline.html")
html = (root / "index.html").read_text(encoding="utf-8")
data = (root / "data.json").read_text(encoding="utf-8")
marker = "<script>\nconst $=s=>"
assert html.count(marker) == 1, "script principal não encontrado"
out.write_text(html.replace(marker, f"<script>window.__DATA={data};</script>\n" + marker), encoding="utf-8")
print(f"ok: {out} ({out.stat().st_size // 1024} KB)")
