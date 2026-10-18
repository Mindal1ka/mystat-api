# -*- coding: utf-8 -*-
"""Завантажує ПУБЛІЧНІ бандли фронтенду MyStat у вказану (бажано нову, порожню) теку.

Запуск (з іншої теки, ізольовано):
    python -I tools/fetch_bundles.py <тека_призначення> [https://mystat.itstep.org/]

Алгоритм (how.md §2): index.html -> main-*.js/polyfills-*.js -> ітеративно всі chunk-*.js.
Логін і токени НЕ потрібні. Також друкує поточну версію (version.json) та release з
environment-чанка — саме release, а не version.json, змінюється при новій збірці.
"""
import pathlib
import re
import sys
import urllib.request

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"}


def main() -> None:
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    out = pathlib.Path(sys.argv[1])
    base = (sys.argv[2] if len(sys.argv) > 2 else "https://mystat.itstep.org/").rstrip("/") + "/"
    out.mkdir(parents=True, exist_ok=True)

    def get(name: str) -> bytes:
        req = urllib.request.Request(base + name, headers=UA)
        return urllib.request.urlopen(req, timeout=60).read()

    print("version.json:", get("assets/version.json").decode().strip().replace("\n", " "))
    index = get("")
    (out / "index.html").write_bytes(index)
    for name in sorted(set(re.findall(r"(?:main|polyfills)-[A-Za-z0-9_-]+\.js|styles-[A-Za-z0-9_-]+\.css", index.decode()))):
        print("entry:", name)
        (out / name).write_bytes(get(name))
    for n in range(1, 11):
        refs: set[str] = set()
        for f in out.glob("*.js"):
            refs |= set(re.findall(r"chunk-[A-Za-z0-9_-]{4,14}\.js", f.read_text("utf-8", errors="ignore")))
        missing = sorted(r for r in refs if not (out / r).exists())
        print(f"прохід {n}: бракує {len(missing)}")
        if not missing:
            break
        for name in missing:
            try:
                (out / name).write_bytes(get(name))
            except Exception as exc:  # noqa: BLE001 - інформаційний скрипт
                print("ПОМИЛКА", name, exc)
                (out / name).write_bytes(b"")
    for f in out.glob("*.js"):
        m = re.search(r"release:`([0-9a-f]{40})`", f.read_text("utf-8", errors="ignore"))
        if m:
            print("release:", m.group(1))
    print("файлів .js:", len(list(out.glob("*.js"))))


if __name__ == "__main__":
    main()
