# Деплой сайта IriSkating на VPS бота (149.33.58.213)

Сайт живёт в одной docker-сети со стеком бота: Caddy из стека бота терминирует
HTTPS и проксирует `www.149.33.58.213.sslip.io` на сервис `web:8000`.
Сам бот при этом не затрагивается — правка только в его `Caddyfile`.

Итоговая схема:

```
internet ──► caddy (80/443, из стека бота)
              ├── 149.33.58.213.sslip.io   → bot:8080   (медиа для Instagram)
              └── www.149.33.58.213.sslip.io → web:8000 (сайт: статика + /api)
```

## 1. Код на сервере

```bash
ssh root@149.33.58.213
git clone git@github.com:BetsonWick/IriSkatingWeb.git /opt/iriskating-web
# либо rsync с Mac:
# rsync -av --exclude '.git' --exclude '.venv' --exclude 'data' --exclude '.env' \
#   ~/iriskating/IriSkatingWeb/ root@149.33.58.213:/opt/iriskating-web/
```

## 2. .env (секреты в git не попадают)

```bash
cd /opt/iriskating-web
cp .env.example .env && chmod 600 .env && nano .env
```

Нужно заполнить:

- `ADMIN_PASSWORD_HASH` — хеш пароля админа (генерация — ниже, §3)
- `SESSION_SECRET` — ключ подписи cookie: `openssl rand -hex 32`
- `TELEGRAM_BOT_TOKEN` / `TELEGRAM_ADMIN_CHAT_IDS` — уведомления о заявках:
  токен того же бота (из `/opt/iriskating/.env`), получатели — ID из
  `ADMIN_TELEGRAM_IDS` бота через запятую. Пусто — заявки сохраняются без
  уведомления.
- `GF_SECURITY_ADMIN_USER` / `GF_SECURITY_ADMIN_PASSWORD` — вход в Grafana
  (`openssl rand -hex 16` для пароля; Grafana читает только `GF_*`).

`ADMIN_USERNAME` по умолчанию `iren` — можно поменять.

## 3. Запуск (требуется работающий стек бота)

Сеть `iriskating_default` создаёт compose-стек бота — он должен быть запущен
(`docker network ls | grep iriskating`). Затем:

```bash
mkdir -p data && chown 1000:1000 data    # uid=1000 — пользователь web в контейнере
docker compose up -d --build             # поднимает web + prometheus + grafana
docker compose logs -f web               # ждём "Uvicorn running on ..."
```

Проверка API: `curl -s https://www.149.33.58.213.sslip.io/api/me` → `{"detail":"Not authenticated"}` (401 — это норма).

## 4. Подключить домен в Caddy (стек бота)

В `/opt/iriskating/Caddyfile` добавить блок (готовый файл — `deploy/Caddyfile`):

```
www.149.33.58.213.sslip.io {
	reverse_proxy web:8000
}
```

Перезапустить caddy:

```bash
docker compose -f /opt/iriskating/docker-compose.yml restart caddy
```

Первый заход на `https://www.149.33.58.213.sslip.io` — Caddy сам выпустит
Let's Encrypt сертификат (до минуты).

> Основной домен `iriskating.com` / `www.iriskating.com` обслуживается через
> Cloudflare (прокси, Full strict, real IP через `trusted_proxies` в Caddyfile).
> Пошаговая настройка и чек-лист — `docs/cloudflare.md` в репозитории бота.

## 5. Админка

- `https://www.149.33.58.213.sslip.io/admin` — вход по `ADMIN_USERNAME`/паролю,
  дальше таблица заявок: подтверждение ✓, отмена ✕, возврат в новые ↺.
- Кнопки **Sign in / Sign up** в шапке сайта ведут на `/admin`.

## 6. Обновление сайта

```bash
cd /opt/iriskating-web
git pull    # или свежий rsync
docker compose up -d --build
docker builder prune -f && docker image prune -f
```

