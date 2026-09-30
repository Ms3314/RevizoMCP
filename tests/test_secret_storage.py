from cryptography.fernet import Fernet

from app.secret_storage import decrypt_leetcode_session, encrypt_leetcode_session


def test_leetcode_session_is_encrypted_at_rest(monkeypatch):
    monkeypatch.setenv("LEETCODE_SESSION_ENCRYPTION_KEY", Fernet.generate_key().decode())
    cookie = "user-private-session-value"

    encrypted = encrypt_leetcode_session(cookie)

    assert encrypted.startswith("fernet:v1:")
    assert cookie not in encrypted
    assert decrypt_leetcode_session(encrypted) == cookie
