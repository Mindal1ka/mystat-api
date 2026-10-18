# -*- coding: utf-8 -*-
r"""
Сканер бандлів mystat.itstep.org: витягує ендпоінти та енами.
Запуск: python tools\scan_bundles.py
Повний звіт: tools\scan_report.txt (+ коротке зведення в stdout)
"""
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
BUNDLES = ROOT / "bundles"
REPORT = ROOT / "tools" / "scan_report.txt"

out_lines = []


def say(line=""):
    print(line)
    out_lines.append(line)


def load_files():
    return sorted(BUNDLES.glob("*.js"))


# ── 1. ЕНДПОІНТИ ──────────────────────────────────────────────────────────────
RE_GETEP = re.compile(r"""getEndpoint\(\s*(['"`])(.{1,120}?)\1""", re.S)
RE_APIURL = re.compile(r"""\{\{?\s*t\.apiUrl\s*\}?\}\s*(/[A-Za-z0-9_\-/.{}\[\]$]+)""")
RE_V1 = re.compile(r"""(['"`])(/v1/[A-Za-z0-9_\-/.{}\[\]$]+)\1""")
RE_RELURL = re.compile(
    r"""(?:endpoint|url|path|Url|URL)\s*[:=]\s*(['"`])(/(?:[A-Za-z0-9_\-]/{0,1}){1,10})\1"""
)

NOISE = (".css", ".png", ".svg", ".woff", ".ttf", ".ico", "assets/", "//", "/*")


def is_noise(s):
    s = s.strip()
    return (
        not s
        or len(s) > 90
        or any(n in s.lower() for n in NOISE)
        or " " in s.split("?")[0]
    )


def section_endpoints(files):
    say("=" * 78)
    say("1. ЕНДПОІНТИ З БАНДЛІВ")
    say("=" * 78)
    getep = {}      # шлях -> set(файли)
    absurls = {}
    v1 = {}
    rel = {}
    for f in files:
        try:
            txt = f.read_text(encoding="utf-8", errors="ignore")
        except OSError as e:
            say(f"!! {f.name}: {e}")
            continue
        for m in RE_GETEP.finditer(txt):
            p = m.group(2).strip()
            if not is_noise(p):
                getep.setdefault(p, set()).add(f.name)
        for m in RE_APIURL.finditer(txt):
            p = m.group(1).strip()
            if not is_noise(p):
                absurls.setdefault(p, set()).add(f.name)
        for m in RE_V1.finditer(txt):
            p = m.group(2).strip()
            if not is_noise(p):
                v1.setdefault(p, set()).add(f.name)
        for m in RE_RELURL.finditer(txt):
            p = m.group(2).strip()
            if not is_noise(p):
                rel.setdefault(p, set()).add(f.name)

    def dump(title, d):
        say(f"\n--- {title}: {len(d)} унікальних ---")
        for p in sorted(d):
            fl = sorted(d[p])
            tail = fl[0] if len(fl) == 1 else f"{len(fl)} файлів"
            say(f"  {p:<62} [{tail}]")

    dump("getEndpoint('<відносний>') — база /v1/mystat/{alias}", getep)
    dump("${apiUrl}/<абсолютний>", absurls)
    dump("/v1/ літерали", v1)
    dump("endpoint:/url: відносні", rel)


# ── 2. СТАТУСИ HOMEWORK ───────────────────────────────────────────────────────
HOMEWORK_FILES_HINT = "homework"
RE_STATUS_CTX = re.compile(
    r".{0,160}(?:status|Status|STATUS).{0,220}", re.S
)
RE_STATUS_CMP = re.compile(
    r"""(?:status|state)\s*={2,3}\s*(['"]?)([\w.\-]+)\1"""
)


def section_homework(files):
    say("")
    say("=" * 78)
    say("2. HOMEWORK: КОНТЕКСТИ СТАТУСІВ")
    say("=" * 78)
    hw_files = [f for f in files if HOMEWORK_FILES_HINT in f.read_text(encoding="utf-8", errors="ignore").lower()]
    seen = set()
    for f in hw_files:
        txt = f.read_text(encoding="utf-8", errors="ignore")
        low = txt.lower()
        idx = 0
        hits = []
        while True:
            i = low.find("homework", idx)
            if i < 0:
                break
            win = txt[max(0, i - 60): i + 400]
            # у вікні шукаємо згадку статусу
            for sm in RE_STATUS_CMP.finditer(win):
                key = sm.group(0)[:80]
                if key not in seen:
                    seen.add(key)
                    hits.append((i, key))
            idx = i + 8
        if hits:
            say(f"\n### {f.name}")
            for _, h in hits[:25]:
                say(f"   cmp: {h}")

    # сирі вікна навколо 'status' усередині homework-чанків
    say("\n--- Сирі вікна (status поруч із homework) ---")
    shown = 0
    for f in hw_files:
        txt = f.read_text(encoding="utf-8", errors="ignore")
        low = txt.lower()
        for m in re.finditer(r"homework", low):
            i = m.start()
            win = txt[max(0, i - 100): i + 500]
            if "status" in win.lower():
                w = re.sub(r"\s+", " ", win).strip()
                if w[:150] not in seen:
                    seen.add(w[:150])
                    say(f"\n[{f.name}] …{w}…")
                    shown += 1
                    if shown >= 40:
                        return


# ── 3. ЧИСЛОВІ/РЯДКОВІ ЕНАМИ СТАТУСІВ ВЗАГАЛІ ──────────────────────────────
def section_status_enums(files):
    say("")
    say("=" * 78)
    say("3. ВСІ ПОРІВНЯННЯ status/state === X ПО ВСІХ ЧАНКАХ")
    say("=" * 78)
    agg = {}
    for f in files:
        try:
            txt = f.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for m in RE_STATUS_CMP.finditer(txt):
            val = m.group(2)
            agg.setdefault(val, set()).add(f.name)
    for val in sorted(agg):
        fl = agg[val]
        say(f"  {val:<30} x{len(fl):<3} {sorted(fl)[0]}")


def main():
    files = load_files()
    say(f"# Сканер бандлів: {len(files)} файлів\n")
    section_endpoints(files)
    section_status_enums(files)
    section_homework(files)
    REPORT.write_text("\n".join(out_lines), encoding="utf-8")
    print(f"\n[OK] Повний звіт: {REPORT}")


if __name__ == "__main__":
    main()
