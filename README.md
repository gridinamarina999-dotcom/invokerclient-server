# InvokerClient

Сайт на Flask: регистрация, подтверждение почты, админ-панель после входа.

## Локально

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

## Railway

1. Залей репозиторий на GitHub и подключи в Railway.
2. Добавь плагин **PostgreSQL** (переменная `DATABASE_URL` появится сама).
3. В **Variables** задай:

| Variable | Пример |
|----------|--------|
| `SECRET_KEY` | длинная случайная строка |
| `ADMIN_EMAIL` | твоя почта админа |
| `ADMIN_PASSWORD` | пароль админа |
| `BASE_URL` | `https://твой-домен` |

4. Домен: Settings → Networking → Custom Domain.
