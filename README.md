# IriSkating — сайт для записи на курсы

Сайт для записи на занятия по фигурному катанию: лендинг (HTML/CSS/JS, без сборки)
+ небольшой FastAPI-бэкенд (заявки в SQLite, авторизация админа). Тёмная тема,
один тренер (Irene), вкладка **Coach**, запись через модальное окно.

## Что внутри

```
├── index.html        # вся разметка лендинга (тексты меняются через data-i18n)
├── admin.html        # админка: вход + таблица заявок
├── css/              # styles.css — тема лендинга; admin.css — админка
├── js/               # i18n.js (словарь EN/RU/中文/FR), slideshow.js, text-slider.js, main.js, admin.js
├── assets/           # favicon + media/ (фото/видео для слайдшоу, сейчас заглушки)
├── server/           # FastAPI: статика + API заявок с авторизацией (см. server/requirements.txt)
│                     #   + метрики посещений по странам (server/metrics.py, /metrics)
├── tests/            # pytest для API и метрик
├── Dockerfile        # образ: статика + API в одном контейнере (uvicorn :8000)
├── docker-compose.yml # web + prometheus + grafana в сети стека бота (iriskating_default)
└── deploy/           # Caddyfile для сервера + DEPLOY.md; prometheus.yml и
                      #   провижининг Grafana (datasource + дашборд)
```

## Админка и заявки

Форма записи отправляет заявки в API (`POST /api/bookings`), они хранятся в
SQLite (`data/site.db`). Если API недоступен (локальный просмотр без бэкенда),
заявка сохраняется в localStorage браузера.

- `/admin` — вход по `ADMIN_USERNAME` + паролю (в `ADMIN_PASSWORD_HASH` хранится
  только PBKDF2-хеш). Внутри — таблица заявок: подтвердить ✓ / отменить ✕ / вернуть ↺,
  плюс статистика посещений по странам (24ч / 7д, конверсия) — данные берёт
  из Prometheus (`/api/stats`; Prometheus недоступен — секция это покажет).
- Хеш пароля: `python3 -m server.hash_password 'Пароль'`
- Секреты — только в `.env` (образец: `.env.example`).

## Запуск локально

Статика без бэкенда — просто открыть `index.html` (заявки уйдут в localStorage).
Полный вариант с API:

```bash
python3 -m venv .venv && .venv/bin/pip install -r server/requirements.txt
.venv/bin/uvicorn server.app:app --reload      # http://127.0.0.1:8000
```

Админка: http://127.0.0.1:8000/admin (логин/пароль из `.env`, для локальной
отладки поставьте `COOKIE_SECURE=false`).

Метрики: http://127.0.0.1:8000/metrics — Prometheus-формат.

## Метрики посещений по регионам

Каждое посещение лендинга (`/`, `/index.html`) и каждая заявка считаются
по стране посетителя. Страна берётся из заголовка **`CF-IPCountry`**, который
Cloudflare добавляет ко всем запросам к origin (основной домен идёт через CF).
Нет заголовка (локальный запуск, прямой заход) — метрика с кодом `XX`.
`/admin` и статика (CSS/JS/картинки) посещениями не считаются.

Метрики (эндпоинт `/metrics`, наружу закрыт Caddy — только Prometheus внутри
docker-сети):

- `iriskating_site_visits_total{country, page}` — посещения лендинга;
- `iriskating_booking_requests_total{country, program}` — заявки (конверсия).

Стек в `docker-compose.yml`: **prometheus** (скрейпит `web:8000`, 15s,
retention 30d) → **grafana** (источник и дашборд «IriSkating · Site visits
by region» провижинятся автоматически из `deploy/grafana/`). Графана слушает
только `127.0.0.1:3000` — на сервере доступ через SSH-туннель
(см. [deploy/DEPLOY.md](deploy/DEPLOY.md), §9). Креды админа Grafana —
`GF_SECURITY_ADMIN_USER` / `GF_SECURITY_ADMIN_PASSWORD` в `.env`.

## Деплой на сервер бота

Пошагово — [deploy/DEPLOY.md](deploy/DEPLOY.md): сайт встаёт рядом с ботом
(`www.149.33.58.213.sslip.io` → `web:8000`), HTTPS терминирует Caddy из стека бота.

## Языки

Переключатель в шапке: 🇬🇧 English · 🇷🇺 Русский · 🇨🇳 中文 · 🇫🇷 Français.
Выбор сохраняется в `localStorage` (`iriskating_lang`). Чтобы добавить язык —
добавьте объект в `I18N` в `js/i18n.js` и `<li data-lang="…">` в `index.html`.

## Слайдшоу на главной

Хиро-панель — слайдшоу из фото и видео с тренировок (на льду и вне льда).
Свои материалы: положите файлы в `assets/media/` и отредактируйте массив
`HERO_MEDIA` в начале `js/slideshow.js`:

```js
{ type: "image", src: "assets/media/foto-1.jpg", tag: { en: "On-ice", ru: "На льду" } },
{ type: "video", src: "assets/media/video-1.mp4", poster: "assets/media/poster.jpg",
  tag: { en: "On-ice · video", ru: "На льду · видео" } },
```

Видео (mp4, H.264) играет без звука, пока его слайд активен; по окончании
листается дальше. Фото меняются каждые 5 секунд. Сейчас стоят стилизованные
заглушки-«скрины Zoom» (`assets/media/*.svg`) — замените их на реальные материалы.

## Запись (Book)

Прототип: кнопки `data-book` открывают модалку с формой; заявка сохраняется
локально (`localStorage`, ключ `iriskating_bookings`) и показывается экран успеха.
Дальше форму можно подключить к Telegram Bot API (заявки владельцу) или мини-бэкенду.

## Заглушки, которые надо заменить на реальные

- **Тренер**: био и достижения тренера Ирены заполнены; фото пока SVG-плейсхолдер — замените на реальное в секции `#coach` (`index.html`), тексты — ключи `coach.*` / `spec.*` в `js/i18n.js`.

- **Программы**: 4 онлайн-формата (`lesson1..4`) и спецпредложение (`offer.*`) — цены и описания правятся в `index.html` + ключах в `js/i18n.js`.
- **События и новости**: `event1..3`, `news1..2` — статичные примеры.
- **Контакты**: Telegram / Instagram / email / адрес катка (`contact.*`) — сейчас кнопки показывают toast «прототип» (`data-proto`).
- **Sign in / Sign up**: прототип (toast).

## Хостинг

Статика: VPS (nginx / Caddy), GitHub Pages, Netlify, Cloudflare Pages — деплой = копирование папки.

**Кеш статики**: CSS/JS подключены с версионным параметром (`styles.css?v=6`) —
после изменений CSS/JS поднимите `?v=` в `index.html` / `admin.html`, чтобы у
посетителей точно обновился кеш (страховка от агрессивных прокси/кешей).
