#!/bin/sh
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Beibit Sakhanov
# Скачивает словарь hunspell-kk из архива Ubuntu и кладёт kk_KZ.aff/.dic в data/hunspell/.
# Словарь трёхлицензионный (GPL / LGPL / MPL), в репозиторий не входит.
set -e
here="$(cd "$(dirname "$0")/.." && pwd)"
mkdir -p "$here/data/hunspell" "$here/.cache"
url="http://archive.ubuntu.com/ubuntu/pool/main/h/hunspell-kk/hunspell-kk_1.1-2.1_all.deb"
curl -fsSL -m 60 -o "$here/.cache/hunspell-kk.deb" "$url"
dpkg-deb -x "$here/.cache/hunspell-kk.deb" "$here/.cache/ex"
cp "$here/.cache/ex/usr/share/hunspell/kk_KZ.aff" "$here/.cache/ex/usr/share/hunspell/kk_KZ.dic" "$here/data/hunspell/"
echo "готово: $here/data/hunspell/kk_KZ.{aff,dic}"
