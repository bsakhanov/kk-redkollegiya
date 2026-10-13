# kk-redkollegiya

[![License: GPL-3.0-or-later](https://img.shields.io/badge/license-GPL--3.0--or--later-blue.svg)](LICENSE)
[![Python 3.8+](https://img.shields.io/badge/python-3.8%2B-blue.svg)](requirements.txt)
[![Version 0.4.5](https://img.shields.io/badge/version-0.4.5-green.svg)](CHANGELOG.md)

[Русский](README.md) · **English** · [Қазақша](README.kk.md)

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
| `data/`, `docs/USAGE.en.md`, `docs/RULES.en.md`, `tests/` | example glossary and term pairs, user guide, rule reference, self-tests |

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
pass its path at run time (`APPLY=/path/to/apply.py sh tests/run_tests.sh` runs the end-to-end check). Every tool has `--version`. The full guide is in [docs/USAGE.en.md](docs/USAGE.en.md).

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
Rule codes are listed in [docs/RULES.en.md](docs/RULES.en.md).

## Measured results

Measured on the author's private corpora (books, newspapers, a bilingual corporate channel); the texts themselves are not in the repository.

| What | Result |
| --- | --- |
| Legacy Kazakh font decoder | three PDF volumes of a novel: after decoding the dictionary recognizes 77–79% of words; before, the text was unreadable |
| Substitute letters (control / Latin characters) | one PDF book: about 760 characters; 602 words confirmed by the dictionary, 154 inferred from context |
| Letter restoration (`kk_restore`) | on books the model had not seen: 90.1% of words restored on the first try; on sentences with one damaged word, 77% (20th-century prose) and 69% (Abai); false suggestions in 3.9% and 13.2% of untouched sentences |
| RU↔KK parity (`kk_parity`) | 1,516 post pairs from a bilingual corporate channel: no discrepancies in 69.0% of pairs, changed number values in 1.7% |
| Terminology policy (`kk_usage`) | example glossary, 25 pairs: 20 usage decisions and 5 decisions by the author (two disputed cases and three exceptions that keep «объект», «концепция» and «партнёр» international) |

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
