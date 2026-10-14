# Rule reference

[Русский](RULES.md) · **English** · [Қазақша](RULES.kk.md) · [← README](../README.en.md)

A finding is a JSON object: `{id, stage, zone, layer, severity, rule, quote, action, edit, note}`. redkollegiya's `apply.py` reads `stage`, `zone`,
`severity`, `quote`, `action` and `edit`; it skips the other fields. `quote` is extended until it is unique in the text (anchoring is verbatim),
`edit` is the whole quote with the replacement already made. The text of `note` is produced in Russian.

- `severity`: `blocker` — do not publish; `fix` — applied to the text; `author_choice` — not applied, goes to the author.
- `action`: `apply` — apply `edit`; `suggest` — offer `edit` to the author; `flag` — there is no replacement.

## kk_lint

| Code | Rule | Zone | Default severity / action |
| --- | --- | --- | --- |
| H01 | `mixed_script` — Latin look-alike letters inside Cyrillic words and the other way round; Roman numerals («IV», «XVIIIғ.») and «IT» are not defects | hygiene | fix / apply; unresolved — author_choice / flag |
| H02 | `schwa` — «ə» for «ә», «ӓ ӧ ӱ» for «ә ө ү» | hygiene | fix / apply |
| H03 | `combining` — decomposed diacritics (NFC) | hygiene | fix / apply |
| H04 | `control_char` — control characters in the text | hygiene | fix / flag (run `kk_clean`) |
| S01 | `restore` — a word without Kazakh letters: a suggestion of the character model (margin Δ ≥ 2) confirmed by the dictionary; an unconfirmed one is shown only at Δ ≥ 12; words with the letters «э», «ц», «щ», «ъ», «ь», «ё», «ф», «в», «ч», «ю», «я» are skipped as loanwords («эскиз») | norm | author_choice / suggest; with `--auto-restore`, a dictionary word and Δ ≥ 6 — fix / apply |
| T01 | `ru_abbrev` — РК, ТОО, АО, ИП instead of ҚР, ЖШС, АҚ, ЖК (the glossary's `abbreviations` block) | terms | fix / apply; with an affix after a hyphen — author_choice / suggest |
| T02 | `glossary_avoid` — forms forbidden by the glossary's `avoid` field; it does not fire inside names («НИИ проект», a «…» quote with two capitalized words) or in contexts listed in `avoid_exclude` | terms | fix / apply or author_choice / suggest (the `avoid_action` field); with an affix — author_choice / flag; an entry without `kk` — fix / flag; `contested` entries are skipped |
| P01 | `punct_junk` — a space before a mark, doubled marks, a double space; mark junctions (the period of an abbreviation — «қ.,», «т.б.,» — is not a junction) | typography | fix / apply; junctions — author_choice / flag |
| P02 | `lower_after_dot` — a lowercase letter after a period (abbreviations and initials are protected) | norm | author_choice / flag |
| P03 | `quotes` — straight quotes; unbalanced «» quotes in a paragraph | typography | fix / flag |
| P04 | `empty_brackets` — empty brackets and quotes | typography | fix / flag |
| P05 | `number_affix` — a number and an affix without a hyphen («5ке») | norm | author_choice / suggest |
| C01 | `currency` — a symbol and a word for money in one document | norm | author_choice / flag |
| J01 | `placeholders` (ini profile) — placeholders and markup differ from the source string | parity | blocker / flag |
| J02 | `missing_key` (ini profile) — a key of the source file is not translated | parity | fix / flag |
| J03 | `ini_syntax` (ini profile) — a line does not parse as `KEY="value"` | parity | fix / flag |

`kk_lint.py` exit code: 0 — fine, 1 — input error, 2 — a `blocker` finding exists.

## kk_parity

Comparison goes paragraph by paragraph (blocks separated by a blank line); when the paragraph counts differ, numbers are compared across the whole document.
Numbers are normalized: «6 мың» = «6000», «1,5 млрд» = «1 500 000 000», «12 желтоқсан» = «12 декабря» = «12.12.2025», two-digit years;
addresses without a scheme are dropped; Latin abbreviations typed with Cyrillic look-alikes («ІРО») count as «IPO».

| Code | Rule | Zone | Severity / action |
| --- | --- | --- | --- |
| PR01 | `paragraphs` — the paragraph counts differ | parity | author_choice / flag |
| PR02 | `number_changed` — equal numbers lost and added in a paragraph («15,3» became «15,8») | facts | blocker / flag |
| PR03 | `number_lost` — a number of the original is not found in the Kazakh version (perhaps spelled out in words) | parity | fix / flag |
| PR04 | `number_extra` — extra numbers in the Kazakh version | parity | author_choice / flag |
| PR05 | `latin_lost` — Latin names and abbreviations are lost | parity | fix / flag |
| PR06 | `term_mismatch` — the original has a glossary concept but the chosen Kazakh form is absent (only with `--glossary`, only for entries with `status: usage` whose `parity_check` is not `false`) | terms | author_choice / flag |

## Zones and layers

The `zone` field says what kind of finding it is; the `layer` field says which named layer it belongs to (see the [README](../README.en.md#layers-and-their-names)).

| Zone | Layer (`layer`) | Name |
| --- | --- | --- |
| `hygiene`, `typography` | `altynsarin` | Altynsarin |
| `parity`, `facts` | `valikhanov` | Valikhanov |
| `terms` | `shakarim` | Shakarim |
| `norm` | `baitursynov` | Baitursynov |

The layers `auezov` (meaning and living speech) and `slopotron-kk` (traces of machine writing) are reserved for future passes; the summaries of `kk_lint` and `kk_parity` show finding counts per layer.

## Glossary

Entry fields: `key`, `ru`, `kk` (the form we write), `avoid` (forbidden forms), `avoid_action` (`apply` by default, or `suggest`), `avoid_exclude` (regular expressions of contexts where an `avoid` form is allowed: «санитарлық торап», «проектор»),
`status` (`usage`, `silent`, `contested`; without `status` — the author's decision), `kk_re` and `parity_ru` (regular expressions for PR06),
`evidence` (frequencies and shares), `consistency` and `parity_check` (translation consistency, see `kk_pairs.py consistency`), `note`.
