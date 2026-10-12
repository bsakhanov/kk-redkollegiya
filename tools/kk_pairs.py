#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Beibit Sakhanov
"""kk_pairs.py — параллельный корпус из двуязычного Telegram-канала и кандидаты в глоссарий.

Канал публикует новости на двух языках почти одновременно (медиана разрыва — полминуты), так что из
выгрузки Telegram Desktop (result.json) получается настоящий корпус переводов, сделанных пресс-службой:
эталон терминологии заказчика, материал для проверки kk_parity и примеры стиля для LLM-этапов.

Команды:
  consistency pairs.jsonl --glossary glossary.yaml --term-pairs term_pairs.yaml -o отчёт.tsv [--write]
         Согласованность переводов с глоссарием: сколько раз, когда в русском стоит понятие, в казахском стоит
         выбранная форма; записи с низкой согласованностью выключаются из проверки PR06 (parity_check: false).
  build  result.json -o pairs.jsonl
         Делит сообщения по языку (доля казахских букв среди кириллических ≥ 6%, не меньше 20 букв)
         и сопоставляет казахский пост с русским: окно ±4 часа, схожесть чисел и латинских имён,
         отношение длин 0,6–2,2, один к одному.
  align  pairs.jsonl -o кандидаты.tsv [--min-pairs 12] [--min-dice 0.45]
         Для русских слов (основа — первые 6 букв) ищет казахские основы (первые 5 букв), чаще всего
         встречающиеся в парах (коэффициент Дайса). Это кандидаты в глоссарий, а не словарь:
         вердикт по каждой паре выносит человек.

Использование из набора:
    kk_pairs.py build result.json -o pairs.jsonl
    kk_pairs.py align pairs.jsonl -o term_candidates.tsv

Только стандартная библиотека. Тексты каналов в набор не входят.
"""

import argparse
import bisect
import collections
import datetime
import json
import re
import statistics
import sys

SP = "әғқңөұүһіӘҒҚҢӨҰҮҺІ"
CYR = "А-Яа-яЁёӘәҒғҚқҢңӨөҰұҮүҺһІі"
NUM = re.compile(r"\d+(?:[.,]\d+)?")
LAT = re.compile(r"[A-Za-z][A-Za-z0-9&.-]{2,}")
URL = re.compile(r"https?://\S+")
STOP = set("""также которые которых который которая этого этой этом этот более очень было были была будет будут после
перед через между около свыше ранее нужно нашей нашего своей своих своего своим всех всего всем всей данный данные
данной может могут можно этих тоже когда если чтобы только лишь вновь снова уже еще ещё""".split())


def flat(m):
    t = m.get("text")
    if isinstance(t, list):
        return "".join(x if isinstance(x, str) else x.get("text", "") for x in t)
    return t or ""


def lang(t):
    cy = len(re.findall(rf"[{CYR}]", t))
    if cy < 20:
        return None
    return "kk" if sum(1 for c in t if c in SP) / cy > 0.06 else "ru"


def nums(t):
    return collections.Counter(x.replace(",", ".") for x in NUM.findall(URL.sub("", t)))


def lat(t):
    return {x.lower() for x in LAT.findall(URL.sub("", t))}


def cmd_build(a):
    d = json.load(open(a.telegram, encoding="utf-8"))
    rows = []
    for m in d["messages"]:
        if m.get("type") != "message":
            continue
        t = flat(m)
        l = lang(t)
        if l:
            rows.append({"id": m["id"], "t": datetime.datetime.fromisoformat(m["date"]), "lang": l, "text": t})
    kk = [r for r in rows if r["lang"] == "kk"]
    ru = [r for r in rows if r["lang"] == "ru"]
    rt = [r["t"] for r in ru]
    used, pairs = set(), []
    for k in kk:
        i = bisect.bisect_left(rt, k["t"])
        best = None
        for j in range(max(0, i - 6), min(len(ru), i + 7)):
            r = ru[j]
            dt = abs((r["t"] - k["t"]).total_seconds()) / 60
            if dt > 240 or r["id"] in used:
                continue
            sk, sr = set(nums(k["text"])), set(nums(r["text"]))
            jc = len(sk & sr) / len(sk | sr) if (sk or sr) else None
            lk, lr = lat(k["text"]), lat(r["text"])
            jl = len(lk & lr) / len(lk | lr) if (lk or lr) else None
            ratio = len(k["text"]) / max(len(r["text"]), 1)
            score = 0.5 * (jc if jc is not None else 0.5) + 0.3 * (jl if jl is not None else 0.5) + 0.2 * max(0, 1 - dt / 60)
            if 0.6 <= ratio <= 2.2 and (best is None or score > best[0]):
                best = (score, r, dt, jc)
        if best and best[0] >= 0.62 and (best[3] is None or best[3] >= 0.6):
            pairs.append((k, best))
            used.add(best[1]["id"])
    with open(a.out, "w", encoding="utf-8") as f:
        for k, (sc, r, dt, jc) in pairs:
            f.write(json.dumps({"kk_id": k["id"], "ru_id": r["id"], "date": k["t"].isoformat(), "dt_min": round(dt, 1),
                                "score": round(sc, 2), "kk": k["text"], "ru": r["text"]}, ensure_ascii=False) + "\n")
    med = statistics.median(p[1][2] for p in pairs) if pairs else 0
    print(f"казахских постов {len(kk)}, русских {len(ru)}, пар {len(pairs)} ({100*len(pairs)/max(len(kk),1):.0f}% казахских); "
          f"медиана разрыва {med:.1f} мин")
    return 0


