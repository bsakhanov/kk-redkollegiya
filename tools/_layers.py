# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Beibit Sakhanov
"""Слои проверок и их имена.

В русской Редколлегии слои носят имена тех, чьё слово в своём ремесле служит мерой (Чуковский, Аграновский, Розенталь,
Мильчин). Здесь заведён тот же обычай. Зона находки (поле zone) определяет слой (поле layer):

    hygiene, typography  → altynsarin   Алтынсарин   (русский образец — Мильчин)
    parity, facts        → valikhanov   Валиханов    (Аграновский)
    terms                → shakarim     Шакарим
    norm                 → baitursynov  Байтурсынов  (Розенталь)

За будущими проходами зарезервированы auezov (смысл и живая речь; Чуковский) и slopotron-kk (следы машинного письма).
"""

LAYER_BY_ZONE = {
    "hygiene": "altynsarin", "typography": "altynsarin",
    "parity": "valikhanov", "facts": "valikhanov",
    "terms": "shakarim",
    "norm": "baitursynov",
    "meaning": "auezov",
    "ai-markers": "slopotron-kk",
}

NAMES = {"altynsarin": "Алтынсарин", "valikhanov": "Валиханов", "shakarim": "Шакарим", "baitursynov": "Байтурсынов",
         "auezov": "Ауэзов", "slopotron-kk": "Слопотрон-kk"}


def layer_of(zone):
    """Слой по зоне находки (пустая строка, если зона неизвестна)."""
    return LAYER_BY_ZONE.get(zone, "")


def summary(findings):
    """Строка «Алтынсарин — 12, Шакарим — 3» для сводки в консоли."""
    n = {}
    for f in findings:
        k = f.get("layer") or "—"
        n[k] = n.get(k, 0) + 1
    return ", ".join(f"{NAMES.get(k, k)} — {v}" for k, v in sorted(n.items(), key=lambda kv: -kv[1]))
