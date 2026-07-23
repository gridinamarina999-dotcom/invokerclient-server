"""
InvokerClient — сайт с регистрацией, подтверждением почты и админ-панелью.
"""

from __future__ import annotations

import os
import re
import secrets
import smtplib
import socket
from datetime import datetime, timezone
from email.message import EmailMessage
from email.utils import formataddr
from functools import wraps

from dotenv import load_dotenv
from flask import (
    Flask,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from flask_sqlalchemy import SQLAlchemy
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.security import check_password_hash, generate_password_hash

load_dotenv()

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", secrets.token_hex(32))
# Railway / reverse proxy: корректные https-ссылки в письмах
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

# Railway Postgres (DATABASE_URL) или локальный SQLite
_database_url = os.getenv("DATABASE_URL", "").strip()
if _database_url.startswith("postgres://"):
    _database_url = _database_url.replace("postgres://", "postgresql://", 1)
app.config["SQLALCHEMY_DATABASE_URI"] = _database_url or "sqlite:///invoker.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "gridinamarina999@gmail.com")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "GGs140711")

EMAIL_RE = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")

db = SQLAlchemy(app)


class User(db.Model):
    """Пользователь сайта: почта, хеш пароля, статус и дата регистрации."""

    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    is_admin = db.Column(db.Boolean, default=False, nullable=False)
    is_verified = db.Column(db.Boolean, default=False, nullable=False)
    verification_token = db.Column(db.String(64), unique=True, nullable=True)
    created_at = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)


class AppSetting(db.Model):
    """Настройки сайта (почта и т.п.) — хранятся в БД, без Railway Variables."""

    __tablename__ = "app_settings"

    key = db.Column(db.String(64), primary_key=True)
    value = db.Column(db.Text, nullable=False, default="")


def get_setting(key: str, default: str = "") -> str:
    """Сначала env (Railway Variables не стираются), потом БД (админка)."""
    env_val = (os.getenv(key, "") or "").strip()
    if env_val:
        return env_val
    row = db.session.get(AppSetting, key)
    if row and row.value.strip():
        return row.value.strip()
    return default.strip()


def set_setting(key: str, value: str) -> None:
    row = db.session.get(AppSetting, key)
    if row is None:
        row = AppSetting(key=key, value=value)
        db.session.add(row)
    else:
        row.value = value
    db.session.commit()


def is_valid_email(email: str) -> bool:
    """Проверка формата и существования домена почты (MX или A)."""
    if not EMAIL_RE.match(email):
        return False
    domain = email.rsplit("@", 1)[-1]
    try:
        import dns.resolver  # type: ignore

        for record in ("MX", "A"):
            try:
                dns.resolver.resolve(domain, record)
                return True
            except Exception:
                continue
        return False
    except ImportError:
        try:
            socket.getaddrinfo(domain, None)
            return True
        except OSError:
            return False


def build_verify_url(token: str) -> str:
    # 1) env / админка  2) автоматический URL текущего сайта
    base_url = get_setting("BASE_URL", "").rstrip("/")
    if not base_url:
        try:
            base_url = request.url_root.rstrip("/")
        except RuntimeError:
            base_url = "http://127.0.0.1:5000"
    return f"{base_url}/verify/{token}"


def get_mail_config() -> dict[str, str]:
    """SMTP: Railway Variables или настройки из админки."""
    username = get_setting("MAIL_USERNAME", ADMIN_EMAIL)
    password = get_setting("MAIL_PASSWORD", "")
    # Gmail app password часто копируют с пробелами
    password = password.replace(" ", "")
    return {
        "server": get_setting("MAIL_SERVER", "smtp.gmail.com"),
        "port": get_setting("MAIL_PORT", "587"),
        "use_tls": get_setting("MAIL_USE_TLS", "1"),
        "username": username,
        "password": password,
        "sender": get_setting("MAIL_DEFAULT_SENDER", username) or username,
    }


def mail_configured() -> bool:
    cfg = get_mail_config()
    return bool(cfg["username"] and cfg["password"])


