# Участие / Contributing

**Русский.** Замечания и pull request приветствуются.

- Перед PR запустите `sh tests/run_tests.sh` (самопроверки без внешних данных); с `APPLY=/путь/к/apply.py` проверяется и связка с redkollegiya.
- Новое правило детектора: код в `docs/RULES.md`, самопроверка в `_selftest()` соответствующего скрипта, уровень и действие по умолчанию с обоснованием.
- Не прикладывайте охраняемые тексты, корпуса и обученные модели; для образцов дефектов достаточно коротких вымышленных фраз.
- Особенно нужны: проверка носителями казахского языка, образцы дефектов (кодировки, омоглифы), профили регистра, интеграция морфоанализатора.
- Версионирование — SemVer; изменения записываются в `CHANGELOG.md`.

**English.** Issues and pull requests are welcome. Run `sh tests/run_tests.sh` before a PR; add a self-test and a rule entry in `docs/RULES.md`
for every new detector; do not attach copyrighted texts, corpora or trained models. Reviews by native speakers are especially valuable.

## Выпуск релиза / Releasing

1. Обновите `VERSION`, `CITATION.cff`, `CHANGELOG.md` и версию в бейджах README.
2. Закоммитьте, поставьте тег `vX.Y.Z` и отправьте его вместе с веткой `main`.
3. Опубликуйте релиз на GitHub: рабочий процесс `release-assets` сам приложит архив `kk-redkollegiya-X.Y.Z.zip` и файл с контрольной суммой.

*English.* Update `VERSION`, `CITATION.cff`, `CHANGELOG.md` and the README badges; commit, tag `vX.Y.Z` and push it together with `main`; publish the GitHub release. The `release-assets` workflow attaches `kk-redkollegiya-X.Y.Z.zip` and its checksum by itself.
