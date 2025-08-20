from db import SessionLocal
from models import User
from werkzeug.security import generate_password_hash

db = SessionLocal()
admin = User(
    fio='Администратор',
    username='admin',
    password=generate_password_hash('admin'),
    is_admin=True
)
db.add(admin)
db.commit()
db.close()
print("Админ создан!")
