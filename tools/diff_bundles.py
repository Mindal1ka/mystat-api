# -*- coding: utf-8 -*-
"""Порівнює дві збірки фронтенду MyStat за РЯДКОВИМИ літералами (імена змінних у
мініфікованому коді та хеші чанків щоразу інші, тому звичайний diff марний).

Запуск:
    python -I tools/diff_bundles.py <тека_стара> <тека_нова> [-v]

Порівнює: getEndpoint(), endpoint=, HTTP-виклики, шляхи-літерали, події сокетів,
X-заголовки, ключі localStorage, зовнішні URL. Результат — +додано / -видалено.
Шум від перейменування змінних (напр. `${t.x}` проти `${e.x}`) оцінюйте очима.
"""
import pathlib
import re
import sys

PATTERNS = {
    "getEndpoint": re.compile(r"""getEndpoint\(\s*(['"`])(.{1,120}?)\1""", re.S),
    "endpoint=": re.compile(r"""\bendpoint\s*=\s*(['"`])(/[^'"`]{1,90})\1"""),
    "http": re.compile(r"""\.(get|post|put|delete|patch)(?:<[^(]{1,120}>)?\(\s*[`"']([^`"']{1,110})[`"']"""),
    "slash-literals": re.compile(r"""[`"'](/[A-Za-z0-9_\-][A-Za-z0-9_\-/.{}$\[\]]{2,90})[`"']"""),
    "socket-events": re.compile(r"""\.(on|emit)\([`"']([A-Za-z_][\w.\-]{1,50})[`"']"""),
    "x-headers": re.compile(r"""[`"'](X-[A-Za-z][A-Za-z\-]{2,40})[`"']"""),
    "localStorage": re.compile(r"""(?:localStorage|sessionStorage)\.(?:get|set|remove)Item\([`"']([\w\-.]{2,40})[`"']"""),
    "urls": re.compile(r"""https?://[A-Za-z0-9_.\-]+(?:/[A-Za-z0-9_\-/.]*)?"""),
}
QUIET = {"slash-literals", "urls"}


def collect(folder: pathlib.Path) -> dict[str, set[str]]:
    res: dict[str, set[str]] = {k: set() for k in PATTERNS}
    for f in folder.glob("*.js"):
        text = f.read_text("utf-8", errors="ignore")
        for key, rx in PATTERNS.items():
            for m in rx.finditer(text):
                res[key].add(m.group(0) if key == "urls" else " ".join(g for g in m.groups() if g and g not in "'\"`"))
    return res


def main() -> None:
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    old, new = collect(pathlib.Path(sys.argv[1])), collect(pathlib.Path(sys.argv[2]))
    verbose = "-v" in sys.argv
    for key in PATTERNS:
        a, b = old[key], new[key]
        print(f"== {key}: було={len(a)} стало={len(b)} додано={len(b - a)} видалено={len(a - b)}")
        if verbose or key not in QUIET:
            for x in sorted(b - a):
                print("  +", x)
            for x in sorted(a - b):
                print("  -", x)


if __name__ == "__main__":
    main()
