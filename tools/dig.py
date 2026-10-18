# -*- coding: utf-8 -*-
"""
Диггер: python tools\\dig.py <chunk-name> <kw1> [kw2 ...]
Друкує вікна ±N символів навколо входжень ключових слів у bundles/<chunk>.
"""
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]

def windows(txt, kw, before=250, after=450):
    low = txt.lower()
    k = kw.lower()
    out, seen, idx = [], set(), 0
    while True:
        i = low.find(k, idx)
        if i < 0:
            break
        w = txt[max(0, i - before): i + after]
        w = re.sub(r"\s+", " ", w).strip()
        key = w[:120]
        if key not in seen:
            seen.add(key)
            out.append(w)
        idx = i + len(kw)
    return out

def main():
    name = sys.argv[1]
    path = ROOT / "bundles" / name
    txt = path.read_text(encoding="utf-8", errors="ignore")
    total = 0
    for kw in sys.argv[2:]:
        ws = windows(txt, kw)
        print(f"\n{'='*78}\n## [{name}] keyword='{kw}' -> {len(ws)} окон\n{'='*78}")
        for w in ws[:14]:
            print(f"\n>>> …{w}…")
            total += 1
    print(f"\n[OK] показано окон: {total}")

if __name__ == "__main__":
    main()
