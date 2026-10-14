# Интерактивный лонгрид

Страницы `index.html` (русский), `kk/index.html` и `en/index.html` собираются из Markdown (`docs/longread*.md`) скриптом `build.py`;
оформление и поведение — в `assets/longread.css` и `assets/longread.js`, тексты вставок — в `i18n.py`.

* Основной адрес: <https://webmarka.kz/research/kk-redkollegiya/> (и `kk/`, `en/`). В каждой странице `rel="canonical"` указывает туда же,
  поэтому копия в этом репозитории (GitHub Pages) считается зеркалом.
* Сборка: `python3 -m pip install markdown && python3 docs/longread/build.py`. Плакаты берутся из `docs/img/characters`.
* Страницы самодостаточны: стили, скрипт и рисунки лежат рядом, внешних запросов нет (кроме необязательного шрифта IBM Plex Sans с webmarka.kz).
