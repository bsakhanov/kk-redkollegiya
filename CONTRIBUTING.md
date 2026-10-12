# Участие / Contributing

**Русский.** Замечания и pull request приветствуются.

- Перед PR запустите `sh tests/run_tests.sh` (самопроверки без внешних данных); с `APPLY=/путь/к/apply.py` проверяется и связка с redkollegiya.
- Новое правило детектора: код в `docs/RULES.md`, самопроверка в `_selftest()` соответствующего скрипта, уровень и действие по умолчанию с обоснованием.
- Не прикладывайте охраняемые тексты, корпуса и обученные модели; для образцов дефектов достаточно коротких вымышленных фраз.
- Особенно нужны: проверка носителями казахского языка, образцы дефектов (кодировки, омоглифы), профили регистра, интеграция морфоанализатора.
- Версионирование — SemVer; изменения записываются в `CHANGELOG.md`.

**English.** Issues and pull requests are welcome. Run `sh tests/run_tests.sh` before a PR; add a self-test and a rule entry in `docs/RULES.md`
for every new detector; do not attach copyrighted texts, corpora or trained models. Reviews by native speakers are especially valuable.