def send_verification_email(to_email: str, token: str) -> None:
    """Отправляет письмо со ссылкой подтверждения через SMTP (587 или 465)."""
    cfg = get_mail_config()
    if not cfg["username"] or not cfg["password"]:
        raise RuntimeError(
            "Почта ещё не настроена. Зайди в админку → блок «Почта» и сохрани пароль приложения Gmail."
        )

    verify_url = build_verify_url(token)
    msg = EmailMessage()
    msg["Subject"] = "Подтверждение регистрации — InvokerClient"
    msg["From"] = formataddr(("InvokerClient", cfg["sender"]))
    msg["To"] = to_email
    msg.set_content(
        "Здравствуйте!\n\n"
        "Вы зарегистрировались на InvokerClient.\n"
        "Чтобы подтвердить почту, откройте ссылку:\n\n"
        f"{verify_url}\n\n"
        "Ссылка одноразовая. Если это были не вы — просто проигнорируйте письмо.\n"
    )
    msg.add_alternative(
        f"""\
<html>
  <body style="font-family:Arial,sans-serif;background:#0b0812;color:#f2eefc;padding:24px;">
    <div style="max-width:520px;margin:0 auto;background:#161022;border:1px solid #3b2d66;border-radius:16px;padding:28px;">
      <h1 style="margin:0 0 12px;font-size:22px;color:#c4b5fd;">InvokerClient</h1>
      <p style="margin:0 0 16px;line-height:1.5;color:#c7bfd9;">
        Подтвердите почту, чтобы завершить регистрацию.
      </p>
      <p style="margin:24px 0;">
        <a href="{verify_url}"
           style="display:inline-block;background:#7c3aed;color:#fff;text-decoration:none;
                  padding:12px 22px;border-radius:999px;font-weight:700;">
          Подтвердить почту
        </a>
      </p>
      <p style="margin:0;font-size:12px;color:#8b83a3;word-break:break-all;">
        Если кнопка не работает, откройте ссылку:<br>{verify_url}
      </p>
    </div>
  </body>
</html>
""",
        subtype="html",
    )

    last_error: Exception | None = None
    # Пробуем STARTTLS :587, затем SSL :465
    attempts = [
        (cfg["server"], int(cfg["port"] or "587"), True, False),
        (cfg["server"], 465, False, True),
    ]
    for host, port, starttls, ssl_mode in attempts:
        try:
            if ssl_mode:
                with smtplib.SMTP_SSL(host, port, timeout=30) as smtp:
                    smtp.login(cfg["username"], cfg["password"])
                    smtp.send_message(msg)
            else:
                with smtplib.SMTP(host, port, timeout=30) as smtp:
                    if starttls:
                        smtp.starttls()
                    smtp.login(cfg["username"], cfg["password"])
                    smtp.send_message(msg)
            return
        except Exception as exc:
            last_error = exc
            print(f"[MAIL] fail {host}:{port} → {exc}")

    raise RuntimeError(str(last_error) if last_error else "Неизвестная ошибка SMTP")


def current_user() -> User | None:
    user_id = session.get("user_id")
    if not user_id:
        return None
    return db.session.get(User, user_id)


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not current_user():
            flash("Сначала войдите в аккаунт.", "error")
            return redirect(url_for("login"))
        return view(*args, **kwargs)

    return wrapped


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        user = current_user()
        # Без ссылки в меню: посторонним просто «нет такой страницы»
        if not user or not user.is_admin:
            return redirect(url_for("index"))
        return view(*args, **kwargs)

    return wrapped


def seed_admin() -> None:
    """Создаёт/обновляет админа: вход только по этой почте и паролю."""
    admin = User.query.filter_by(email=ADMIN_EMAIL.lower()).first()
    if admin:
        admin.is_admin = True
        admin.is_verified = True
        admin.verification_token = None
        admin.set_password(ADMIN_PASSWORD)
        db.session.commit()
        return

    admin = User(
        email=ADMIN_EMAIL.lower(),
        is_admin=True,
        is_verified=True,
        verification_token=None,
    )
    admin.set_password(ADMIN_PASSWORD)
    db.session.add(admin)
    db.session.commit()
    print(f"[OK] Админ создан: {ADMIN_EMAIL}")


@app.context_processor
def inject_user():
    return {"current_user": current_user()}


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if current_user():
        return redirect(url_for("index"))

    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""
        password2 = request.form.get("password2") or ""

        if not is_valid_email(email):
            flash("Введите существующий email (проверьте адрес и домен).", "error")
            return render_template("register.html")

        if len(password) < 6:
            flash("Пароль должен быть не короче 6 символов.", "error")
            return render_template("register.html")

        if password != password2:
            flash("Пароли не совпадают.", "error")
            return render_template("register.html")

        existing = User.query.filter_by(email=email).first()
        if existing and existing.is_verified:
            flash("Пользователь с такой почтой уже зарегистрирован.", "error")
            return render_template("register.html")

        token = secrets.token_urlsafe(32)

        if existing and not existing.is_verified:
            # Повторная регистрация неподтверждённого аккаунта — обновляем пароль и шлём письмо снова
            existing.set_password(password)
            existing.verification_token = token
            user = existing
        else:
            user = User(
                email=email,
                is_admin=False,
                is_verified=False,
                verification_token=token,
            )
            user.set_password(password)
            db.session.add(user)

        db.session.commit()

        try:
            send_verification_email(email, token)
        except Exception as exc:
            print(f"[MAIL ERROR] {exc}")
            # Аккаунт оставляем — админ может подтвердить вручную
            flash(
                "Аккаунт создан, но письмо не отправилось. "
                "Зайди в админку → Почта (сохрани пароль приложения снова) "
                "или подтверди пользователя кнопкой «Подтвердить». "
                f"Ошибка: {exc}",
                "warning",
            )
            return render_template("verify_notice.html", email=email)

        flash(
            "Регистрация прошла успешно. Мы отправили письмо — откройте ссылку внутри.",
            "success",
        )
        return render_template("verify_notice.html", email=email)

    return render_template("register.html")


