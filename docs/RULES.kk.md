# Ережелер анықтамасы

[Русский](RULES.md) · [English](RULES.en.md) · **Қазақша** · [← README](../README.kk.md)

Ескерту (finding) — JSON нысаны: `{id, stage, zone, severity, rule, quote, action, edit, note}`. redkollegiya-дағы `apply.py` `stage`, `zone`, `severity`, `quote`,
`action`, `edit` өрістерін оқиды; қалғандарын өткізіп жібереді. `quote` мәтінде бірегей болғанша кеңейтіледі (іздеу сөзбе-сөз жүреді), `edit` — ауыстыру
енгізілген тұтас дәйексөз. `note` мәтінін құрал орысша жазады.

- `severity`: `blocker` — жариялауға болмайды; `fix` — мәтінге енгізіледі; `author_choice` — мәтінге енгізілмейді, авторға беріледі.
- `action`: `apply` — `edit` енгізу; `suggest` — `edit` үлгісін авторға ұсыну; `flag` — ауыстыру жоқ.

## kk_lint

| Код | Ереже | Аймақ | Әдепкі деңгей / әрекет |
| --- | --- | --- | --- |
| H01 | `mixed_script` — кириллицамен жазылған сөздердің ішіндегі ұқсас латын әріптері және керісінше | hygiene | fix / apply; шешілмегені — author_choice / flag |
| H02 | `schwa` — «ә» орнына «ə», «ә ө ү» орнына «ӓ ӧ ӱ» | hygiene | fix / apply |
| H03 | `combining` — бөлшектенген диакритикалық белгілер (NFC) | hygiene | fix / apply |
| H04 | `control_char` — мәтіндегі басқарушы таңбалар | hygiene | fix / flag (`kk_clean` арқылы өткізу керек) |
| S01 | `restore` — қазақ әріптері жоқ сөз: символдық модельдің сөздік растаған ұсынысы (айырма Δ ≥ 2); растамаған ұсыныс тек Δ ≥ 12 болғанда көрсетіледі | norm | author_choice / suggest; `--auto-restore` болса, сөз сөздікте бар және Δ ≥ 6 болса — fix / apply |
| T01 | `ru_abbrev` — ҚР, ЖШС, АҚ, ЖК орнына РК, ТОО, АО, ИП (глоссарийдің `abbreviations` блогы) | terms | fix / apply; сызықшадан кейінгі жалғау болса — author_choice / suggest |
| T02 | `glossary_avoid` — глоссарийдің `avoid` өрісіндегі тыйым салынған формалар | terms | fix / apply немесе author_choice / suggest (`avoid_action` өрісі); жалғау болса — author_choice / flag; `kk` өрісі жоқ жазба — fix / flag; `contested` жазбалары өткізіліп жіберіледі |
| P01 | `punct_junk` — тыныс белгісінің алдындағы бос орын, қосарланған белгілер, қос бос орын; белгілер түйіскен жерлер | typography | fix / apply; түйіскен жерлер — author_choice / flag |
| P02 | `lower_after_dot` — нүктеден кейінгі кіші әріп (қысқартулар мен инициалдар қорғалған) | norm | author_choice / flag |
| P03 | `quotes` — тік тырнақшалар; абзацтағы жұпталмаған «» тырнақшалары | typography | fix / flag |
| P04 | `empty_brackets` — бос жақшалар мен тырнақшалар | typography | fix / flag |
| P05 | `number_affix` — санның жалғауы сызықшасыз жазылған («5ке») | norm | author_choice / suggest |
| C01 | `currency` — бір құжатта ақша үшін таңба мен сөз қатар жүр | norm | author_choice / flag |
| J01 | `placeholders` (ini профилі) — толтырғыштар мен тегтер бастапқы жолмен сәйкес келмейді | parity | blocker / flag |
| J02 | `missing_key` (ini профилі) — бастапқы файлдың кілті аударылмаған | parity | fix / flag |
| J03 | `ini_syntax` (ini профилі) — жол `KEY="мән"` ретінде оқылмайды | parity | fix / flag |

`kk_lint.py` қайтару коды: 0 — жақсы, 1 — енгізу қатесі, 2 — `blocker` деңгейіндегі ескерту бар.

## kk_parity

Салыстыру абзацтар бойынша жүреді (бос жолмен бөлінген блоктар); абзац саны сәйкес келмесе, сандар бүкіл құжат бойынша салыстырылады.
Сандар бір түрге келтіріледі: «6 мың» = «6000», «1,5 млрд» = «1 500 000 000», «12 желтоқсан» = «12 декабря» = «12.12.2025», екі таңбалы жыл;
схемасыз мекенжайлар тасталады; кириллицадағы ұқсас әріптермен терілген латын қысқартулары («ІРО») «IPO» деп есептеледі.

| Код | Ереже | Аймақ | Деңгей / әрекет |
| --- | --- | --- | --- |
| PR01 | `paragraphs` — абзац саны сәйкес келмейді | parity | author_choice / flag |
| PR02 | `number_changed` — абзацта бірдей санда сан жоғалып, қосылған («15,3» орнына «15,8» шықты) | facts | blocker / flag |
| PR03 | `number_lost` — түпнұсқадағы сан қазақша нұсқада табылмады (мүмкін, сөзбен жазылған) | parity | fix / flag |
| PR04 | `number_extra` — қазақша нұсқада артық сандар | parity | author_choice / flag |
| PR05 | `latin_lost` — латын атаулары мен қысқартулары жоғалды | parity | fix / flag |
| PR06 | `term_mismatch` — түпнұсқада глоссарий ұғымы бар, ал таңдалған қазақ формасы жоқ (тек `--glossary` болса, тек `status: usage` және `parity_check` мәні `false` емес жазбалар үшін) | terms | author_choice / flag |

## Глоссарий

Жазба өрістері: `key`, `ru`, `kk` (біз жазатын форма), `avoid` (тыйым салынған формалар), `avoid_action` (әдепкіде `apply`, немесе `suggest`),
`status` (`usage`, `silent`, `contested`; `status` жоқ болса — автордың шешімі), `kk_re` және `parity_ru` (PR06 үшін тұрақты өрнектер),
`evidence` (жиіліктер мен үлестер), `consistency` және `parity_check` (аудармалардың үйлесімділігі, `kk_pairs.py consistency` қараңыз), `note`.