def _stems(text, n, minlen):
    out = {}
    for w in re.findall(rf"[{CYR}]+", URL.sub("", text.lower())):
        if len(w) >= minlen and w not in STOP:
            out.setdefault(w[:n], collections.Counter())[w] += 1
    return out


def cmd_align(a):
    P = [json.loads(l) for l in open(a.pairs, encoding="utf-8")]
    rdf, kdf, rk = collections.Counter(), collections.Counter(), collections.Counter()
    rform, kform = collections.defaultdict(collections.Counter), collections.defaultdict(collections.Counter)
    for p in P:
        rs, ks = _stems(p["ru"], 6, 6), _stems(p["kk"], 5, 4)
        for s, c in rs.items():
            rdf[s] += 1
            rform[s].update(c)
        for s, c in ks.items():
            kdf[s] += 1
            kform[s].update(c)
        for r in rs:
            for k in ks:
                rk[(r, k)] += 1
    best = {}
    for (r, k), c in rk.items():
        if rdf[r] < a.min_pairs or c < 3:
            continue
        dice = 2 * c / (rdf[r] + kdf[k])
        if dice >= a.min_dice and (r not in best or dice > best[r][0]):
            best[r] = (dice, c, k)
    rows = sorted(best.items(), key=lambda x: -x[1][1])
    with open(a.out, "w", encoding="utf-8") as f:
        f.write("русская форма\tказахская форма\tпар\tДайс\n")
        for r, (d, c, k) in rows:
            f.write(f"{rform[r].most_common(1)[0][0]}\t{kform[k].most_common(1)[0][0]}\t{c}\t{d:.2f}".replace(".", ",", 1) if False
                    else f"{rform[r].most_common(1)[0][0]}\t{kform[k].most_common(1)[0][0]}\t{c}\t{str(round(d, 2)).replace('.', ',')}\n")
    print(f"кандидатов {len(rows)} → {a.out}")
    return 0


def cmd_consistency(a):
    """Согласованность переводов с глоссарием: в скольких парах, где в русском есть понятие, в казахском стоит выбранная форма."""
    import yaml
    gl = yaml.safe_load(open(a.glossary, encoding="utf-8"))
    pairs = {p["key"]: p for p in yaml.safe_load(open(a.term_pairs, encoding="utf-8"))}
    P = [json.loads(l) for l in open(a.pairs, encoding="utf-8")]
    clean = lambda t: re.sub(r"\n\s*\n", " ", URL.sub("", t)).lower()
    guard = rf"(?<![{CYR}A-Za-z])(?:%s)"
    rows = []
    for e in gl.get("entries", []):
        if e.get("status") != "usage" or e["key"] not in pairs:
            continue
        p = pairs[e["key"]]
        lose = p["a"]["re"] if e["kk"] == p["b"]["label"] else p["b"]["re"]
        n = ok = bad = 0
        for q in P:
            ru, kk = clean(q["ru"]), clean(q["kk"])
            if not re.search(e["parity_ru"], ru):
                continue
            n += 1
            if re.search(guard % e["kk_re"], kk):
                ok += 1
            elif re.search(guard % lose, kk):
                bad += 1
        if n < 5:
            continue
        share = ok / n
        e["consistency"] = {"pairs": n, "ok": ok, "other_form": bad, "neither": n - ok - bad, "share": round(share, 2)}
        e["parity_check"] = bool(n >= 20 and share >= a.min_share)
        rows.append((e["key"], e["ru"], e["kk"], n, ok, bad, n - ok - bad, share, e["parity_check"]))
    rows.sort(key=lambda r: -r[3])
    with open(a.out, "w", encoding="utf-8") as f:
        f.write("пара\tрусское\tформа по узусу корпуса\tпар с понятием\tесть форма глоссария\tесть другая форма\tиное\tсогласованность\tPR06 включён\n")
        for k, ru, kk, n, ok, bad, ne, sh, on in rows:
            f.write(f"{k}\t{ru}\t{kk}\t{n}\t{ok}\t{bad}\t{ne}\t{round(100*sh)}%\t{'да' if on else 'нет'}\n")
    if a.write:
        with open(a.glossary, "w", encoding="utf-8") as f:
            yaml.safe_dump(gl, f, allow_unicode=True, sort_keys=False, width=110)
    on = sum(1 for r in rows if r[-1])
    print(f"записей проверено {len(rows)}; PR06 включён у {on} (порог согласованности {int(a.min_share*100)}%) → {a.out}")
    return 0


def main(argv=None):
    import _version
    ap = argparse.ArgumentParser(description="Параллельный корпус из Telegram-канала")
    ap.add_argument("--version", action="version", version="%(prog)s " + _version.get())
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("telegram")
    b.add_argument("-o", "--out", required=True)
    b.set_defaults(fn=cmd_build)
    al = sub.add_parser("align")
    al.add_argument("pairs")
    al.add_argument("-o", "--out", required=True)
    al.add_argument("--min-pairs", type=int, default=12)
    al.add_argument("--min-dice", type=float, default=0.45)
    al.set_defaults(fn=cmd_align)
    co = sub.add_parser("consistency")
    co.add_argument("pairs")
    co.add_argument("--glossary", required=True)
    co.add_argument("--term-pairs", required=True)
    co.add_argument("-o", "--out", required=True)
    co.add_argument("--min-share", type=float, default=0.85)
    co.add_argument("--write", action="store_true", help="записать consistency и parity_check в глоссарий")
    co.set_defaults(fn=cmd_consistency)
    a = ap.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
