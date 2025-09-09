from db.db_models import User
from db_utils import create_user, fetch_user_by_id, update_user_status
from user_management.auth import login

def test_full_registration_approval_login(db_session):
    # Register
    password = "secret"
    password_hash = User.hash_password(password)
    user_id = create_user(db_session, "newuser", "new@user.com", password_hash)
    db_session.commit()  # <-- Add this line!
    user = fetch_user_by_id(db_session, user_id)
    assert user.status == "Pending"
    # Try login (should fail)
    session_token, error = login(db_session, "newuser", password)  # <-- Pass session!
    assert session_token is None
    assert "not approved" in error
    # Approve user
    update_user_status(db_session, user_id, "Approved", approved_by=1)
    db_session.commit()
    # Try login (should succeed)
    session_token, error = login(db_session, "newuser", password)
    assert session_token is not None
    assert error is None