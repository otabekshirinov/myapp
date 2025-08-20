# app.py
import os
from flask import Flask, redirect, url_for, session, flash

# Загружаем .env (если есть)
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

# Blueprints
from auth.routes import auth_bp
from admin_tests.routes import tests_bp
from user_tests.user_tests_bp import user_tests_bp

# Для бутстрапа админа
from werkzeug.security import generate_password_hash
from db import SessionLocal, Base, engine
from models import User


def ensure_default_admin() -> None:
    """
    1) (Опционально) создаёт таблицы в БД
       ENV: AUTO_CREATE_TABLES=1 (по умолчанию 1)
    2) Создаёт дефолтного админа, если ни одного ещё нет.
       Логин/пароль/ФИО берём из ENV:
         ADMIN_USERNAME (default 'admin')
         ADMIN_PASSWORD (default 'admin')
         ADMIN_FIO      (default 'Администратор')
    """
    if os.getenv("AUTO_CREATE_TABLES", "1") == "1":
        try:
            Base.metadata.create_all(bind=engine)
            print("[BOOTSTRAP] create_all() OK")
        except Exception as e:
            print(f"[BOOTSTRAP] create_all() skipped/error: {e}")

    db = SessionLocal()
    try:
        # Если есть хоть один админ — ничего не делаем
        any_admin = db.query(User).filter_by(is_admin=True).first()
        if any_admin:
            print("[BOOTSTRAP] Admin already exists — skip creating.")
            return

        username = (os.getenv("ADMIN_USERNAME", "admin") or "admin").strip()
        password = (os.getenv("ADMIN_PASSWORD", "admin") or "admin").strip()
        fio      = (os.getenv("ADMIN_FIO", "Администратор") or "Администратор").strip()

        # Если пользователь с таким логином есть — просто повышаем его до админа
        existing = db.query(User).filter_by(username=username).first()
        if existing:
            if not existing.is_admin:
                existing.is_admin = True
                db.commit()
                print(f"[BOOTSTRAP] User '{username}' promoted to admin.")
            else:
                print(f"[BOOTSTRAP] User '{username}' is already admin.")
            return

        # Создаём нового админа
        admin = User(
            fio=fio,
            username=username,
            password=generate_password_hash(password),
            is_admin=True
        )
        db.add(admin)
        db.commit()
        print(f"[BOOTSTRAP] Admin '{username}' created.")
    except Exception as e:
        print(f"[BOOTSTRAP] Failed to ensure admin: {e}")
    finally:
        db.close()


app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'your-secret-key')

# Регистрируем blueprints
app.register_blueprint(auth_bp)
app.register_blueprint(tests_bp)
app.register_blueprint(user_tests_bp)

# Бутстрапим БД и админа (безопасно при многократном запуске)
ensure_default_admin()


@app.route("/")
def index():
    if 'user_id' in session:
        if session.get('is_admin'):
            return redirect(url_for('tests.list_tests'))      # для админа
        else:
            return redirect(url_for('user_tests.list_tests')) # для пользователя
    return redirect(url_for('auth.login'))


if __name__ == "__main__":
    # debug=True — для разработки, уберите/поставьте False в проде
    app.run(host="0.0.0.0", port=80, debug=True)
