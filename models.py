from db import Base
from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, Float, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.types import Unicode
import datetime

class User(Base):
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True, index=True)
    fio = Column(Unicode(200), nullable=False)
    username = Column(Unicode(100), unique=True, nullable=False)
    password = Column(Unicode(255), nullable=False)
    tab_number = Column(Unicode(20))
    is_admin = Column(Boolean, default=False)

    results = relationship('TestResult', back_populates='user', cascade="all, delete-orphan")

class Test(Base):
    __tablename__ = 'tests'
    id = Column(Integer, primary_key=True)
    title = Column(Unicode(255), nullable=False)
    description = Column(Unicode(1000))
    time_limit = Column(Integer, nullable=True)  # в минутах, None — неограничено
    questions_per_attempt = Column(Integer, nullable=True)  # ← ДОБАВЛЕНО: сколько вопросов показывать
    questions = relationship('Question', back_populates='test', cascade="all, delete-orphan")
    results = relationship('TestResult', back_populates='test', cascade="all, delete-orphan")

class Question(Base):
    __tablename__ = 'questions'
    id = Column(Integer, primary_key=True)
    test_id = Column(Integer, ForeignKey('tests.id'), nullable=False)
    text = Column(Unicode(500), nullable=False)
    answers = relationship('Answer', back_populates='question', cascade="all, delete-orphan")
    test = relationship('Test', back_populates='questions')

class Answer(Base):
    __tablename__ = 'answers'
    id = Column(Integer, primary_key=True)
    question_id = Column(Integer, ForeignKey('questions.id'), nullable=False)
    text = Column(Unicode(255), nullable=False)
    is_correct = Column(Boolean, default=False)
    score = Column(Float, default=0.0)
    question = relationship('Question', back_populates='answers')

# --- Прохождение теста ---

class TestResult(Base):
    __tablename__ = 'test_results'

    id = Column(Integer, primary_key=True)
    user_id   = Column(Integer, ForeignKey('users.id'),   nullable=False)
    test_id   = Column(Integer, ForeignKey('tests.id'),   nullable=False)
    started_at = Column(DateTime, nullable=False, default=datetime.datetime.utcnow)
    passed_at  = Column(DateTime, nullable=True)
    score      = Column(Float,   default=0.0)

    user    = relationship('User',       back_populates='results')
    test    = relationship('Test',       back_populates='results')
    answers = relationship('UserAnswer', back_populates='result', cascade='all, delete-orphan')

class UserAnswer(Base):
    __tablename__ = 'user_answers'
    id = Column(Integer, primary_key=True)
    result_id = Column(Integer, ForeignKey('test_results.id'), nullable=False)
    question_id = Column(Integer, ForeignKey('questions.id'), nullable=False)
    answer_id = Column(Integer, ForeignKey('answers.id'), nullable=False)

    result = relationship('TestResult', back_populates='answers')
    question = relationship('Question')
    answer = relationship('Answer')
