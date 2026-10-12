# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Beibit Sakhanov
"""Версия набора: читается из файла VERSION в корне репозитория."""
import os


def get():
    p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "VERSION")
    try:
        return open(p, encoding="utf-8").read().strip()
    except OSError:
        return "unknown"
