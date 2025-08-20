from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from db import SessionLocal
from models import *
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy.orm import joinedload  # ← добавили

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        fio = request.form['fio']
        username = request.form['username']
        password = request.form['password']
        tab_number = request.form['tab_number']

        db = SessionLocal()
        user = db.query(User).filter_by(username=username).first()
        if user:
            flash('Логин уже занят!')
            db.close()
            return redirect(url_for('auth.register'))

        user = User(
            fio=fio,
            username=username,
            password=generate_password_hash(password),
            tab_number=tab_number,
            is_admin=False
        )
        db.add(user)
        db.commit()
        db.close()
        flash('Регистрация успешна! Теперь войдите.')
        return redirect(url_for('auth.login'))

    return render_template('register.html')


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        db = SessionLocal()
        user = db.query(User).filter_by(username=username).first()
        db.close()
        if user and check_password_hash(user.password, password):
            session['user_id'] = user.id
            session['is_admin'] = user.is_admin
            session['fio'] = user.fio
            if user.is_admin:
                return redirect(url_for('auth.admin_dashboard'))
            return redirect(url_for('auth.user_dashboard'))
        else:
            flash('Неверный логин или пароль')
    return render_template('login.html')


@auth_bp.route('/admin')
def admin_dashboard():
    if not session.get('is_admin'):
        return redirect(url_for('auth.login'))
    db = SessionLocal()
    users = db.query(User).filter_by(is_admin=False).all()
    db.close()
    return render_template('admin_dashboard.html', users=users)


@auth_bp.route('/dashboard')
def user_dashboard():
    if not session.get('user_id'):
        return redirect(url_for('auth.login'))

    db = SessionLocal()
    try:
        fio = session.get('fio')
        user_id = session['user_id']

        # Подтягиваем тесты с вопросами и ответами, чтобы посчитать максимум
        tests = db.query(Test).options(
            joinedload(Test.questions).joinedload(Question.answers)
        ).all()

        # Последний результат пользователя по каждому тесту (если нужно — можно выбрать max по времени)
        user_results = {
            r.test_id: r
            for r in db.query(TestResult).filter_by(user_id=user_id).all()
        }

        # Максимально возможный балл по тесту = сумма max(score) по каждому вопросу
        max_by_test = {}
        for t in tests:
            max_score = 0.0
            for q in t.questions or []:
                if q.answers:
                    max_score += max((a.score for a in q.answers), default=0.0)
            max_by_test[t.id] = round(max_score, 2)

        return render_template(
            'user_dashboard.html',
            fio=fio,
            tests=tests,
            user_results=user_results,
            max_by_test=max_by_test,
        )
    finally:
        db.close()


@auth_bp.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('auth.login'))
