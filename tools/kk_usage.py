#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Beibit Sakhanov
"""kk_usage.py — политика терминов «узус корпуса; международное слово — только там, где узус молчит».

Скрипт применяет её к корпусу заказчика: для каждой пары
«международная форма — казахская форма» считает частоты в казахском тексте и принимает решение:

  usage      одна форма занимает не меньше 70% вхождений (при ≥ 10 вхождений всего): пишем её,
             вторая уходит в avoid;
  silent     вхождений меньше 10: узус молчит, берётся международная форма (по решению автора);
  contested  доли в пределах 30–70%: узус разделён, запись остаётся за автором (по умолчанию —
             форма, у которой больше вхождений), в avoid ничего не попадает.

Результат — записи для glossary.yaml (с полем evidence: частоты и доли) и таблица в консоль.
Записи с другим status (author — решения автора) при --merge сохраняются и не перезаписываются.

Использование:
    kk_usage.py --groups data/corpus_groups.yaml --group corporate --pairs data/term_pairs.yaml \
                [--merge data/glossary.yaml] [--out data/glossary.yaml] [--tsv отчёт.tsv]
    kk_usage.py --selftest
Только стандартная библиотека; для YAML нужен PyYAML (pip install pyyaml).
"""

import argparse
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from kk_attest import L, _load_cfg, load_text, pat  # noqa: E402

MIN_TOTAL = 10
MAJORITY = 0.70


def decide(ca, cb, min_total=MIN_TOTAL, majority=MAJORITY):
    """-> (status, победившая сторона 'a' или 'b')."""
    t = ca + cb
    if t < min_total:
        return "silent", "a"
    sb = cb / t
    if sb >= majority:
        return "usage", "b"
    if sb <= 1 - majority:
        return "usage", "a"
    return "contested", ("b" if cb >= ca else "a")


def make_entry(p, ca, cb, n_words, status, win):
    w, l = (p["b"], p["a"]) if win == "b" else (p["a"], p["b"])
    rate = lambda c: round(1e5 * c / max(n_words, 1), 1)
    t = max(ca + cb, 1)
    e = {
        "key": p["key"], "ru": p["ru"], "kk": w["label"],
        "avoid": [l["label"]] if status == "usage" else [],
        "avoid_action": "suggest",
        "status": status,
        "kk_re": w["re"],
        "parity_ru": p.get("parity_ru"),
        "evidence": {"corpus_words": n_words,
                     "a": {"form": p["a"]["label"], "count": ca, "per100k": rate(ca), "share": round(ca / t, 2)},
                     "b": {"form": p["b"]["label"], "count": cb, "per100k": rate(cb), "share": round(cb / t, 2)}},
        "decided": "политика узуса корпуса",
    }
    if p.get("avoid_exclude"):
        e["avoid_exclude"] = list(p["avoid_exclude"])
    if p.get("no_avoid"):
        e["avoid"] = []
    if p.get("note") and status == "usage":
        e["note"] = p["note"]
    if status == "silent":
        e["note"] = "узус молчит: по решению автора берётся международная форма"
    elif status == "contested":
        e["note"] = "узус разделён: нужен вердикт автора; пока — форма с большим числом вхождений"
    return e


def run(pairs, texts, n_words):
    out = []
    for p in pairs:
        ca = len(pat(p["a"]["re"]).findall(texts))
        cb = len(pat(p["b"]["re"]).findall(texts))
        status, win = decide(ca, cb)
        out.append((p, ca, cb, status, win, make_entry(p, ca, cb, n_words, status, win)))
    return out


def _selftest():
    assert decide(5, 4) == ("silent", "a")
    assert decide(10, 90) == ("usage", "b")
    assert decide(90, 10) == ("usage", "a")
    assert decide(40, 60) == ("contested", "b")
    p = {"key": "x", "ru": "икс", "a": {"label": "а", "re": "а"}, "b": {"label": "б", "re": "б"}}
    e = make_entry(p, 10, 90, 100000, "usage", "b")
    assert e["kk"] == "б" and e["avoid"] == ["а"] and e["evidence"]["b"]["share"] == 0.9
    print("kk_usage selftest: ok")


def main(argv=None):
    import _version
    ap = argparse.ArgumentParser(description="Политика терминов: узус корпуса, международное — где узус молчит")
    ap.add_argument("--version", action="version", version="%(prog)s " + _version.get())
    ap.add_argument("--groups")
    ap.add_argument("--group", default="corporate")
    ap.add_argument("--pairs")
    ap.add_argument("--merge", help="существующий glossary.yaml: решения автора сохраняются")
    ap.add_argument("--out")
    ap.add_argument("--tsv")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        _selftest()
        return 0
    if not (a.groups and a.pairs):
        ap.error("нужны --groups и --pairs")
    groups, pairs = _load_cfg(a.groups), _load_cfg(a.pairs)
    base = os.path.dirname(os.path.abspath(a.groups))
    g = groups[a.group]
    texts = " ".join(load_text(f if os.path.isabs(f) else os.path.join(base, f)) for f in g["files"])
    n_words = len(re.findall(rf"[{L}]+", texts))
    res = run(pairs, texts, n_words)
    print(f"корпус «{g['label']}»: {n_words:,} слов; порог большинства {int(MAJORITY*100)}%, минимум {MIN_TOTAL} вхождений".replace(",", " "))
    print(f"{'пара':16}{'международная':>22}{'казахская':>22}{'доля каз.':>10}  решение")
    for p, ca, cb, st, win, e in res:
        t = max(ca + cb, 1)
        print(f"{p['key']:16}{p['a']['label'][:14]+' '+str(ca):>22}{p['b']['label'][:14]+' '+str(cb):>22}{100*cb/t:>9.0f}%  {st:9} → {e['kk']}")
    if a.tsv:
        with open(a.tsv, "w", encoding="utf-8") as f:
            f.write("пара\tрусское\tмеждународная форма\tчисло\tказахская форма\tчисло\tдоля казахской\tрешение\tформа\n")
            for p, ca, cb, st, win, e in res:
                t = max(ca + cb, 1)
                f.write(f"{p['key']}\t{p['ru']}\t{p['a']['label']}\t{ca}\t{p['b']['label']}\t{cb}\t{round(100*cb/t)}%\t{st}\t{e['kk']}\n")
    if a.out:
        import yaml
        gl = {}
        if a.merge and os.path.exists(a.merge):
            gl = yaml.safe_load(open(a.merge, encoding="utf-8")) or {}
        gl.setdefault("version", 0.2)
        gl["policy"] = {"rule": "usage-first",
                        "text": "узус корпуса заказчика; международное слово — только там, где узус молчит",
                        "corpus": f"{g['label']}, {n_words} слов", "majority": MAJORITY, "min_total": MIN_TOTAL}
        keep = [e for e in gl.get("entries", []) if e.get("status") not in ("usage", "silent", "contested")]
        gen = [e for *_, e in res]
        taken = {e["key"] for e in keep}
        gl["entries"] = keep + [e for e in gen if e["key"] not in taken]
        with open(a.out, "w", encoding="utf-8") as f:
            yaml.safe_dump(gl, f, allow_unicode=True, sort_keys=False, width=110)
        print(f"глоссарий записан: {a.out} ({len(gl['entries'])} записей)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
