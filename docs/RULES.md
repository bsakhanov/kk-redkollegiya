# Справочник правил

**Русский** · [English](RULES.en.md) · [Қазақша](RULES.kk.md) · [← README](../README.md)

Находка — JSON-объект: `{id, stage, zone, layer, severity, rule, quote, action, edit, note}`. `apply.py` из redkollegiya читает
`stage`, `zone`, `severity`, `quote`, `action`, `edit`; остальные поля он пропускает. `quote` расширяется до уникальной в тексте
(якорение дословное), `edit` — вся цитата с уже внесённой заменой.

- `severity`: `blocker` — публиковать нельзя; `fix` — вносится в текст; `author_choice` — в текст не вносится, идёт автору.
- `action`: `apply` — внести `edit`; `suggest` — предложить `edit` автору; `flag` — замены нет.

## kk_lint

| Код | Правило | Зона | Уровень / действие по умолчанию |
| --- | --- | --- | --- |
| H01 | `mixed_script` — латинские буквы-двойники внутри кириллических слов и наоборот | hygiene | fix / apply; неразобранное — author_choice / flag |
| H02 | `schwa` — «ə» вместо «ә», «ӓ ӧ ӱ» вместо «ә ө ү» | hygiene | fix / apply |
| H03 | `combining` — разложенные диакритики (NFC) | hygiene | fix / apply |
| H04 | `control_char` — управляющие символы в тексте | hygiene | fix / flag (прогнать `kk_clean`) |
| S01 | `restore` — слово без казахских букв: подсказка символьной модели (запас Δ ≥ 2), подтверждённая словарём; не подтверждённая — только при Δ ≥ 12 | norm | author_choice / suggest; с `--auto-restore`, словом в словаре и Δ ≥ 6 — fix / apply |
| T01 | `ru_abbrev` — РК, ТОО, АО, ИП вместо ҚР, ЖШС, АҚ, ЖК (блок `abbreviations` глоссария) | terms | fix / apply; с аффиксом после дефиса — author_choice / suggest |
| T02 | `glossary_avoid` — запрещённые формы из поля `avoid` глоссария | terms | fix / apply или author_choice / suggest (поле `avoid_action`); с аффиксом — author_choice / flag; запись без `kk` — fix / flag; записи `contested` пропускаются |
| P01 | `punct_junk` — пробел перед знаком, двойные знаки, двойной пробел; стыки знаков | typography | fix / apply; стыки — author_choice / flag |
| P02 | `lower_after_dot` — строчная после точки (сокращения и инициалы защищены) | norm | author_choice / flag |
| P03 | `quotes` — прямые кавычки; несбалансированные «ёлочки» в абзаце | typography | fix / flag |
| P04 | `empty_brackets` — пустые скобки и кавычки | typography | fix / flag |
| P05 | `number_affix` — число и аффикс без дефиса («5ке») | norm | author_choice / suggest |
| C01 | `currency` — символ и слово для денег в одном документе | norm | author_choice / flag |
| J01 | `placeholders` (профиль ini) — заполнители и разметка не совпадают с исходной строкой | parity | blocker / flag |
| J02 | `missing_key` (профиль ini) — ключ исходного файла не переведён | parity | fix / flag |
| J03 | `ini_syntax` (профиль ini) — строка не разбирается как `KEY="значение"` | parity | fix / flag |

Код возврата `kk_lint.py`: 0 — нормально, 1 — ошибка входа, 2 — есть находка уровня `blocker`.

## kk_parity

Сверка идёт по абзацам (блоки, разделённые пустой строкой); при разном числе абзацев числа сверяются по документу целиком.
Числа приводятся к одному виду: «6 мың» = «6000», «1,5 млрд» = «1 500 000 000», «12 желтоқсан» = «12 декабря» = «12.12.2025», двузначный год,
адреса без схемы отбрасываются; латинские сокращения, набранные кириллическими двойниками («ІРО»), засчитываются как «IPO».

| Код | Правило | Зона | Уровень / действие |
| --- | --- | --- | --- |
| PR01 | `paragraphs` — число абзацев не совпадает | parity | author_choice / flag |
| PR02 | `number_changed` — в абзаце потеряно и добавлено поровну чисел («15,3» стало «15,8») | facts | blocker / flag |
| PR03 | `number_lost` — число оригинала не найдено в казахской версии (возможно, записано словом) | parity | fix / flag |
| PR04 | `number_extra` — лишние числа в казахской версии | parity | author_choice / flag |
| PR05 | `latin_lost` — потеряны латинские имена и сокращения | parity | fix / flag |
| PR06 | `term_mismatch` — в оригинале понятие глоссария, а выбранной казахской формы нет (только с `--glossary`, только для записей `status: usage` с `parity_check` не `false`) | terms | author_choice / flag |

## Зоны и слои

Поле `zone` говорит, какого рода находка; поле `layer` — какому слою, носящему имя, она принадлежит (подробнее — в [README](../README.md#слои-и-их-имена)).

| Зона | Слой (`layer`) | Имя |
| --- | --- | --- |
| `hygiene`, `typography` | `altynsarin` | Алтынсарин |
| `parity`, `facts` | `valikhanov` | Валиханов |
| `terms` | `shakarim` | Шакарим |
| `norm` | `baitursynov` | Байтурсынов |

Слои `auezov` (смысл и живая речь) и `slopotron-kk` (следы машинного письма) закреплены за будущими проходами; сводки `kk_lint` и `kk_parity` показывают число находок по слоям.

## Глоссарий

Поля записи: `key`, `ru`, `kk` (форма, которую пишем), `avoid` (формы под запретом), `avoid_action` (`apply` по умолчанию или `suggest`),
`status` (`usage`, `silent`, `contested`; без `status` — решение автора), `kk_re` и `parity_ru` (регулярные выражения для PR06),
`evidence` (частоты и доли), `consistency` и `parity_check` (согласованность переводов, см. `kk_pairs.py consistency`), `note`.
