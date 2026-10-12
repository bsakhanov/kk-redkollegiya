# kk-redkollegiya

[![Лицензия: GPL-3.0-or-later](https://img.shields.io/badge/license-GPL--3.0--or--later-blue.svg)](LICENSE)
[![Python 3.8+](https://img.shields.io/badge/python-3.8%2B-blue.svg)](requirements.txt)
[![Версия 0.4.0](https://img.shields.io/badge/version-0.4.0-green.svg)](CHANGELOG.md)

**Русский** · [English](#english)

Технический слой языкового прогона казахских текстов: чистка кодировки и алфавита, восстановление казахских букв,
линтер, сверка с русским оригиналом и политика терминов по живому узусу. Задуман по образцу
[redkollegiya](https://github.com/beaverbeard/redkollegiya) — оркестратора редактуры русского текста для Claude Code, —
но для казахского языка. Скрипты отдают находки в формате `apply.py` из redkollegiya (дословная цитата, замена, уровень),
а решение по спорному остаётся за читающим по-казахски.

> **Статус: 0.x.** Готов первый слой — скрипты. LLM-этапы (смысл и кальки, следы машинного письма, орфография)
> и скрипт-типограф ещё не написаны, см. [дорожную карту](#дорожная-карта).

## Что внутри

| Файл | Что делает |
| --- | --- |
| `tools/kk_clean.py` | восстановление текста: Юникод NFC, старая кодировка казахских шрифтов, латинская «ə» вместо «ә», буквы-заместители (управляющие и латинские символы вместо қ ғ ң ә ө ұ ү һ і), латинские двойники внутри слов |
| `tools/kk_restore.py` | символьная модель (5-граммы) для восстановления казахских букв в словах, набранных на русской раскладке |
| `tools/kk_lint.py` | детекторы технических дефектов; находки в формате `apply.py`; профили `prose` и `ini` (языковые пакеты Joomla) |
| `tools/kk_parity.py` | сверка казахской версии с русским оригиналом: числа, даты, шкала «мың / млн / млрд», латинские имена, термины глоссария |
| `tools/kk_pairs.py` | параллельный корпус из выгрузки двуязычного Telegram-канала; кандидаты в двуязычный глоссарий; согласованность переводов с глоссарием |
| `tools/kk_usage.py` | политика терминов «узус корпуса; международное слово — только там, где узус молчит» |
| `tools/kk_attest.py` | засвидетельствованность: частота оборота по группам корпуса на 100 тыс. слов и контексты |
| `tools/fetch_hunspell_kk.sh` | скачивает словарь hunspell-kk (в репозиторий не входит) |
| `data/` | глоссарий-пример, пары терминов, списки оборотов, пример групп корпуса |
| `docs/RULES.md` | справочник правил детекторов (коды, уровни, действия) |
| `tests/` | самопроверки и образец текста с подсаженными дефектами |

## Как это устроено

```
казахский текст (+ русский оригинал)
  → А-kk     kk_clean · kk_restore · kk_lint     гигиена: кодировка, алфавит, словарь, числа, заполнители
  → parity   kk_parity · kk_pairs                сверка с оригиналом
  → terms    kk_usage · glossary.yaml            термины по узусу корпуса
  → …        LLM-этапы: meaning-kk, ai-markers-kk, norm-kk (в планах)
  → apply.py (redkollegiya)                      внесение находок по дословным цитатам
  → вердикт читающего по-казахски
```

Принципы:

- **Раздельные проходы** со своими зонами (`hygiene`, `parity`, `terms`, `norm`, `typography`): гигиена дёшева и идёт при каждой сборке, вердикты человека дороги.
- **Переписчиков нет.** Каждый этап отдаёт находки с дословной цитатой, вносит их `apply.py`. На языке, где правку труднее проверить на глаз, свободный перепис опаснее.
- **Спорное — автору.** Находки уровня `author_choice` в текст молча не вносятся.
- **Гигиена идёт первой:** `apply.py` якорит цитаты побуквенно, и латинская `i` вместо `і` или разложенное `ә` ломают якорение.

## Установка

```bash
git clone https://github.com/bsakhanov/kk-redkollegiya.git
cd kk-redkollegiya
pip install -r requirements.txt        # spylls (словарь Hunspell), pyyaml
sh tools/fetch_hunspell_kk.sh          # словарь hunspell-kk → data/hunspell/ (в репозиторий не входит)
sh tests/run_tests.sh                  # самопроверки без внешних данных
```

Нужен Python 3.8+. Скрипт `apply.py` берётся из [redkollegiya](https://github.com/beaverbeard/redkollegiya) (MIT) и в набор не входит:
путь к нему передаётся при запуске. Сквозная проверка с ним: `APPLY=/путь/к/apply.py sh tests/run_tests.sh`.
У каждой утилиты есть `--version`.

## Быстрый старт

```bash
# 1. чистка (книги, выгрузки из PDF); журнал показывает, что и сколько починено
python3 tools/kk_clean.py книги/*.txt -o чистое/ --dict data/hunspell/kk_KZ --journal журнал.json

# 2. модель букв — по чистому корпусу; остаётся у вас и наружу не публикуется
python3 tools/kk_restore.py train чистое/*.txt -o lm.json.gz

# 3. линтер: находки в формате apply.py
python3 tools/kk_lint.py текст.md --dict data/hunspell/kk_KZ --glossary data/glossary.yaml \
        --lm lm.json.gz --json находки.json

# 4. внесение находок скриптом redkollegiya
python3 /путь/к/redkollegiya/apply.py --text текст.md --findings находки.json \
        --out текст_v2.md --report отчёт.json

# сверка с русским оригиналом (абзацы разделены пустой строкой)
python3 tools/kk_parity.py --ru оригинал.md --kk казахский.md --glossary data/glossary.yaml

# языковые пакеты Joomla: проверяются только значения, заполнители сверяются с исходным файлом
python3 tools/kk_lint.py kk-KZ.com_x.ini --profile ini --source en-GB.com_x.ini --dict data/hunspell/kk_KZ

# параллельный корпус из выгрузки Telegram Desktop и кандидаты в двуязычный глоссарий
python3 tools/kk_pairs.py build result.json -o pairs.jsonl
python3 tools/kk_pairs.py align pairs.jsonl -o term_candidates.tsv
```

`kk_lint.py` завершается кодом 2, если есть находка уровня `blocker` (например, потерян заполнитель `%s` в строке Joomla).
Правила и коды находок — в [docs/RULES.md](docs/RULES.md).

## Что проверено

Замеры сделаны на частных корпусах автора (книги, газеты, двуязычный корпоративный канал); сами тексты в репозиторий не входят.

| Что | Результат |
| --- | --- |
| Декодер старой кодировки казахских шрифтов | три тома романа из PDF: после декодирования словарь узнаёт 77–79% слов, до этого текст нечитаем |
| Буквы-заместители (управляющие и латинские символы) | PDF-книга: около 760 символов; 602 слова подтверждены словарём, 154 выведены по контексту |
| Восстановление казахских букв (`kk_restore`) | на книгах, которых модель не видела: 90,1% слов с первой попытки; на предложениях с одним испорченным словом — 77% (проза XX века) и 69% (Абай); ложные подсказки в 3,9% и 13,2% нетронутых предложений |
| Сверка RU↔KK (`kk_parity`) | 1 516 пар постов двуязычного корпоративного канала: расхождений нет в 69,0% пар, изменённые значения чисел — в 1,7% |
| Политика терминов (`kk_usage`) | в примере глоссария 25 пар: 23 решения по узусу и 2 спорных, закрытых решением автора |

## Политика терминов

`kk_usage.py` применяет к корпусу заказчика правило **«узус корпуса; международное слово — только там, где узус молчит»**.
Для каждой пары «международная форма — казахская форма» он считает вхождения в казахском тексте и принимает решение:

| status | Условие | Что записывается |
| --- | --- | --- |
| `usage` | одна форма занимает не меньше 70% вхождений, всего не меньше 10 | эта форма; вторая — в `avoid` |
| `silent` | меньше 10 вхождений: узус молчит | международная форма |
| `contested` | доли от 30 до 70% | запись остаётся за автором (пока — форма с большим числом вхождений) |
| без `status` | решение автора | не перезаписывается при `--merge` |

Решения применяются как предложения (`author_choice`), а не как молчаливая правка: проигравшая форма встречается у носителей,
и часть вхождений стоит внутри названий. Для записей, где переводчики корпуса в 85% и больше пар ставят выбранную форму,
включена проверка PR06 в `kk_parity`. Сам глоссарий — [data/glossary.yaml](data/glossary.yaml) — пример; замените его своим.

## Данные и приватность

В репозиторий не входят ни тексты корпусов, ни обученные модели (`lm.json.gz`): книги и публикации могут быть под охраной,
а модель — производные частоты. `.gitignore` закрывает такие файлы. Словарь hunspell-kk скачивается отдельно.

## Ограничения

- Словарь hunspell-kk (проект OpenOffice конца 2000-х, около 54 тыс. основ) служит поставщиком кандидатов, а не судьёй: на малой выборке он счёл неизвестными 14% верных слов, но поймал 11 из 11 нарочно испорченных.
- Подсказки восстановления букв по умолчанию идут как `suggest`; внесение без вердикта (`--auto-restore`) допустимо только для текста, набранного целиком без казахских букв.
- Латиница не обрабатывается: алфавит на латинской графике не утверждён. Латинские слова (в том числе «Sáýir») не трогаются.
- Орфографический словарь 2013 года в машинном виде не подключён, морфоанализатор (`apertium-kaz`) не проверен.
- Числа, записанные словом, при сверке не сравниваются; пересчёт единиц даёт ложные срабатывания.
- Качество LLM-этапов не измерено: gold-set ещё нет. Скрипты не заменяют читающего по-казахски.

## Дорожная карта

- [ ] LLM-этапы: `meaning-kk` (кальки, порядок слов, управление), `ai-markers-kk`, `norm-kk`, `terms-kk`
- [ ] скрипт-типограф `typography-kk`
- [ ] gold-set на 150–300 предложений с пометкой носителя
- [ ] подключение морфоанализатора и словаря 2013 года
- [ ] профили регистра («советская норма», «классический», «официальный», «пресс-релиз»)
- [ ] полный текст методологии в `docs/`

## Версионирование

[Семантическое версионирование](https://semver.org/lang/ru/): `MAJOR.MINOR.PATCH`. Пока `0.x`, интерфейсы командной строки могут меняться;
формат находок стабилен и совпадает с контрактом `apply.py`. Версия лежит в файле `VERSION`, выводится флагом `--version`,
отмечается тегами `vX.Y.Z` и описывается в [CHANGELOG.md](CHANGELOG.md).

## Участие

Замечания и PR приветствуются, см. [CONTRIBUTING.md](CONTRIBUTING.md). Особенно нужны проверка носителями языка и образцы дефектов
без охраняемых текстов.

## Лицензия

[GNU General Public License v3.0 или новее](LICENSE) (`GPL-3.0-or-later`). Сторонние компоненты в набор не входят:
словарь hunspell-kk (GPL / LGPL / MPL, скачивается отдельно), `apply.py` из redkollegiya (MIT), библиотеки spylls (MPL-2.0) и PyYAML (MIT).

## Благодарности

- [redkollegiya](https://github.com/beaverbeard/redkollegiya) (@beaverbeard, MIT) — архитектура оркестровки, формат находок и `apply.py`.
- hunspell-kk (Акмарал Мұсаева, Алексей Липчанский и другие) — словарь для проверки орфографии.
- Центр «Тіл-Қазына» — открытые наборы и модели для казахского языка; изучены при проектировании, в набор не входят.

---

# English

Technical layer for editing Kazakh texts: encoding and alphabet cleanup, Kazakh letter restoration, a linter,
checks against the Russian original, and a usage-based terminology policy. It is modeled on
[redkollegiya](https://github.com/beaverbeard/redkollegiya), an editing orchestrator for Russian text in Claude Code,
but built for Kazakh. The scripts emit findings in the format of redkollegiya's `apply.py` (verbatim quote, replacement,
severity); disputed cases are left to a reader of Kazakh.

> **Status: 0.x.** The first layer (scripts) is ready. LLM stages (meaning and calques, machine-writing traces, orthography)
> and a typography script are not written yet; see the [roadmap](#roadmap).

## What is inside

| File | Purpose |
| --- | --- |
| `tools/kk_clean.py` | text recovery: Unicode NFC, legacy Kazakh font encoding, Latin schwa «ə» for «ә», substitute letters (control and Latin characters standing for қ ғ ң ә ө ұ ү һ і), Latin look-alikes inside Cyrillic words |
| `tools/kk_restore.py` | character n-gram model (n=5) that restores Kazakh letters in words typed on a Russian keyboard |
| `tools/kk_lint.py` | detectors for technical defects; findings in `apply.py` format; `prose` and `ini` (Joomla language pack) profiles |
| `tools/kk_parity.py` | checks a Kazakh version against the Russian original: numbers, dates, scale words, Latin names, glossary terms |
| `tools/kk_pairs.py` | builds a parallel corpus from a bilingual Telegram export; bilingual glossary candidates; translation consistency with the glossary |
| `tools/kk_usage.py` | terminology policy: "corpus usage first; the international word only where usage is silent" |
| `tools/kk_attest.py` | attestation: frequency per 100k words across corpus groups, with contexts |
| `data/`, `docs/RULES.md`, `tests/` | example glossary and term pairs, rule reference, self-tests |

## How it works

```
Kazakh text (+ Russian original)
  → A-kk     kk_clean · kk_restore · kk_lint     hygiene: encoding, alphabet, dictionary, numbers, placeholders
  → parity   kk_parity · kk_pairs                check against the original
  → terms    kk_usage · glossary.yaml            terms by corpus usage
  → …        LLM stages: meaning-kk, ai-markers-kk, norm-kk (planned)
  → apply.py (redkollegiya)                      applies findings by verbatim quote
  → verdict of a reader of Kazakh
```

Principles: separate passes with their own zones; no free rewriting (every stage returns findings with a verbatim quote,
`apply.py` applies them); disputed items go to the author (`author_choice`); hygiene runs first because `apply.py` anchors
quotes character by character.

## Install

```bash
git clone https://github.com/bsakhanov/kk-redkollegiya.git
cd kk-redkollegiya
pip install -r requirements.txt        # spylls (Hunspell dictionary engine), pyyaml
sh tools/fetch_hunspell_kk.sh          # downloads hunspell-kk into data/hunspell/ (not bundled)
sh tests/run_tests.sh                  # self-tests, no external data needed
```

Python 3.8+. `apply.py` comes from [redkollegiya](https://github.com/beaverbeard/redkollegiya) (MIT) and is not bundled;
pass its path at run time (`APPLY=/path/to/apply.py sh tests/run_tests.sh` runs the end-to-end check). Every tool has `--version`.

## Quick start

```bash
python3 tools/kk_clean.py books/*.txt -o clean/ --dict data/hunspell/kk_KZ --journal journal.json
python3 tools/kk_restore.py train clean/*.txt -o lm.json.gz          # stays on your machine
python3 tools/kk_lint.py text.md --dict data/hunspell/kk_KZ --glossary data/glossary.yaml --lm lm.json.gz --json findings.json
python3 /path/to/redkollegiya/apply.py --text text.md --findings findings.json --out text_v2.md --report report.json
python3 tools/kk_parity.py --ru original.md --kk kazakh.md --glossary data/glossary.yaml
python3 tools/kk_lint.py kk-KZ.com_x.ini --profile ini --source en-GB.com_x.ini --dict data/hunspell/kk_KZ
python3 tools/kk_pairs.py build result.json -o pairs.jsonl
```

`kk_lint.py` exits with code 2 when a `blocker` finding exists (for example, a lost `%s` placeholder in a Joomla string).
Rule codes are listed in [docs/RULES.md](docs/RULES.md).

## Measured results

Measured on the author's private corpora (books, newspapers, a bilingual corporate channel); the texts themselves are not in the repository.

| What | Result |
| --- | --- |
| Legacy Kazakh font decoder | three PDF volumes of a novel: after decoding the dictionary recognizes 77–79% of words; before, the text was unreadable |
| Substitute letters (control / Latin characters) | one PDF book: about 760 characters; 602 words confirmed by the dictionary, 154 inferred from context |
| Letter restoration (`kk_restore`) | on books the model had not seen: 90.1% of words restored on the first try; on sentences with one damaged word, 77% (20th-century prose) and 69% (Abai); false suggestions in 3.9% and 13.2% of untouched sentences |
| RU↔KK parity (`kk_parity`) | 1,516 post pairs from a bilingual corporate channel: no discrepancies in 69.0% of pairs, changed number values in 1.7% |
| Terminology policy (`kk_usage`) | example glossary, 25 pairs: 23 usage decisions and 2 disputed cases settled by the author |

## Terminology policy

`kk_usage.py` applies the rule **"corpus usage first; the international word only where usage is silent"**. A form with at least
70% of occurrences (and at least 10 in total) wins (`usage`); with fewer than 10 occurrences usage is silent and the international
form is taken (`silent`); shares between 30% and 70% are `contested` and left to the author; entries without `status` are the
author's decisions and are never overwritten by `--merge`. Decisions are applied as suggestions (`author_choice`), not silent edits.

## Data and privacy

No corpora and no trained models (`lm.json.gz`) are in the repository: books and publications may be copyrighted, and a model
is derived frequency data. `.gitignore` excludes them. The hunspell-kk dictionary is downloaded separately.

## Limitations

The hunspell-kk dictionary (about 54k stems) is a candidate generator, not a judge (14% of correct words flagged as unknown on a small sample);
restoration suggestions are `suggest` by default; Latin-script Kazakh is not processed (no approved Latin alphabet);
the 2013 orthographic dictionary and a morphological analyzer are not integrated; numbers spelled out in words are not compared in parity checks;
LLM stages are unmeasured (no gold set yet). The scripts do not replace a reader of Kazakh.

## Roadmap

LLM stages (`meaning-kk`, `ai-markers-kk`, `norm-kk`, `terms-kk`); a typography script; a gold set of 150–300 sentences reviewed by a native reader;
morphology and the 2013 dictionary; register profiles; the full methodology text in `docs/`.

## Versioning

[Semantic Versioning](https://semver.org/). While `0.x`, command-line interfaces may change; the findings format is stable and matches the `apply.py` contract.
The version lives in `VERSION`, is printed by `--version`, tagged as `vX.Y.Z`, and described in [CHANGELOG.md](CHANGELOG.md).

## Contributing

Issues and pull requests are welcome, see [CONTRIBUTING.md](CONTRIBUTING.md). Reviews by native speakers and defect samples without copyrighted text are especially valuable.

## License

[GNU General Public License v3.0 or later](LICENSE) (`GPL-3.0-or-later`). Third-party components are not bundled:
the hunspell-kk dictionary (GPL / LGPL / MPL, downloaded separately), `apply.py` from redkollegiya (MIT), spylls (MPL-2.0), PyYAML (MIT).

## Acknowledgments

[redkollegiya](https://github.com/beaverbeard/redkollegiya) (@beaverbeard, MIT) for the orchestration design, the findings format and `apply.py`;
the hunspell-kk authors (Akmaral Mussayeva, Alexey Lipchansky and others); the Til-Qazyna center for open Kazakh NLP resources (studied during design, not included).
