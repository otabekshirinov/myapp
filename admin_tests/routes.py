from flask import Blueprint, render_template, request, redirect, url_for, session, flash, abort
from db import SessionLocal
from models import *
from sqlalchemy.orm import joinedload
from sqlalchemy import func

tests_bp = Blueprint('tests', __name__, url_prefix='/tests')

def is_admin():
    return session.get('is_admin')

def _pos_int_or_none(v, *, max_value=None):
    """Парсим целое > 0. Если пусто/мусор/<=0 — возвращаем None. При max_value — обрезаем сверху."""
    try:
        n = int(str(v).strip())
    except (TypeError, ValueError):
        return None
    if n <= 0:
        return None
    if max_value is not None:
        n = min(n, max_value)
    return n

@tests_bp.route('/')
def list_tests():
    if not is_admin():
        return redirect(url_for('auth.login'))
    db = SessionLocal()
    tests = db.query(Test).all()
    db.close()
    return render_template('tests/list.html', tests=tests)

# create_test
@tests_bp.route('/create', methods=['GET', 'POST'])
def create_test():
    if not is_admin():
        return redirect(url_for('auth.login'))
    if request.method == 'POST':
        title = request.form['title']
        description = request.form['description']
        time_limit = request.form.get('time_limit')
        time_limit = int(time_limit) if time_limit and time_limit.strip() and int(time_limit) > 0 else None

        # НОВОЕ:
        qpa = request.form.get('questions_per_attempt')
        questions_per_attempt = int(qpa) if qpa and qpa.strip() and int(qpa) > 0 else None

        db = SessionLocal()
        test = Test(
            title=title,
            description=description,
            time_limit=time_limit,
            questions_per_attempt=questions_per_attempt  # ← НОВОЕ
        )
        db.add(test)
        db.commit()
        test_id = test.id
        db.close()
        return redirect(url_for('tests.view_test', test_id=test_id))
    return render_template('tests/create.html')


@tests_bp.route('/<int:test_id>')
def view_test(test_id):
    if not is_admin():
        return redirect(url_for('auth.login'))
    db = SessionLocal()
    test = db.query(Test)\
        .options(joinedload(Test.questions).joinedload(Question.answers))\
        .filter_by(id=test_id).first()
    db.close()
    return render_template('tests/view.html', test=test)

@tests_bp.route('/<int:test_id>/add_question', methods=['GET', 'POST'])
def add_question(test_id):
    if not is_admin():
        return redirect(url_for('auth.login'))
    db = SessionLocal()
    test = db.query(Test).filter_by(id=test_id).first()
    if request.method == 'POST':
        q_text = request.form['text']
        answer_count = 0
        answers = []
        while True:
            answer_count += 1
            if not request.form.get(f'ans_{answer_count}'):
                answer_count -= 1
                break
        if answer_count < 2:
            flash('Добавьте минимум два варианта!')
            db.close()
            return render_template('tests/add_question.html', test=test)
        q = Question(text=q_text, test_id=test.id)
        db.add(q)
        db.commit()
        correct = int(request.form['correct'])
        for i in range(1, answer_count + 1):
            ans_text = request.form.get(f'ans_{i}')
            if not ans_text:
                continue
            score = float(request.form.get(f'score_{i}', 0))
            is_corr = (i == correct)
            answers.append(Answer(text=ans_text, is_correct=is_corr, score=score, question=q))
        db.add_all(answers)
        db.commit()
        test_id_val = test.id  # Сохраняем id
        db.close()
        return redirect(url_for('tests.view_test', test_id=test_id_val))
    db.close()
    return render_template('tests/add_question.html', test=test)

@tests_bp.route('/<int:test_id>/delete', methods=['POST'])
def delete_test(test_id):
    if not is_admin():
        return redirect(url_for('auth.login'))
    db = SessionLocal()
    test = db.query(Test).filter_by(id=test_id).first()
    if test:
        db.delete(test)
        db.commit()
    db.close()
    flash('Тест удалён', 'success')
    return redirect(url_for('tests.list_tests'))

