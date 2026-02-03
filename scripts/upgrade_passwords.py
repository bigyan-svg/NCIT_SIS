import os
import mysql.connector
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash

load_dotenv()


def is_password_hashed(value):
    if not value:
        return False
    return (
        value.startswith("pbkdf2:")
        or value.startswith("scrypt:")
        or value.startswith("argon2:")
    )


def get_db():
    return mysql.connector.connect(
        host=os.getenv("DB_HOST", "localhost"),
        user=os.getenv("DB_USER", "root"),
        password=os.getenv("DB_PASSWORD", ""),
        database=os.getenv("DB_NAME", "ncit_sis"),
        port=int(os.getenv("DB_PORT", "3306")),
    )


def main():
    conn = get_db()
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT user_id, email, password FROM users")
    users = cur.fetchall()

    upgraded = 0
    for user in users:
        stored = user["password"]
        if not is_password_hashed(stored):
            new_hash = generate_password_hash(stored)
            cur.execute(
                "UPDATE users SET password=%s WHERE user_id=%s",
                (new_hash, user["user_id"]),
            )
            upgraded += 1

    if upgraded:
        conn.commit()

    conn.close()
    print(f"Upgraded {upgraded} user password(s).")


if __name__ == "__main__":
    main()
