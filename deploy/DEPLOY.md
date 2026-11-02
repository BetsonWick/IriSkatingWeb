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

`ADMIN_USERNAME` по умолчанию `iren` — можно поменять.

## 3. Запуск (требуется работающий стек бота)

Сеть `iriskating_default` создаёт compose-стек бота — он должен быть запущен
(`docker network ls | grep iriskating`). Затем:

```bash
mkdir -p data && chown 1000:1000 data    # uid=1000 — пользователь web в контейнере
docker compose up -d --build
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