# edit_test
@tests_bp.route('/<int:test_id>/edit', methods=['GET', 'POST'])
def edit_test(test_id):
    if not is_admin():
        return redirect(url_for('auth.login'))

    db = SessionLocal()
    try:
        # Берём тест (без questions, чтобы не детачить ленивые связи)
        test = db.query(Test).filter_by(id=test_id).first()
        if not test:
            flash('Тест не найден', 'error')
            return redirect(url_for('tests.list_tests'))

        if request.method == 'POST':
            # Текстовые поля
            test.title = (request.form.get('title') or '').strip()
            test.description = (request.form.get('description') or '').strip()

            # Лимиты
            # Ограничение по времени: 0/пусто -> None; иначе 1..240
            test.time_limit = _pos_int_or_none(request.form.get('time_limit'), max_value=240)

            # Сколько вопросов показывать за попытку
            # Сначала узнаём сколько всего вопросов в тесте
            n_total = db.query(func.count(Question.id)).filter(Question.test_id == test.id).scalar() or 0
            qpa_val = _pos_int_or_none(request.form.get('questions_per_attempt'))
            if qpa_val is not None:
                # не даём поставить больше, чем есть вопросов (и не меньше 1)
                if n_total > 0:
                    qpa_val = max(1, min(qpa_val, n_total))
                else:
                    # если вопросов ещё нет — игнорируем число и держим None
                    qpa_val = None
            test.questions_per_attempt = qpa_val

            db.commit()
            flash('Тест обновлён', 'success')
            return redirect(url_for('tests.view_test', test_id=test.id))

        # GET: считаем количество вопросов отдельно (без обращения к test.questions)
        questions_count = db.query(func.count(Question.id)).filter(Question.test_id == test.id).scalar() or 0
        return render_template('tests/edit.html', test=test, questions_count=questions_count)

    except Exception as e:
        db.rollback()
        # Можно залогировать e, если используешь логгер
        flash('Не удалось сохранить изменения. Проверьте введённые данные.', 'error')
        return redirect(url_for('tests.edit_test', test_id=test_id))
    finally:
        db.close()



@tests_bp.route('/question/<int:question_id>/delete', methods=['POST'])
def delete_question(question_id):
    if not is_admin():
        return redirect(url_for('auth.login'))
    db = SessionLocal()
    q = db.query(Question).filter_by(id=question_id).first()
    test_id = q.test_id if q else None
    if q:
        db.delete(q)
        db.commit()
    db.close()
    flash('Вопрос удалён', 'success')
    return redirect(url_for('tests.view_test', test_id=test_id))

@tests_bp.route('/question/<int:question_id>/edit', methods=['GET', 'POST'])
def edit_question(question_id):
    if not is_admin():
        return redirect(url_for('auth.login'))
    db = SessionLocal()
    q = db.query(Question)\
        .options(joinedload(Question.answers), joinedload(Question.test))\
        .filter_by(id=question_id).first()
    if not q:
        db.close()
        return redirect(url_for('tests.list_tests'))
    if request.method == 'POST':
        q.text = request.form['text']
        for a in q.answers:
            db.delete(a)
        db.commit()
        answers = []
        correct = int(request.form['correct'])
        answer_count = 0
        while True:
            answer_count += 1
            if not request.form.get(f'ans_{answer_count}'):
                answer_count -= 1
                break
        for i in range(1, answer_count+1):
            ans_text = request.form.get(f'ans_{i}')
            if not ans_text:
                continue
            score = float(request.form.get(f'score_{i}', 0))
            is_corr = (i == correct)
            answers.append(Answer(text=ans_text, is_correct=is_corr, score=score, question=q))
        db.add_all(answers)
        db.commit()
        test_id = q.test_id
        db.close()
        flash('Вопрос обновлён', 'success')
        return redirect(url_for('tests.view_test', test_id=test_id))
    db.close()
    return render_template('tests/edit_question.html', question=q)

@tests_bp.route('/<int:test_id>/results')
def test_results(test_id):
    if not is_admin():
        return redirect(url_for('auth.login'))

    db = SessionLocal()
    test = db.query(Test).filter_by(id=test_id).first()

    # Получаем результаты с join-ами
    results = db.query(TestResult)\
        .options(
            joinedload(TestResult.user),
            joinedload(TestResult.test)
        )\
        .filter_by(test_id=test_id).order_by(TestResult.score.desc()).all()

    # Максимальный балл (можно хранить в тесте, либо считать по вопросам)
    if hasattr(test, 'max_score') and test.max_score:
        max_score = test.max_score
    else:
        # Если max_score не задан, возьмём максимальный из результатов, fallback=0
        max_score = max([r.score for r in results], default=0)

    # Средний балл
    if results:
        avg_score = round(sum(r.score for r in results) / len(results), 2)
        min_score = min(r.score for r in results)
    else:
        avg_score = 0
        min_score = 0

    db.close()
    return render_template(
        'tests/results.html',
        test=test,
        results=results,
        max_score=max_score,
        avg_score=avg_score,
        min_score=min_score
    )


@tests_bp.route('/result/<int:result_id>')
def view_result(result_id):
    if not is_admin():
        return redirect(url_for('auth.login'))
    db = SessionLocal()
    result = db.query(TestResult)\
        .options(
            joinedload(TestResult.user),
            joinedload(TestResult.test),
            joinedload(TestResult.answers).joinedload(UserAnswer.question),
            joinedload(TestResult.answers).joinedload(UserAnswer.answer)
        )\
        .filter_by(id=result_id).first()
    db.close()
    if not result:
        abort(404)
    return render_template('tests/user_result.html', result=result)