## 7. Бэкап заявок

Заявки лежат в `/opt/iriskating-web/data/site.db` (SQLite, переживает пересборку).
В cron рядом с бэкапом бота:

```
45 4 * * * sqlite3 /opt/iriskating-web/data/site.db ".backup /opt/iriskating-web/data/backups/site-$(date +\%F).db"
```

(и по желанию `-mtime +30 -delete` для старых копий).

## 8. Безопасность

- Пароль админа существует только в виде PBKDF2-хеша в `.env` (chmod 600).
- Сессионная cookie: HttpOnly + SameSite=Lax + Secure, подпись HMAC-SHA256.
- Лимиты: логин 10 попыток / 5 мин с одного IP, заявки 30 / 10 мин.
- UFW на сервере остаётся как для бота: снаружи только 22/80/443.
- Смена пароля: новый хеш в `.env` → `docker compose up -d` (пересоздаёт контейнер).
- `/metrics` сайта наружу закрыт: Caddy отвечает 404 (см. §9), эндпоинт
  доступен только Prometheus'у внутри docker-сети. Оговорка: на sslip.io-хосте
  (без Cloudflare) посетитель теоретически может подделать `CF-IPCountry`
  и «переехать»; для основного домена заголовок ставит CF и клиенты его
  подделать не могут.

## 9. Мониторинг: посещения по регионам в Grafana

Посещения и заявки считаются по стране посетителя (заголовок `CF-IPCountry`
от Cloudflare) и отдаются через `/metrics`; Prometheus скрейпит их внутри
docker-сети, Grafana рисует дашборд. Стек: `web` + `prometheus` +
`grafana` в `docker-compose.yml` этого репозитория, бота не затрагивает.

Схема:

```
посетитель ──► Cloudflare (ставит CF-IPCountry) ──► caddy ──► web:8000
                                                 (404 на /metrics)
prometheus (compose) ──скрейп 15s──► web:8000/metrics
grafana (compose) ──► prometheus:9090   [127.0.0.1:3000 снаружи]
```

### Доступ к Grafana (SSH-туннель)

```bash
ssh -L 3000:127.0.0.1:3000 root@149.33.58.213
# затем локально: http://localhost:3000, вход GRAFANA_ADMIN_USER / GRAFANA_ADMIN_PASSWORD
```

Дашборд **IriSkating · Site visits by region** провижинится автоматически
(`deploy/grafana/`): визиты/заявки за 24ч, конверсия, pie по странам,
табличка заявок по странам, темп визитов. Источник данных `prometheus`
тоже провижинится — руками ничего добавлять не нужно.

### Что сделать при первом деплое мониторинга

1. Обновить код сайта (`git pull` / rsync) и `docker compose up -d --build`.
2. **Синхронизировать Caddyfile стека бота** — иначе `/metrics` открыт всему
   интернету через домен сайта:

   ```bash
   cd /opt/iriskating && git pull && docker compose restart caddy
   # в двух блоках сайта должен появиться: respond @webMetrics 404
   ```

3. В `.env` сайта задать `GF_SECURITY_ADMIN_USER` / `GF_SECURITY_ADMIN_PASSWORD`
   и `docker compose up -d` (пересоздаёт grafana).

### Эксплуатация

- Retention Prometheus — 30 дней (`--storage.tsdb.retention.time` в compose),
  данных мало (единицы МБ).
- Данные Grafana — volume `grafana-data`, Prometheus — `prometheus-data`;
  `docker compose down -v` их удалит, не делать без нужды.
- После каждой пересборки — `docker builder prune -f` (правило из AGENTS.md
  бота; на малом диске VPS это критично).
- Опционально можно вынести Grafana на поддомен (`grafana.iriskating.com`):
  A-запись в Cloudflare → блок в Caddyfile с basic-auth или своим прокси —
  сейчас осознанно не делаем, туннеля достаточно.
