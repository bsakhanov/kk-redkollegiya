# Changelog

Формат — [Keep a Changelog](https://keepachangelog.com/ru/1.1.0/), версии — [SemVer](https://semver.org/lang/ru/).

## [0.4.1] — 2026-10-12

### Добавлено
- README на английском (`README.en.md`) и казахском (`README.kk.md`); `README.md` теперь русский, с переключателем языков.
- Руководство пользователя на трёх языках: `docs/USAGE.md`, `docs/USAGE.en.md`, `docs/USAGE.kk.md`.

### Изменено
- В примерах команд пути записаны латиницей (переносимее для оболочек).

## [0.4.0] — 2026-10-12

Первая публичная версия.

### Добавлено
- Лицензия GPL-3.0-or-later (файл `LICENSE`, SPDX-заголовки в исходниках).
- Файл `VERSION` и флаг `--version` у всех утилит.
- `tools/kk_usage.py` — политика терминов «узус корпуса; международное слово — только там, где узус молчит»; `data/term_pairs.yaml`.
- `tools/kk_pairs.py consistency` — согласованность переводов с глоссарием; запись `parity_check` в глоссарий.
- Правило PR06 в `kk_parity` (термин из глоссария) и флаг `--glossary`.
- Двуязычный README, `docs/RULES.md`, `CONTRIBUTING.md`, `CITATION.cff`, `requirements.txt`, `.gitignore`.

### Изменено
- `kk_lint`, правило T02: поле `avoid_action` (`apply` или `suggest`), записи `contested` пропускаются, формы из блока `abbreviations` не дублируются.
- Данные обезличены: пример глоссария и пары терминов не привязаны к конкретной компании.

## Предрелизные итерации

Не отражены в истории git; перечислены для полноты.

- **0.3.0** — `kk_usage`, PR06, расчёт согласованности переводов.
- **0.2.0** — `kk_parity` (числа, даты, шкала, латинские сокращения кириллицей) и `kk_pairs` (параллельный корпус из Telegram, кандидаты в глоссарий); исправлен счётчик NFC в `kk_clean`.
- **0.1.0** — `kk_clean`, `kk_restore`, `kk_lint`, `kk_attest`, глоссарий и тесты.

[0.4.1]: https://github.com/bsakhanov/kk-redkollegiya/compare/v0.4.0...v0.4.1
[0.4.0]: https://github.com/bsakhanov/kk-redkollegiya/releases/tag/v0.4.0
