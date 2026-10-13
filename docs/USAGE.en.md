# User guide

[Русский](USAGE.md) · **English** · [Қазақша](USAGE.kk.md) · [← README](../README.en.md)

The guide goes from installation to five typical tasks. Rule codes and glossary fields are in [RULES.en.md](RULES.en.md).

## 1. Requirements

- Python 3.8 or newer.
- `pip install -r requirements.txt` installs `spylls` (the dictionary engine) and `pyyaml` (glossaries and lists).
- The hunspell-kk dictionary. `sh tools/fetch_hunspell_kk.sh` puts `kk_KZ.aff` and `kk_KZ.dic` into `data/hunspell/`. The script does not run on
  Windows: download the `hunspell-kk` package (the `.deb` address is inside the script), extract `data.tar.xz` from it and copy both files from
  `usr/share/hunspell/` into `data/hunspell/`. Without the dictionary, alphabet cleanup, typography and number checks still work; word checks do not.
- Texts in UTF-8. Extract text from a PDF with `pdftotext -enc UTF-8 book.pdf book.txt`, from an EPUB with pandoc.
- Optionally `apply.py` from [redkollegiya](https://github.com/beaverbeard/redkollegiya): it applies the findings to the text by verbatim quote.

Check the installation: `sh tests/run_tests.sh` must finish without errors, and `python3 tools/kk_lint.py --version` must print the version.

## 2. Reading the results

`kk_lint.py` and `kk_parity.py` write findings as JSON (`--json file`). One finding (the text of the `note` field is produced in Russian):

```json
{"id": "T01-0001", "stage": "kk_lint", "zone": "terms", "severity": "fix",
 "rule": "T01 ru_abbrev", "quote": "РК", "action": "apply", "edit": "ҚР",
 "note": "в казахском тексте «ҚР» вместо «РК»"}
```

- `quote` is a verbatim fragment of the text, extended until it is unique; `edit` is that fragment with the replacement already made.
- `severity`: `blocker` — do not publish; `fix` — applied to the text; `author_choice` — a human decides.
- `action`: `apply` — apply the edit; `suggest` — offer the replacement; `flag` — there is no replacement.
- `kk_lint.py` exit code: 0 — fine, 1 — input error, 2 — a `blocker` finding exists.

Findings are applied by redkollegiya's `apply.py`: it applies findings with the `apply` action and leaves the rest to the author (the `to_author`
list in its report). The scripts themselves never rewrite the text.

## 3. Task A. Clean up a book or a PDF export

```bash
python3 tools/kk_clean.py books/*.txt -o clean/ --dict data/hunspell/kk_KZ --journal journal.json
```

For every file a line like `book.txt: legacy:494672, homoglyph:10` is printed: the step and the number of repairs. `journal.json` keeps
the counters and "before → after" examples.

| Step | What it repairs |
| --- | --- |
| `nfc` | decomposed characters ("й", "ё" stored as two marks) |
| `legacy` | legacy Kazakh font encoding, detected automatically (the word «мектеп» reads as «ìåêòåï») |
| `schwa` | Latin «ə» for «ә»; «ӓ ӧ ӱ» for «ә ө ү» |
| `substitute` | control and Latin characters standing for Kazakh letters; needs the dictionary. A `substitute_guess` entry means the dictionary did not confirm the word: review those in the journal |
| `homoglyph` | Latin look-alikes inside Cyrillic words («қорықca») and the other way round («ІSBN»); `homoglyph_ambiguous` — not resolved |
| `dehyphenate` | only with `--dehyphenate`: joins a word split by a line-end hyphen when the result is in the dictionary |

`--check` writes nothing and only shows the journal. `--no-legacy` turns off legacy-encoding detection.
Clean bilingual editions (Kazakh and Russian text mixed) of Russian lines separately before any counting.

## 4. Task B. Check an article or a web page

```bash
python3 tools/kk_lint.py clean/article.txt --dict data/hunspell/kk_KZ --glossary data/glossary.yaml \
        --json findings.json --unknown-tsv unknown.tsv
python3 /path/to/apply.py --text clean/article.txt --findings findings.json --out article_v2.txt --report report.json
```

1. The first command prints a summary: how many findings per rule and severity.
2. The second applies the `fix` findings with the `apply` action and writes a report: `applied` — what was applied, `to_author` — what awaits a decision.
3. Review the `suggest` and `flag` findings in `findings.json` (fields `quote`, `edit`, `note`) and correct the text by hand.

**Words outside the dictionary.** `unknown.tsv` (word and count) lists candidates for a whitelist. Put the correct words (names, terms) one per line into
`whitelist.txt` and run with `--whitelist whitelist.txt`: the noise drops.

**Restoring Kazakh letters.** If the text has «Казакстан» instead of «Қазақстан», train the model on your own clean corpus and plug it in:

```bash
python3 tools/kk_restore.py train clean/*.txt -o lm.json.gz
python3 tools/kk_lint.py text.txt --dict data/hunspell/kk_KZ --lm lm.json.gz --json findings.json
```

Rule S01 proposes «Казакстан» → «Қазақстан» as a `suggest`. The `--auto-restore` flag applies high-confidence suggestions: use it only for text typed
entirely without Kazakh letters. Capitalized words inside a sentence are skipped as names; `--names` checks them too. Check the model on your data with
`kk_restore.py eval --lm lm.json.gz --test book.txt`.

