from flask import Blueprint, render_template, session, redirect, url_for, request, flash
from sqlalchemy.orm import joinedload
from sqlalchemy import func
import datetime
import random

from db import SessionLocal
from models import Test, Question, Answer, TestResult, UserAnswer

user_tests_bp = Blueprint('user_tests', __name__, url_prefix='/user/tests')


@user_tests_bp.route('/')
def list_tests():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    db = SessionLocal()
    try:
        tests = db.query(Test).all()
        return render_template('user_tests/list.html', tests=tests)
    finally:
        db.close()


@user_tests_bp.route('/<int:test_id>/ready')
def ready_test(test_id: int):
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    db = SessionLocal()
    try:
        test = db.get(Test, test_id)
        if not test:
            flash('Тест не найден', 'error')
            return redirect(url_for('user_tests.list_tests'))
        return render_template('user_tests/ready.html', test=test)
    finally:
        db.close()


def _session_key_selected(res_id: int) -> str:
    return f'selected_questions_{res_id}'


@user_tests_bp.route('/<int:test_id>/start', methods=['GET', 'POST'])
def start_test(test_id: int):
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))

    user_id = session['user_id']
    db = SessionLocal()
    try:
        test = db.get(Test, test_id)
        if not test:
            flash('Тест не найден', 'error')
            return redirect(url_for('user_tests.list_tests'))

        res = db.query(TestResult).filter_by(
            user_id=user_id, test_id=test_id, passed_at=None
        ).first()

        # ---------- GET ----------
        if request.method == 'GET':
            if not res:
                res = TestResult(
                    user_id=user_id,
                    test_id=test_id,
                    started_at=datetime.datetime.utcnow()
                )
                db.add(res)
                db.commit()

            skey = _session_key_selected(res.id)
            selected_ids = session.get(skey)

            if not selected_ids:
                all_q_ids = [qid for (qid,) in db.query(Question.id)
                                               .filter(Question.test_id == test_id)
                                               .all()]
                n_total = len(all_q_ids)
                if n_total == 0:
                    flash('В этом тесте пока нет вопросов.', 'warning')
                    return redirect(url_for('user_tests.list_tests'))
                n_pick = test.questions_per_attempt or n_total
                n_pick = max(1, min(n_pick, n_total))
                selected_ids = random.sample(all_q_ids, n_pick)
                session[skey] = selected_ids
                session.modified = True

            selected_qs = db.query(Question)\
                .options(joinedload(Question.answers))\
                .filter(Question.id.in_(selected_ids)).all()
            order = {qid: i for i, qid in enumerate(selected_ids)}
            selected_qs.sort(key=lambda q: order.get(q.id, 10**9))
            for q in selected_qs:
                random.shuffle(q.answers)

            # ВАЖНО: считаем оставшиеся секунды на сервере
            time_limit_sec = test.time_limit * 60 if test.time_limit else None
            remaining_seconds = None
            if time_limit_sec:
                elapsed = int((datetime.datetime.utcnow() - res.started_at).total_seconds())
                remaining_seconds = max(0, time_limit_sec - elapsed)

            return render_template(
                'user_tests/start.html',
                test=test,
                questions=selected_qs,
                time_limit=time_limit_sec,       # секунды
                remaining_seconds=remaining_seconds,  # секунды на старте таймера
            )

        # ---------- POST ----------
        if not res:
            flash('Не найдена начатая попытка', 'error')
            return redirect(url_for('user_tests.ready_test', test_id=test_id))
        if res.passed_at:
            flash('Тест уже завершён', 'warning')
            return redirect(url_for('user_tests.view_result', result_id=res.id))

        skey = _session_key_selected(res.id)
        selected_ids = session.get(skey) or []
        selected_qs = db.query(Question)\
            .options(joinedload(Question.answers))\
            .filter(Question.id.in_(selected_ids)).all()

        # проверяем, истёк ли лимит
        expired = False
        if test.time_limit:
            elapsed_min = (datetime.datetime.utcnow() - res.started_at).total_seconds() / 60
            expired = elapsed_min >= test.time_limit

        # если нет ни одного ответа:
        no_answers = not any(request.form.get(f'question_{q.id}') for q in selected_qs)
        if no_answers:
            if expired:
                # корректно завершаем попытку с нулём, чтобы не было бесконечного цикла
                res.score = 0.0
                res.passed_at = datetime.datetime.utcnow()
                db.commit()
                session.pop(skey, None)
                flash('Время вышло. Попытка завершена.', 'warning')
                return redirect(url_for('user_tests.view_result', result_id=res.id))
            else:
                flash('Вы не выбрали ни одного ответа!', 'error')
                return redirect(url_for('user_tests.start_test', test_id=test_id))

        # сохраняем ответы
        db.query(UserAnswer).filter_by(result_id=res.id).delete()
        score = 0.0
        to_add = []
        for q in selected_qs:
            sel = request.form.get(f'question_{q.id}')
            if not sel:
                continue
            a = db.query(Answer).filter(
                Answer.id == int(sel),
                Answer.question_id == q.id
            ).first()
            if a:
                score += a.score
                to_add.append(UserAnswer(result_id=res.id, question_id=q.id, answer_id=a.id))
        if to_add:
            db.add_all(to_add)

        res.score = score
        res.passed_at = datetime.datetime.utcnow()
        db.commit()
        session.pop(skey, None)
        flash(f'Тест завершён! Ваш результат: {score:.1f} балл(ов).', 'success')
        return redirect(url_for('user_tests.view_result', result_id=res.id))

    finally:
        db.close()



@user_tests_bp.route('/result/<int:result_id>')
def view_result(result_id: int):
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    db = SessionLocal()
    try:
        res = db.query(TestResult).options(
            joinedload(TestResult.test),
            joinedload(TestResult.answers)
                .joinedload(UserAnswer.question)
                .joinedload(Question.answers),
            joinedload(TestResult.answers)
                .joinedload(UserAnswer.answer)
        ).filter_by(id=result_id, user_id=session['user_id']).first()

        if not res:
            flash('Результат не найден', 'error')
            return redirect(url_for('user_tests.list_tests'))

        return render_template('user_tests/result.html', result=res)
    finally:
        db.close()