@app.route("/verify/<token>")
def verify_email(token: str):
    user = User.query.filter_by(verification_token=token).first()
    if not user:
        flash("Ссылка недействительна или уже использована.", "error")
        return redirect(url_for("login"))

    user.is_verified = True
    user.verification_token = None
    db.session.commit()
    flash("Почта подтверждена. Теперь можно войти.", "success")
    return redirect(url_for("login"))


@app.route("/resend-verification", methods=["GET", "POST"])
def resend_verification():
    """Повторная отправка письма подтверждения."""
    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        user = User.query.filter_by(email=email).first()

        if not user:
            flash("Если такой аккаунт есть — письмо будет отправлено.", "success")
            return redirect(url_for("login"))

        if user.is_verified:
            flash("Эта почта уже подтверждена. Можно входить.", "success")
            return redirect(url_for("login"))

        token = secrets.token_urlsafe(32)
        user.verification_token = token
        db.session.commit()

        try:
            send_verification_email(email, token)
            flash("Письмо отправлено повторно. Проверьте почту и «Спам».", "success")
        except Exception as exc:
            print(f"[MAIL ERROR] {exc}")
            flash("Не удалось отправить письмо. Попробуйте позже.", "error")

        return redirect(url_for("login"))

    return render_template("resend.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    user = current_user()
    if user:
        # Уже вошли: админ сразу в панель, остальные на главную
        if user.is_admin:
            return redirect(url_for("admin_panel"))
        return redirect(url_for("index"))

    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""

        user = User.query.filter_by(email=email).first()
        if not user or not user.check_password(password):
            flash("Неверная почта или пароль.", "error")
            return render_template("login.html")

        if not user.is_verified:
            flash("Сначала подтвердите почту — ссылка была в письме после регистрации.", "error")
            return render_template("login.html")

        session.clear()
        session["user_id"] = user.id

        # Админ-панель только после входа под админ-аккаунтом (без пункта в меню)
        if user.is_admin:
            flash("Вход выполнен. Админ-панель.", "success")
            return redirect(url_for("admin_panel"))

        flash("Вы вошли в аккаунт.", "success")
        return redirect(url_for("index"))

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("Вы вышли из аккаунта.", "success")
    return redirect(url_for("index"))


@app.route("/admin", methods=["GET", "POST"])
@admin_required
def admin_panel():
    if request.method == "POST":
        action = request.form.get("action") or ""

        if action == "save_mail":
            username = (request.form.get("mail_username") or "").strip()
            password = (request.form.get("mail_password") or "").strip()
            # убираем пробелы из пароля приложения Gmail (Google показывает с пробелами)
            password = password.replace(" ", "")
            set_setting("MAIL_SERVER", "smtp.gmail.com")
            set_setting("MAIL_PORT", "587")
            set_setting("MAIL_USE_TLS", "1")
            set_setting("MAIL_USERNAME", username)
            if password:
                set_setting("MAIL_PASSWORD", password)
            set_setting("MAIL_DEFAULT_SENDER", username)
            set_setting("BASE_URL", request.url_root.rstrip("/"))
            flash("Настройки почты сохранены.", "success")

            if password or get_setting("MAIL_PASSWORD"):
                try:
                    # тестовое письмо самому себе
                    token = secrets.token_urlsafe(8)
                    send_verification_email(username, token)
                    flash("Тестовое письмо отправлено на твою почту. Проверь «Входящие» и «Спам».", "success")
                except Exception as exc:
                    print(f"[MAIL TEST ERROR] {exc}")
                    flash(
                        f"Сохранено, но отправка не прошла: {exc}. "
                        "Нужен пароль приложения Google, не обычный пароль.",
                        "error",
                    )
            return redirect(url_for("admin_panel"))

        if action == "verify_user":
            user_id = request.form.get("user_id")
            user = db.session.get(User, int(user_id)) if user_id else None
            if user and not user.is_admin:
                user.is_verified = True
                user.verification_token = None
                db.session.commit()
                flash(f"Почта подтверждена вручную: {user.email}", "success")
            return redirect(url_for("admin_panel"))

    users = User.query.order_by(User.created_at.desc()).all()
    cfg = get_mail_config()
    return render_template(
        "admin.html",
        users=users,
        mail_username=cfg["username"],
        mail_configured=mail_configured(),
        mail_password_set=bool(cfg["password"]),
    )


@app.route("/admin/verify/<int:user_id>", methods=["POST"])
@admin_required
def admin_verify_user(user_id: int):
    user = db.session.get(User, user_id)
    if user and not user.is_admin:
        user.is_verified = True
        user.verification_token = None
        db.session.commit()
        flash(f"Подтверждено: {user.email}", "success")
    return redirect(url_for("admin_panel"))


with app.app_context():
    db.create_all()
    seed_admin()


if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    app.run(
        debug=os.getenv("FLASK_DEBUG", "0") == "1",
        host="0.0.0.0",
        port=port,
    )