**Choosing rules:** `--only H01,H02` runs only the listed ones, `--skip P02` skips the listed ones.

## 5. Task C. A Joomla language pack (.ini)

```bash
python3 tools/kk_lint.py kk-KZ.com_example.ini --profile ini --source en-GB.com_example.ini \
        --dict data/hunspell/kk_KZ --json findings.json
```

In the `ini` profile only the quoted values are checked: placeholders (`%s`, `%1$s`, `{name}`), tags and entities (`&nbsp;`) are left alone.
A lost or extra placeholder is a `blocker` (J01) with exit code 2; an untranslated key is J02; a line that is not `KEY="value"` is J03.
This makes a build check:

```sh
for f in language/kk-KZ/*.ini; do
  src="language/en-GB/$(basename "$f" | sed 's/^kk-KZ/en-GB/')"
  python3 tools/kk_lint.py "$f" --profile ini --source "$src" --dict data/hunspell/kk_KZ || exit 1
done
```

## 6. Task D. Compare a translation with the Russian original

```bash
python3 tools/kk_parity.py --ru original.md --kk kazakh.md --glossary data/glossary.yaml --json parity.json
```

Paragraphs in both files are separated by a blank line. If the paragraph counts differ, that is PR01, and numbers are compared across the whole document.

| Code | Meaning | What to do |
| --- | --- | --- |
| PR02 (`blocker`) | equal numbers lost and added in a paragraph: "15,3" became "15,8" | check against the original, fix |
| PR03 | a number of the original is not found in the Kazakh version | check: it may be spelled out in words |
| PR04 | an extra number in the Kazakh version | check: it may be a unit conversion |
| PR05 | a Latin name or abbreviation is lost | restore it or replace it deliberately |
| PR06 | the original has a glossary concept but the chosen Kazakh form is absent | the author decides (only with `--glossary`) |

Numbers are normalized: «6 мың» = «6000», «1,5 млрд» = «1 500 000 000», «12 желтоқсан» = «12 декабря» = «12.12.2025». Numbers spelled out in words are not compared.

## 7. Task E. Terms by corpus usage

The rule: **corpus usage first; the international word only where usage is silent**. Prepare a groups file whose keys are corpus groups;
paths are relative to the file itself:

```yaml
# groups.yaml
corporate:
  label: corporate usage
  files: [corpus/news_kk.txt, corpus/channel_kk.txt]
```

```bash
# how often each form occurs (contexts help tell senses apart)
python3 tools/kk_attest.py --groups groups.yaml --terms data/terms_variants.yaml --context 3

# decisions per pair; the author's decisions in the glossary are preserved
python3 tools/kk_usage.py --groups groups.yaml --group corporate --pairs data/term_pairs.yaml \
        --merge data/glossary.yaml --out data/glossary.yaml --tsv decisions.tsv
```

Add your own pair to `data/term_pairs.yaml`: `a` is the international form in Kazakh text, `b` the Kazakh one, `re` a regular expression
for lowercase letters, `parity_ru` how the concept looks in the Russian original:

```yaml
- {key: well, ru: скважина, a: {label: скважина, re: "скважин\\w*"}, b: {label: ұңғыма, re: "ұңғыма\\w*"}, parity_ru: "скважин\\w*"}
```

Entry statuses: `usage` — one form has at least 70% of occurrences with ten or more in total; `silent` — fewer than ten occurrences, the international form is taken;
`contested` — shares between 30% and 70%, the author decides. To lock your own decision, remove `status` or write `status: author`: such an entry is not overwritten
by `--merge`. The linter applies decisions as suggestions (`author_choice`).

**A corpus from a bilingual Telegram channel.** In Telegram Desktop choose "Export chat history" in JSON format (the file `result.json`):

```bash
python3 tools/kk_pairs.py build result.json -o pairs.jsonl                 # "Kazakh post — Russian post" pairs
python3 tools/kk_pairs.py align pairs.jsonl -o candidates.tsv              # candidates for a bilingual glossary
python3 tools/kk_pairs.py consistency pairs.jsonl --glossary data/glossary.yaml \
        --term-pairs data/term_pairs.yaml -o consistency.tsv --write       # how closely translations follow the glossary
```

`candidates.tsv` is co-occurrence statistics, not a dictionary: a human decides on each pair. `--write` stores the `consistency` and `parity_check` fields
in the glossary; the PR06 check is enabled only for entries whose consistency is at least 85%.

## 8. Troubleshooting

| Symptom | What to do |
| --- | --- |
| a PyYAML message or `spylls` is not found | `pip install -r requirements.txt` |
| "dictionary not loaded" | give `--dict` without an extension: `data/hunspell/kk_KZ`; the `.aff` and `.dic` files must sit next to each other |
| "looks like a legacy encoding" | run the text through `kk_clean.py` first |
| too many words outside the dictionary | add correct words to `--whitelist`; the dictionary is old and does not know new words |
| `apply.py` handed a finding to the author: "quote is not unique" or "not found" | edit by hand using the `quote` field; after edits, re-run the findings against the new text |
| Latin script in Kazakh text is not corrected | by design: the toolkit is built for the Cyrillic script, Latin words are left alone |
| the text is not UTF-8 | re-encode: `iconv -f cp1251 -t utf-8 in.txt > out.txt` |

Bugs and requests go to [Issues](https://github.com/bsakhanov/kk-redkollegiya/issues).
