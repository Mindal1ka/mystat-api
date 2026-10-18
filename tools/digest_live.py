# -*- coding: utf-8 -*-
"""
Компактний дайджест прикладів з examples/live/*.json:
тип, ключі верхнього рівня, ключі першого елемента списку, розміри.
Запуск: python tools\\digest_live.py [частина_імені_файлу]
"""
import json, os, sys, glob

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "examples", "live")
flt = sys.argv[1] if len(sys.argv) > 1 else ""


def shape(v, depth=0):
    if isinstance(v, dict):
        inner = {k: shape(x, depth + 1) for k, x in list(v.items())[:14]}
        return "{" + ", ".join("%s:%s" % (k, t) for k, t in inner.items()) + ("…" if len(v) > 14 else "") + "}"
    if isinstance(v, list):
        return "[%d x %s]" % (len(v), shape(v[0], depth + 1) if v else "?")
    s = str(v)
    return s if len(s) <= 28 else "<%s>" % type(v).__name__


for p in sorted(glob.glob(os.path.join(OUT, "*"+flt+"*.json"))):
    name = os.path.basename(p)
    if name.startswith("_"):
        continue
    raw = open(p, "rb").read()
    try:
        j = json.loads(raw)
    except Exception:
        print("%-34s %6dB  <не-JSON: %r...>" % (name, len(raw), raw[:40]))
        continue
    print("%-34s %6dB  %s" % (name, len(raw), shape(j)))
