from db.db_models import User
from db_utils import get_db

db_session = get_db()
password = "admin"
password_hash = User.hash_password(password)
user = User(
    username="adminr",
    email="philiplau114@gmail.com",
    password_hash=password_hash,
    role="Admin",
    status="Approved"
)
db_session.add(user)
db_session.commit()
print("Admin user created!")