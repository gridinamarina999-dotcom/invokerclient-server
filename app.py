"""
InvokerClient — сайт с регистрацией, подтверждением почты и админ-панелью.
"""

from __future__ import annotations

import os
import secrets
import smtplib
from datetime import datetime, timezone
from email.message import EmailMessage
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
from werkzeug.security import check_password_hash, generate_password_hash

load_dotenv()

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", secrets.token_hex(32))

# Railway Postgres (DATABASE_URL) или локальный SQLite
_database_url = os.getenv("DATABASE_URL", "").strip()
if _database_url.startswith("postgres://"):
    # SQLAlchemy 2 / Railway: postgres:// → postgresql://
    _database_url = _database_url.replace("postgres://", "postgresql://", 1)
app.config["SQLALCHEMY_DATABASE_URI"] = _database_url or "sqlite:///invoker.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# Админ: на Railway задай ADMIN_EMAIL / ADMIN_PASSWORD в Variables
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "gridinamarina999@gmail.com")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "GGs140711")

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


def send_verification_email(to_email: str, token: str) -> tuple[bool, str]:
    """
    Отправляет письмо со ссылкой подтверждения.
    Если SMTP не настроен — возвращает ссылку для ручного перехода (удобно при разработке).
    """
    base_url = os.getenv("BASE_URL", "http://127.0.0.1:5000").rstrip("/")
    verify_url = f"{base_url}/verify/{token}"

    mail_server = os.getenv("MAIL_SERVER", "").strip()
    mail_username = os.getenv("MAIL_USERNAME", "").strip()
    mail_password = os.getenv("MAIL_PASSWORD", "").strip()
    mail_sender = os.getenv("MAIL_DEFAULT_SENDER", mail_username).strip()

    # Без SMTP — не падаем: отдаём ссылку в UI/консоль
    if not mail_server or not mail_username or not mail_password:
        print(f"[DEV] Ссылка подтверждения для {to_email}: {verify_url}")
        return False, verify_url

    msg = EmailMessage()
    msg["Subject"] = "Подтверждение регистрации — InvokerClient"
    msg["From"] = mail_sender
    msg["To"] = to_email
    msg.set_content(
        "Здравствуйте!\n\n"
        "Вы зарегистрировались на InvokerClient.\n"
        "Чтобы подтвердить почту, откройте ссылку:\n\n"
        f"{verify_url}\n\n"
        "Если это были не вы — просто проигнорируйте письмо.\n"
    )

    port = int(os.getenv("MAIL_PORT", "587"))
    use_tls = os.getenv("MAIL_USE_TLS", "1") == "1"

    with smtplib.SMTP(mail_server, port, timeout=30) as smtp:
        if use_tls:
            smtp.starttls()
        smtp.login(mail_username, mail_password)
        smtp.send_message(msg)

    return True, verify_url


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

        if not email or "@" not in email or "." not in email.split("@")[-1]:
            flash("Введите корректный адрес почты.", "error")
            return render_template("register.html")

        if len(password) < 6:
            flash("Пароль должен быть не короче 6 символов.", "error")
            return render_template("register.html")

        if password != password2:
            flash("Пароли не совпадают.", "error")
            return render_template("register.html")

        if User.query.filter_by(email=email).first():
            flash("Пользователь с такой почтой уже зарегистрирован.", "error")
            return render_template("register.html")

        token = secrets.token_urlsafe(32)
        user = User(
            email=email,
            is_admin=False,
            is_verified=False,
            verification_token=token,
        )
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        sent, verify_url = send_verification_email(email, token)
        if sent:
            flash(
                "Регистрация прошла успешно. Проверьте почту и перейдите по ссылке подтверждения.",
                "success",
            )
            return render_template("verify_notice.html", email=email, verify_url=None)

        # SMTP не настроен — показываем ссылку, чтобы можно было протестировать
        flash(
            "Аккаунт создан. SMTP не настроен — подтвердите почту по ссылке ниже.",
            "warning",
        )
        return render_template("verify_notice.html", email=email, verify_url=verify_url)

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


@app.route("/admin")
@admin_required
def admin_panel():
    users = User.query.order_by(User.created_at.desc()).all()
    return render_template("admin.html", users=users)


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
