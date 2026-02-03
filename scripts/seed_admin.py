import os
import mysql.connector
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash

load_dotenv()


def get_db():
    return mysql.connector.connect(
        host=os.getenv("DB_HOST", "localhost"),
        user=os.getenv("DB_USER", "root"),
        password=os.getenv("DB_PASSWORD", ""),
        database=os.getenv("DB_NAME", "ncit_sis"),
        port=int(os.getenv("DB_PORT", "3306")),
    )


def main():
    name = os.getenv("SEED_ADMIN_NAME", "System Admin")
    email = os.getenv("SEED_ADMIN_EMAIL", "admin@ncit.edu.np")
    password = os.getenv("SEED_ADMIN_PASSWORD", "admin123")

    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT user_id FROM users WHERE email=%s", (email,))
    if cur.fetchone():
        print(f"Admin already exists: {email}")
        conn.close()
        return

    password_hash = generate_password_hash(password)
    cur.execute(
        "INSERT INTO users (full_name, email, password, role) VALUES (%s, %s, %s, 'admin')",
        (name, email, password_hash),
    )
    conn.commit()
    conn.close()
    print(f"Admin created: {email}")


if __name__ == "__main__":
    main()
