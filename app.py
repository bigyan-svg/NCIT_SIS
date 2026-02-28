from flask import Flask, render_template, request, redirect, url_for, session, flash, send_from_directory
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from dotenv import load_dotenv
import mysql.connector
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
import os
import re
import uuid
import secrets
import smtplib
import base64
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from urllib import parse as urllib_parse, request as urllib_request

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "dev_secret_key")
app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024  # 50 MB uploads

# ==========================================
# DATABASE CONNECTION
# ==========================================

def get_db():
    return mysql.connector.connect(
        host=os.getenv("DB_HOST", "localhost"),
        user=os.getenv("DB_USER", "root"),
        password=os.getenv("DB_PASSWORD", ""),
        database=os.getenv("DB_NAME", "ncit_sis"),
        port=int(os.getenv("DB_PORT", "3306"))
    )

# ==========================================
# HELPER FUNCTIONS
# ==========================================

def is_password_hashed(value):
    if not value:
        return False
    return (
        value.startswith("pbkdf2:")
        or value.startswith("scrypt:")
        or value.startswith("argon2:")
    )

def verify_password(stored, provided):
    if not stored:
        return False
    if is_password_hashed(stored):
        return check_password_hash(stored, provided)
    return stored == provided

def check_auth(role_required):
    if 'user_id' not in session: return False
    if session.get('role') != role_required: return False
    return True

def get_notices(role):
    conn = get_db()
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT * FROM notices WHERE target_role IN ('all', %s) ORDER BY date_posted DESC LIMIT 5", (role,))
    notices = cur.fetchall()
    conn.close()
    return notices

def calculate_grade_gpa(obtained, full):
    if full == 0: return 'F', 0.0
    percentage = (obtained / full) * 100
    
    if percentage >= 90: return 'A', 4.0
    elif percentage >= 85: return 'A-', 3.7
    elif percentage >= 80: return 'B+', 3.3
    elif percentage >= 75: return 'B', 3.0
    elif percentage >= 70: return 'B-', 2.7
    elif percentage >= 65: return 'C+', 2.3
    elif percentage >= 60: return 'C', 2.0
    elif percentage >= 55: return 'C-', 1.7
    elif percentage >= 50: return 'D+', 1.3
    elif percentage >= 45: return 'D', 1.0
    else: return 'F', 0.0

# ==========================================
# INPUT VALIDATION HELPERS
# ==========================================

PERSON_NAME_REGEX = re.compile(r"^[A-Za-z][A-Za-z .'-]*$")
DEPT_NAME_REGEX = re.compile(r"^[A-Za-z][A-Za-z0-9 &/.-]*$")
COURSE_NAME_REGEX = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 &().,/+-]*$")
COURSE_CODE_REGEX = re.compile(r"^[A-Z0-9][A-Z0-9-]{1,19}$")
ROLL_NO_REGEX = re.compile(r"^[A-Za-z0-9-]{2,50}$")
EMAIL_REGEX = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")
PHONE_REGEX = re.compile(r"^[0-9+ -]{7,20}$")
ISBN_REGEX = re.compile(r"^[0-9Xx-]{7,20}$")
ROOM_REGEX = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 .,#/-]{0,49}$")

ALLOWED_GENDERS = {'Male', 'Female', 'Other'}
SEMESTER_OPTIONS = ('1st', '2nd', '3rd', '4th', '5th', '6th', '7th', '8th')
ALLOWED_SEMESTERS = set(SEMESTER_OPTIONS)
ALLOWED_FEE_STATUS = {'Paid', 'Pending'}
ALLOWED_NOTICE_TARGET = {'all', 'student', 'teacher'}
ALLOWED_EXAM_TYPES = (
    'Unit Test 1',
    'Unit Test 2',
    'Mid Term',
    'Pre Board',
    'Final',
    'Assignment',
)
MAX_BULK_STUDENTS = 100
MAX_BULK_RESULTS = 200
MAX_ASSIGNMENT_TITLE_LENGTH = 200
MAX_ASSIGNMENT_NOTICE_LENGTH = 4000
MAX_ASSIGNMENT_DESCRIPTION_LENGTH = 8000
MAX_ASSIGNMENT_COMMENT_LENGTH = 2000
PASSWORD_RESET_OTP_LENGTH = int(os.getenv("PWD_RESET_OTP_LENGTH", "6") or "6")
PASSWORD_RESET_OTP_EXP_MINUTES = int(os.getenv("PWD_RESET_OTP_EXP_MINUTES", "10") or "10")
PASSWORD_RESET_MAX_VERIFY_ATTEMPTS = int(os.getenv("PWD_RESET_MAX_VERIFY_ATTEMPTS", "5") or "5")
PASSWORD_RESET_SEND_COOLDOWN_SECONDS = int(os.getenv("PWD_RESET_COOLDOWN_SECONDS", "60") or "60")
PASSWORD_RESET_MAX_SENDS_PER_IP_HOUR = int(os.getenv("PWD_RESET_MAX_SENDS_PER_IP_HOUR", "10") or "10")
PASSWORD_RESET_MAX_SENDS_PER_USER_HOUR = int(os.getenv("PWD_RESET_MAX_SENDS_PER_USER_HOUR", "5") or "5")
PASSWORD_RESET_ALLOW_LOCAL_TEST_CODE = os.getenv("PWD_RESET_ALLOW_LOCAL_TEST_CODE", "1").strip().lower() in {"1", "true", "yes", "on"}
MIN_ACADEMIC_YEAR = 2000
MAX_ACADEMIC_YEAR = 2100
DEFAULT_ACADEMIC_YEAR = date.today().year

UPLOAD_BASE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "uploads")
UPLOAD_ASSIGNMENTS_DIR = os.path.join(UPLOAD_BASE_DIR, "assignments")
UPLOAD_SUBMISSIONS_DIR = os.path.join(UPLOAD_BASE_DIR, "submissions")
UPLOAD_PROFILE_PHOTOS_DIR = os.path.join(UPLOAD_BASE_DIR, "profile_photos")
ALLOWED_PROFILE_PHOTO_EXTENSIONS = {"jpg", "jpeg", "png", "gif", "webp"}
AUTO_INCREMENT_PRIMARY_KEYS = {
    "assignment_comments": "comment_id",
    "assignment_submissions": "submission_id",
    "attendance": "attendance_id",
    "book_categories": "category_id",
    "borrows": "borrow_id",
    "courses": "course_id",
    "departments": "dept_id",
    "exam_schedule": "exam_id",
    "fees": "fee_id",
    "library_books": "book_id",
    "notices": "notice_id",
    "password_reset_otps": "otp_id",
    "student_enrollments": "enrollment_id",
    "student_results": "result_id",
    "teacher_assignments": "assignment_id",
    "teacher_courses": "assign_id",
    "users": "user_id",
}


def normalize_spaces(value):
    return " ".join((value or "").split())


def is_valid_name(value):
    value = normalize_spaces(value)
    return bool(value) and bool(PERSON_NAME_REGEX.fullmatch(value))


def is_valid_dept_name(value):
    value = normalize_spaces(value)
    return bool(value) and bool(DEPT_NAME_REGEX.fullmatch(value))


def is_valid_course_name(value):
    value = normalize_spaces(value)
    return bool(value) and bool(COURSE_NAME_REGEX.fullmatch(value))


def is_valid_course_code(value):
    return bool(COURSE_CODE_REGEX.fullmatch((value or "").strip().upper()))


def is_valid_roll_no(value):
    return bool(ROLL_NO_REGEX.fullmatch((value or "").strip().upper()))


def is_valid_email(value):
    return bool(EMAIL_REGEX.fullmatch((value or "").strip()))


def is_valid_phone(value):
    return bool(PHONE_REGEX.fullmatch((value or "").strip()))


def is_valid_isbn(value):
    return bool(ISBN_REGEX.fullmatch((value or "").strip()))


def is_valid_room(value):
    return bool(ROOM_REGEX.fullmatch(normalize_spaces(value)))


def parse_positive_int(value):
    try:
        parsed = int(value)
        if parsed <= 0:
            return None
        return parsed
    except (TypeError, ValueError):
        return None


def parse_academic_year(value):
    raw = str(value or "").strip()
    if not raw or not re.fullmatch(r"[0-9]{4}", raw):
        return None
    try:
        parsed = int(raw)
    except ValueError:
        return None
    if parsed < MIN_ACADEMIC_YEAR or parsed > MAX_ACADEMIC_YEAR:
        return None
    return parsed


def parse_non_negative_decimal(value):
    try:
        parsed = Decimal(str(value))
        if parsed < 0:
            return None
        return parsed
    except (TypeError, InvalidOperation, ValueError):
        return None


def parse_iso_date(value):
    value = (value or "").strip()
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None


def align_table_auto_increment(conn, table_name, id_column):
    """
    Align AUTO_INCREMENT with current data so new inserts continue from MAX(id)+1.
    If table is empty, next id becomes 1.
    """
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", table_name):
        return
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", id_column):
        return

    cur = conn.cursor()
    try:
        cur.execute(f"SELECT COALESCE(MAX({id_column}), 0) + 1 FROM {table_name}")
        row = cur.fetchone()
        next_id = int(row[0]) if row and row[0] else 1
        if next_id < 1:
            next_id = 1
        cur.execute(f"ALTER TABLE {table_name} AUTO_INCREMENT = {next_id}")
        conn.commit()
    finally:
        cur.close()


def align_auto_increment_for_table(conn, table_name):
    id_column = AUTO_INCREMENT_PRIMARY_KEYS.get(table_name)
    if not id_column:
        return
    align_table_auto_increment(conn, table_name, id_column)


def align_auto_increment_for_tables(conn, table_names):
    seen = set()
    for table_name in table_names:
        if table_name in seen:
            continue
        seen.add(table_name)
        align_auto_increment_for_table(conn, table_name)


def parse_iso_time(value):
    value = (value or "").strip()
    if not value:
        return None
    for fmt in ("%H:%M", "%H:%M:%S"):
        try:
            return datetime.strptime(value, fmt).time()
        except ValueError:
            continue
    return None


def normalize_mysql_time_value(value):
    if value is None:
        return None
    if hasattr(value, "hour") and hasattr(value, "minute"):
        return value
    if isinstance(value, timedelta):
        total_seconds = int(value.total_seconds())
        if total_seconds < 0:
            total_seconds = 0
        hours = (total_seconds // 3600) % 24
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60
        return datetime.strptime(f"{hours:02d}:{minutes:02d}:{seconds:02d}", "%H:%M:%S").time()
    if isinstance(value, str):
        return parse_iso_time(value)
    return None


def is_valid_date_of_birth(dob):
    if not dob:
        return False
    return date(1900, 1, 1) <= dob <= date.today()


def ensure_users_date_of_birth_column(conn):
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT 1
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'users'
              AND COLUMN_NAME = 'date_of_birth'
            LIMIT 1
        """)
        if cur.fetchone():
            return

        cur.execute("ALTER TABLE users ADD COLUMN date_of_birth DATE DEFAULT NULL AFTER semester")
        conn.commit()
    finally:
        cur.close()


def ensure_users_profile_photo_column(conn):
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT 1
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'users'
              AND COLUMN_NAME = 'profile_photo'
            LIMIT 1
        """)
        if cur.fetchone():
            return

        cur.execute("ALTER TABLE users ADD COLUMN profile_photo VARCHAR(255) NULL AFTER address")
        conn.commit()
    finally:
        cur.close()


def ensure_courses_credit_hour_column(conn):
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT 1
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'courses'
              AND COLUMN_NAME = 'credit_hour'
            LIMIT 1
        """)
        if cur.fetchone():
            return

        cur.execute("ALTER TABLE courses ADD COLUMN credit_hour DECIMAL(4,2) NOT NULL DEFAULT 3.00 AFTER course_code")
        conn.commit()
    finally:
        cur.close()


def constraint_exists(cur, table_name, constraint_name):
    cur.execute("""
        SELECT 1
        FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS
        WHERE TABLE_SCHEMA = DATABASE()
          AND TABLE_NAME = %s
          AND CONSTRAINT_NAME = %s
        LIMIT 1
    """, (table_name, constraint_name))
    return cur.fetchone() is not None


def index_exists(cur, table_name, index_name):
    cur.execute("""
        SELECT 1
        FROM INFORMATION_SCHEMA.STATISTICS
        WHERE TABLE_SCHEMA = DATABASE()
          AND TABLE_NAME = %s
          AND INDEX_NAME = %s
        LIMIT 1
    """, (table_name, index_name))
    return cur.fetchone() is not None


def ensure_student_results_metadata_columns(conn):
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT 1
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'student_results'
              AND COLUMN_NAME = 'teacher_id'
            LIMIT 1
        """)
        if not cur.fetchone():
            cur.execute("ALTER TABLE student_results ADD COLUMN teacher_id INT NULL AFTER course_id")

        cur.execute("""
            SELECT 1
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'student_results'
              AND COLUMN_NAME = 'academic_year'
            LIMIT 1
        """)
        if not cur.fetchone():
            cur.execute("ALTER TABLE student_results ADD COLUMN academic_year SMALLINT UNSIGNED NULL AFTER exam_type")

        cur.execute("""
            UPDATE student_results
            SET academic_year = %s
            WHERE academic_year IS NULL
               OR academic_year < %s
               OR academic_year > %s
        """, (DEFAULT_ACADEMIC_YEAR, MIN_ACADEMIC_YEAR, MAX_ACADEMIC_YEAR))
        cur.execute(
            f"""
            ALTER TABLE student_results
            MODIFY academic_year SMALLINT UNSIGNED NOT NULL DEFAULT {DEFAULT_ACADEMIC_YEAR}
            """
        )

        cur.execute("""
            UPDATE student_results r
            LEFT JOIN (
                SELECT course_id, MIN(teacher_id) AS teacher_id
                FROM teacher_courses
                GROUP BY course_id
            ) tc ON tc.course_id = r.course_id
            SET r.teacher_id = COALESCE(r.teacher_id, tc.teacher_id)
            WHERE r.teacher_id IS NULL
        """)

        if index_exists(cur, 'student_results', 'uq_student_result_exam') and not index_exists(cur, 'student_results', 'uq_student_result_exam_year'):
            cur.execute("ALTER TABLE student_results DROP INDEX uq_student_result_exam")
        if not index_exists(cur, 'student_results', 'uq_student_result_exam_year'):
            cur.execute("""
                ALTER TABLE student_results
                ADD UNIQUE KEY uq_student_result_exam_year (student_id, course_id, exam_type, academic_year)
            """)
        if not index_exists(cur, 'student_results', 'idx_student_results_teacher'):
            cur.execute("CREATE INDEX idx_student_results_teacher ON student_results (teacher_id)")
        if not index_exists(cur, 'student_results', 'idx_student_results_year'):
            cur.execute("CREATE INDEX idx_student_results_year ON student_results (academic_year)")

        if not constraint_exists(cur, 'student_results', 'chk_results_academic_year'):
            cur.execute(
                f"""
                ALTER TABLE student_results
                ADD CONSTRAINT chk_results_academic_year
                CHECK (academic_year >= {MIN_ACADEMIC_YEAR} AND academic_year <= {MAX_ACADEMIC_YEAR})
                """
            )
        if not constraint_exists(cur, 'student_results', 'fk_results_teacher'):
            cur.execute("""
                ALTER TABLE student_results
                ADD CONSTRAINT fk_results_teacher
                FOREIGN KEY (teacher_id) REFERENCES users(user_id)
                ON UPDATE CASCADE ON DELETE SET NULL
            """)

        conn.commit()
    finally:
        cur.close()


def ensure_reference_domain_tables(conn):
    cur = conn.cursor()
    try:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS ref_user_roles (
                role_code VARCHAR(20) PRIMARY KEY
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS ref_genders (
                gender_code VARCHAR(10) PRIMARY KEY
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS ref_semesters (
                semester_code VARCHAR(20) PRIMARY KEY
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS ref_notice_targets (
                target_code VARCHAR(20) PRIMARY KEY
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS ref_fee_statuses (
                status_code VARCHAR(20) PRIMARY KEY
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS ref_attendance_statuses (
                status_code VARCHAR(20) PRIMARY KEY
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS ref_exam_types (
                exam_type_code VARCHAR(50) PRIMARY KEY
            )
        """)

        cur.executemany(
            "INSERT IGNORE INTO ref_user_roles (role_code) VALUES (%s)",
            [('admin',), ('teacher',), ('student',)]
        )
        cur.executemany(
            "INSERT IGNORE INTO ref_genders (gender_code) VALUES (%s)",
            [('Male',), ('Female',), ('Other',)]
        )
        cur.executemany(
            "INSERT IGNORE INTO ref_semesters (semester_code) VALUES (%s)",
            [(s,) for s in sorted(ALLOWED_SEMESTERS)]
        )
        cur.executemany(
            "INSERT IGNORE INTO ref_notice_targets (target_code) VALUES (%s)",
            [('all',), ('student',), ('teacher',)]
        )
        cur.executemany(
            "INSERT IGNORE INTO ref_fee_statuses (status_code) VALUES (%s)",
            [('Paid',), ('Pending',)]
        )
        cur.executemany(
            "INSERT IGNORE INTO ref_attendance_statuses (status_code) VALUES (%s)",
            [('Present',), ('Absent',)]
        )
        cur.executemany(
            "INSERT IGNORE INTO ref_exam_types (exam_type_code) VALUES (%s)",
            [(exam_name,) for exam_name in ALLOWED_EXAM_TYPES]
        )

        # Keep values inside normalized domains before attaching foreign keys.
        cur.execute("""
            UPDATE users
            SET role = LOWER(TRIM(role))
            WHERE role IS NOT NULL
        """)
        cur.execute("""
            UPDATE users
            SET role = 'student'
            WHERE role NOT IN ('admin', 'teacher', 'student')
               OR role IS NULL
               OR TRIM(role) = ''
        """)
        cur.execute("""
            UPDATE users
            SET gender = CASE
                WHEN gender IS NULL OR TRIM(gender) = '' THEN NULL
                WHEN LOWER(TRIM(gender)) = 'male' THEN 'Male'
                WHEN LOWER(TRIM(gender)) = 'female' THEN 'Female'
                WHEN LOWER(TRIM(gender)) = 'other' THEN 'Other'
                ELSE NULL
            END
        """)
        cur.execute("""
            UPDATE users
            SET semester = NULL
            WHERE semester IS NOT NULL AND TRIM(semester) = ''
        """)
        cur.execute("""
            UPDATE notices
            SET target_role = 'all'
            WHERE target_role IS NULL
               OR TRIM(target_role) = ''
               OR target_role NOT IN ('all', 'student', 'teacher')
        """)
        cur.execute("""
            UPDATE fees
            SET status = 'Pending'
            WHERE status IS NULL
               OR TRIM(status) = ''
               OR status NOT IN ('Paid', 'Pending')
        """)
        cur.execute("""
            UPDATE attendance
            SET status = 'Absent'
            WHERE status IS NULL
               OR TRIM(status) = ''
               OR status NOT IN ('Present', 'Absent')
        """)
        cur.execute("""
            UPDATE student_results
            SET exam_type = 'Final'
            WHERE exam_type IS NULL OR TRIM(exam_type) = ''
        """)
        cur.execute("""
            INSERT IGNORE INTO ref_exam_types (exam_type_code)
            SELECT DISTINCT exam_type
            FROM student_results
            WHERE exam_type IS NOT NULL AND TRIM(exam_type) <> ''
        """)

        cur.execute("ALTER TABLE users MODIFY role VARCHAR(20) NOT NULL")
        cur.execute("ALTER TABLE users MODIFY gender VARCHAR(10) NULL")
        cur.execute("ALTER TABLE users MODIFY semester VARCHAR(20) NULL")
        cur.execute("ALTER TABLE notices MODIFY target_role VARCHAR(20) NOT NULL DEFAULT 'all'")
        cur.execute("ALTER TABLE fees MODIFY status VARCHAR(20) NOT NULL DEFAULT 'Pending'")
        cur.execute("ALTER TABLE attendance MODIFY status VARCHAR(20) NOT NULL")
        cur.execute("ALTER TABLE student_results MODIFY exam_type VARCHAR(50) NOT NULL DEFAULT 'Final'")

        if not constraint_exists(cur, 'users', 'fk_users_role_domain'):
            cur.execute("""
                ALTER TABLE users
                ADD CONSTRAINT fk_users_role_domain
                FOREIGN KEY (role) REFERENCES ref_user_roles(role_code)
                ON UPDATE CASCADE ON DELETE RESTRICT
            """)

        if not constraint_exists(cur, 'users', 'fk_users_gender_domain'):
            cur.execute("""
                ALTER TABLE users
                ADD CONSTRAINT fk_users_gender_domain
                FOREIGN KEY (gender) REFERENCES ref_genders(gender_code)
                ON UPDATE CASCADE ON DELETE SET NULL
            """)

        if not constraint_exists(cur, 'users', 'fk_users_semester_domain'):
            cur.execute("""
                ALTER TABLE users
                ADD CONSTRAINT fk_users_semester_domain
                FOREIGN KEY (semester) REFERENCES ref_semesters(semester_code)
                ON UPDATE CASCADE ON DELETE SET NULL
            """)

        if not constraint_exists(cur, 'notices', 'fk_notices_target_domain'):
            cur.execute("""
                ALTER TABLE notices
                ADD CONSTRAINT fk_notices_target_domain
                FOREIGN KEY (target_role) REFERENCES ref_notice_targets(target_code)
                ON UPDATE CASCADE ON DELETE RESTRICT
            """)

        if not constraint_exists(cur, 'fees', 'fk_fees_status_domain'):
            cur.execute("""
                ALTER TABLE fees
                ADD CONSTRAINT fk_fees_status_domain
                FOREIGN KEY (status) REFERENCES ref_fee_statuses(status_code)
                ON UPDATE CASCADE ON DELETE RESTRICT
            """)

        if not constraint_exists(cur, 'attendance', 'fk_attendance_status_domain'):
            cur.execute("""
                ALTER TABLE attendance
                ADD CONSTRAINT fk_attendance_status_domain
                FOREIGN KEY (status) REFERENCES ref_attendance_statuses(status_code)
                ON UPDATE CASCADE ON DELETE RESTRICT
            """)

        if not constraint_exists(cur, 'student_results', 'fk_results_exam_type_domain'):
            cur.execute("""
                ALTER TABLE student_results
                ADD CONSTRAINT fk_results_exam_type_domain
                FOREIGN KEY (exam_type) REFERENCES ref_exam_types(exam_type_code)
                ON UPDATE CASCADE ON DELETE RESTRICT
            """)

        conn.commit()
    finally:
        cur.close()


def ensure_student_results_grading_triggers(conn):
    cur = conn.cursor()
    try:
        cur.execute("DROP TRIGGER IF EXISTS trg_student_results_before_insert")
        cur.execute("DROP TRIGGER IF EXISTS trg_student_results_before_update")

        cur.execute("""
            CREATE TRIGGER trg_student_results_before_insert
            BEFORE INSERT ON student_results
            FOR EACH ROW
            BEGIN
                DECLARE pct DECIMAL(8,4);

                IF NEW.full_marks IS NULL OR NEW.full_marks <= 0 THEN
                    SET NEW.full_marks = 100.00;
                END IF;
                IF NEW.marks_obtained IS NULL OR NEW.marks_obtained < 0 THEN
                    SET NEW.marks_obtained = 0.00;
                END IF;
                IF NEW.marks_obtained > NEW.full_marks THEN
                    SET NEW.marks_obtained = NEW.full_marks;
                END IF;

                SET pct = (NEW.marks_obtained / NEW.full_marks) * 100;

                IF pct >= 90 THEN SET NEW.grade = 'A'; SET NEW.gpa = 4.0;
                ELSEIF pct >= 85 THEN SET NEW.grade = 'A-'; SET NEW.gpa = 3.7;
                ELSEIF pct >= 80 THEN SET NEW.grade = 'B+'; SET NEW.gpa = 3.3;
                ELSEIF pct >= 75 THEN SET NEW.grade = 'B'; SET NEW.gpa = 3.0;
                ELSEIF pct >= 70 THEN SET NEW.grade = 'B-'; SET NEW.gpa = 2.7;
                ELSEIF pct >= 65 THEN SET NEW.grade = 'C+'; SET NEW.gpa = 2.3;
                ELSEIF pct >= 60 THEN SET NEW.grade = 'C'; SET NEW.gpa = 2.0;
                ELSEIF pct >= 55 THEN SET NEW.grade = 'C-'; SET NEW.gpa = 1.7;
                ELSEIF pct >= 50 THEN SET NEW.grade = 'D+'; SET NEW.gpa = 1.3;
                ELSEIF pct >= 45 THEN SET NEW.grade = 'D'; SET NEW.gpa = 1.0;
                ELSE SET NEW.grade = 'F'; SET NEW.gpa = 0.0;
                END IF;
            END
        """)

        cur.execute("""
            CREATE TRIGGER trg_student_results_before_update
            BEFORE UPDATE ON student_results
            FOR EACH ROW
            BEGIN
                DECLARE pct DECIMAL(8,4);

                IF NEW.full_marks IS NULL OR NEW.full_marks <= 0 THEN
                    SET NEW.full_marks = 100.00;
                END IF;
                IF NEW.marks_obtained IS NULL OR NEW.marks_obtained < 0 THEN
                    SET NEW.marks_obtained = 0.00;
                END IF;
                IF NEW.marks_obtained > NEW.full_marks THEN
                    SET NEW.marks_obtained = NEW.full_marks;
                END IF;

                SET pct = (NEW.marks_obtained / NEW.full_marks) * 100;

                IF pct >= 90 THEN SET NEW.grade = 'A'; SET NEW.gpa = 4.0;
                ELSEIF pct >= 85 THEN SET NEW.grade = 'A-'; SET NEW.gpa = 3.7;
                ELSEIF pct >= 80 THEN SET NEW.grade = 'B+'; SET NEW.gpa = 3.3;
                ELSEIF pct >= 75 THEN SET NEW.grade = 'B'; SET NEW.gpa = 3.0;
                ELSEIF pct >= 70 THEN SET NEW.grade = 'B-'; SET NEW.gpa = 2.7;
                ELSEIF pct >= 65 THEN SET NEW.grade = 'C+'; SET NEW.gpa = 2.3;
                ELSEIF pct >= 60 THEN SET NEW.grade = 'C'; SET NEW.gpa = 2.0;
                ELSEIF pct >= 55 THEN SET NEW.grade = 'C-'; SET NEW.gpa = 1.7;
                ELSEIF pct >= 50 THEN SET NEW.grade = 'D+'; SET NEW.gpa = 1.3;
                ELSEIF pct >= 45 THEN SET NEW.grade = 'D'; SET NEW.gpa = 1.0;
                ELSE SET NEW.grade = 'F'; SET NEW.gpa = 0.0;
                END IF;
            END
        """)

        conn.commit()
    finally:
        cur.close()


def ensure_assignment_tables(conn):
    cur = conn.cursor()
    try:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS teacher_assignments (
                assignment_id INT AUTO_INCREMENT PRIMARY KEY,
                course_id INT NOT NULL,
                teacher_id INT NOT NULL,
                title VARCHAR(200) NOT NULL,
                notice TEXT NULL,
                description TEXT NULL,
                due_date DATE NULL,
                due_time TIME NULL,
                attachment_path VARCHAR(255) NULL,
                attachment_name VARCHAR(255) NULL,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                INDEX idx_teacher_assignments_course (course_id),
                INDEX idx_teacher_assignments_teacher (teacher_id),
                CONSTRAINT fk_teacher_assignments_course
                    FOREIGN KEY (course_id) REFERENCES courses(course_id) ON DELETE CASCADE,
                CONSTRAINT fk_teacher_assignments_teacher
                    FOREIGN KEY (teacher_id) REFERENCES users(user_id) ON DELETE CASCADE
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS assignment_submissions (
                submission_id INT AUTO_INCREMENT PRIMARY KEY,
                assignment_id INT NOT NULL,
                student_id INT NOT NULL,
                status ENUM('not_submitted', 'turned_in', 'submitted') NOT NULL DEFAULT 'not_submitted',
                submission_path VARCHAR(255) NULL,
                submission_name VARCHAR(255) NULL,
                submitted_at DATETIME NULL,
                is_late TINYINT(1) NOT NULL DEFAULT 0,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                UNIQUE KEY uq_assignment_student (assignment_id, student_id),
                INDEX idx_assignment_submissions_student (student_id),
                CONSTRAINT fk_assignment_submissions_assignment
                    FOREIGN KEY (assignment_id) REFERENCES teacher_assignments(assignment_id) ON DELETE CASCADE,
                CONSTRAINT fk_assignment_submissions_student
                    FOREIGN KEY (student_id) REFERENCES users(user_id) ON DELETE CASCADE
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS assignment_comments (
                comment_id INT AUTO_INCREMENT PRIMARY KEY,
                submission_id INT NOT NULL,
                sender_id INT NOT NULL,
                sender_role ENUM('teacher', 'student') NOT NULL,
                comment_text TEXT NOT NULL,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_assignment_comments_submission (submission_id),
                CONSTRAINT fk_assignment_comments_submission
                    FOREIGN KEY (submission_id) REFERENCES assignment_submissions(submission_id) ON DELETE CASCADE,
                CONSTRAINT fk_assignment_comments_sender
                    FOREIGN KEY (sender_id) REFERENCES users(user_id) ON DELETE CASCADE
            )
        """)

        cur.execute("""
            SELECT 1
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'teacher_assignments'
              AND COLUMN_NAME = 'due_time'
            LIMIT 1
        """)
        if not cur.fetchone():
            cur.execute("ALTER TABLE teacher_assignments ADD COLUMN due_time TIME NULL AFTER due_date")

        conn.commit()
    finally:
        cur.close()


def ensure_upload_dirs():
    os.makedirs(UPLOAD_ASSIGNMENTS_DIR, exist_ok=True)
    os.makedirs(UPLOAD_SUBMISSIONS_DIR, exist_ok=True)
    os.makedirs(UPLOAD_PROFILE_PHOTOS_DIR, exist_ok=True)


def save_uploaded_file(uploaded_file, target_dir):
    if not uploaded_file:
        return None, None
    original_name = (uploaded_file.filename or "").strip()
    if not original_name:
        return None, None
    safe_name = secure_filename(original_name)
    if not safe_name:
        return None, None
    ensure_upload_dirs()
    unique_name = f"{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex}_{safe_name}"
    destination = os.path.join(target_dir, unique_name)
    uploaded_file.save(destination)
    return unique_name, original_name


def validate_profile_photo_upload(uploaded_file):
    if not uploaded_file:
        return None
    original_name = (uploaded_file.filename or "").strip()
    if not original_name:
        return None

    safe_name = secure_filename(original_name)
    if not safe_name or "." not in safe_name:
        return "Profile photo filename is invalid."

    extension = safe_name.rsplit(".", 1)[1].lower()
    if extension not in ALLOWED_PROFILE_PHOTO_EXTENSIONS:
        return "Profile photo must be JPG, JPEG, PNG, GIF, or WEBP."

    mimetype = (uploaded_file.mimetype or "").lower()
    if mimetype and not mimetype.startswith("image/"):
        return "Profile photo must be an image file."

    return None


def save_profile_photo(uploaded_file):
    validation_error = validate_profile_photo_upload(uploaded_file)
    if validation_error:
        return None, None, validation_error
    stored_name, original_name = save_uploaded_file(uploaded_file, UPLOAD_PROFILE_PHOTOS_DIR)
    return stored_name, original_name, None


def remove_uploaded_file_if_exists(target_dir, file_name):
    if not file_name:
        return
    file_path = os.path.join(target_dir, file_name)
    if os.path.isfile(file_path):
        try:
            os.remove(file_path)
        except OSError:
            pass


def sanitize_assignment_text(value, max_length):
    return (value or "").strip()[:max_length]


def compute_submission_late_flag(due_date, due_time, submitted_at):
    if not due_date or not submitted_at:
        return 0

    normalized_due_time = normalize_mysql_time_value(due_time)
    if normalized_due_time is None:
        normalized_due_time = datetime.strptime("23:59:59", "%H:%M:%S").time()

    due_at = datetime.combine(due_date, normalized_due_time)
    return 1 if submitted_at > due_at else 0


def get_or_create_assignment_submission(conn, cur, assignment_id, student_id):
    align_auto_increment_for_table(conn, "assignment_submissions")
    cur.execute("""
        INSERT INTO assignment_submissions (assignment_id, student_id, status)
        VALUES (%s, %s, 'not_submitted')
        ON DUPLICATE KEY UPDATE assignment_id = VALUES(assignment_id)
    """, (assignment_id, student_id))
    cur.execute("""
        SELECT submission_id, assignment_id, student_id, status, submission_path, submission_name,
               submitted_at, is_late, created_at, updated_at
        FROM assignment_submissions
        WHERE assignment_id = %s AND student_id = %s
    """, (assignment_id, student_id))
    return cur.fetchone()


def ensure_password_reset_table(conn):
    cur = conn.cursor()
    try:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS password_reset_otps (
                otp_id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT NOT NULL,
                delivery_channel VARCHAR(20) NOT NULL,
                destination VARCHAR(150) NOT NULL,
                otp_hash VARCHAR(255) NOT NULL,
                expires_at DATETIME NOT NULL,
                attempts INT NOT NULL DEFAULT 0,
                verified_at DATETIME NULL,
                used_at DATETIME NULL,
                sent_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                request_ip VARCHAR(45) NULL,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_password_reset_user (user_id),
                INDEX idx_password_reset_destination (destination),
                CONSTRAINT fk_password_reset_otps_user
                    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
            )
        """)

        cur.execute("""
            SELECT 1
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'password_reset_otps'
              AND COLUMN_NAME = 'sent_at'
            LIMIT 1
        """)
        if not cur.fetchone():
            cur.execute("ALTER TABLE password_reset_otps ADD COLUMN sent_at DATETIME NULL AFTER used_at")
            cur.execute("UPDATE password_reset_otps SET sent_at = created_at WHERE sent_at IS NULL")
            cur.execute("ALTER TABLE password_reset_otps MODIFY sent_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP")

        cur.execute("""
            SELECT 1
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'password_reset_otps'
              AND COLUMN_NAME = 'request_ip'
            LIMIT 1
        """)
        if not cur.fetchone():
            cur.execute("ALTER TABLE password_reset_otps ADD COLUMN request_ip VARCHAR(45) NULL AFTER sent_at")

        if not index_exists(cur, 'password_reset_otps', 'idx_password_reset_ip_sent'):
            cur.execute("CREATE INDEX idx_password_reset_ip_sent ON password_reset_otps (request_ip, sent_at)")

        if not index_exists(cur, 'password_reset_otps', 'idx_password_reset_user_sent'):
            cur.execute("CREATE INDEX idx_password_reset_user_sent ON password_reset_otps (user_id, sent_at)")

        cur.execute("""
            DELETE FROM password_reset_otps
            WHERE used_at IS NOT NULL
               OR expires_at < (NOW() - INTERVAL 1 DAY)
        """)
        conn.commit()
        align_auto_increment_for_table(conn, "password_reset_otps")
    finally:
        cur.close()


def normalize_phone_for_match(value):
    return re.sub(r"[ -]", "", (value or "").strip())


def normalize_email_for_match(value):
    return (value or "").strip().lower()


def get_password_reset_delivery_candidates(user_row, preferred_channel):
    candidates = []
    seen = set()

    email = normalize_email_for_match(user_row.get('email'))
    phone = (user_row.get('contact_no') or '').strip()

    ordered_channels = ['email', 'phone'] if preferred_channel == 'email' else ['phone', 'email']
    for channel in ordered_channels:
        destination = email if channel == 'email' else phone
        if not destination:
            continue
        is_valid = is_valid_email(destination) if channel == 'email' else is_valid_phone(destination)
        if not is_valid:
            continue
        key = (channel, normalize_phone_for_match(destination) if channel == 'phone' else destination)
        if key in seen:
            continue
        seen.add(key)
        candidates.append({'channel': channel, 'destination': destination})

    return candidates


def create_password_reset_otp_record(conn, user_id, delivery_channel, destination, request_ip, otp_code=None):
    otp_code = (otp_code or "").strip() or generate_numeric_otp(PASSWORD_RESET_OTP_LENGTH)
    otp_hash = generate_password_hash(otp_code)
    expires_at = datetime.now() + timedelta(minutes=PASSWORD_RESET_OTP_EXP_MINUTES)

    cur = conn.cursor()
    try:
        align_auto_increment_for_table(conn, "password_reset_otps")
        cur.execute("""
            INSERT INTO password_reset_otps
            (user_id, delivery_channel, destination, otp_hash, expires_at, attempts, request_ip, sent_at)
            VALUES (%s, %s, %s, %s, %s, 0, %s, NOW())
        """, (user_id, delivery_channel, destination, otp_hash, expires_at, request_ip))
        otp_id = cur.lastrowid
        conn.commit()
        return otp_id, otp_code
    except mysql.connector.Error:
        conn.rollback()
        raise
    finally:
        cur.close()


def refresh_password_reset_otp_record(
    conn,
    otp_id,
    user_id,
    delivery_channel,
    destination,
    request_ip,
    otp_code=None,
):
    otp_code = (otp_code or "").strip() or generate_numeric_otp(PASSWORD_RESET_OTP_LENGTH)
    new_hash = generate_password_hash(otp_code)
    new_expiry = datetime.now() + timedelta(minutes=PASSWORD_RESET_OTP_EXP_MINUTES)

    cur = conn.cursor()
    try:
        cur.execute("""
            UPDATE password_reset_otps
            SET delivery_channel = %s,
                destination = %s,
                otp_hash = %s,
                expires_at = %s,
                attempts = 0,
                verified_at = NULL,
                used_at = NULL,
                request_ip = %s,
                sent_at = NOW()
            WHERE otp_id = %s AND user_id = %s
        """, (delivery_channel, destination, new_hash, new_expiry, request_ip, otp_id, user_id))
        conn.commit()
        return otp_code
    except mysql.connector.Error:
        conn.rollback()
        raise
    finally:
        cur.close()


def create_password_reset_otp_with_fallback(conn, user_id, candidates, request_ip):
    if not candidates:
        return False, None, None, None, "No valid email/phone destination is available for this account.", 0

    cur = conn.cursor(dictionary=True)
    send_errors = []
    rate_limit_message = None
    rate_cooldown = 0

    try:
        for candidate in candidates:
            delivery_channel = candidate['channel']
            destination = candidate['destination']

            allowed, rate_msg, cooldown = validate_password_reset_send_rate(
                conn,
                user_id,
                destination,
                request_ip,
            )
            if not allowed:
                if rate_limit_message is None:
                    rate_limit_message = rate_msg
                    rate_cooldown = cooldown
                continue

            otp_id, otp_code = create_password_reset_otp_record(
                conn,
                user_id,
                delivery_channel,
                destination,
                request_ip,
            )

            sent, error_message = dispatch_password_reset_code(delivery_channel, destination, otp_code)
            if sent:
                return True, otp_id, delivery_channel, destination, None, 0

            cur.execute("DELETE FROM password_reset_otps WHERE otp_id = %s", (otp_id,))
            conn.commit()
            align_auto_increment_for_table(conn, "password_reset_otps")
            send_errors.append(error_message or f"Unable to send code via {delivery_channel}.")
    finally:
        cur.close()

    if send_errors:
        if len(send_errors) == 1:
            return False, None, None, None, send_errors[0], 0
        return False, None, None, None, f"Delivery failed. {send_errors[0]}", 0
    if rate_limit_message:
        return False, None, None, None, rate_limit_message, rate_cooldown
    return False, None, None, None, "Unable to deliver verification code.", 0


def resend_password_reset_otp_with_fallback(conn, otp_id, user_id, candidates, request_ip):
    if not candidates:
        return False, None, None, "No valid email/phone destination is available for this account.", 0

    send_errors = []
    rate_limit_message = None
    rate_cooldown = 0

    for candidate in candidates:
        delivery_channel = candidate['channel']
        destination = candidate['destination']

        allowed, rate_msg, cooldown = validate_password_reset_send_rate(
            conn,
            user_id,
            destination,
            request_ip,
        )
        if not allowed:
            if rate_limit_message is None:
                rate_limit_message = rate_msg
                rate_cooldown = cooldown
            continue

        otp_code = generate_numeric_otp(PASSWORD_RESET_OTP_LENGTH)
        sent, error_message = dispatch_password_reset_code(delivery_channel, destination, otp_code)
        if not sent:
            send_errors.append(error_message or f"Unable to send code via {delivery_channel}.")
            continue

        refresh_password_reset_otp_record(
            conn,
            otp_id,
            user_id,
            delivery_channel,
            destination,
            request_ip,
            otp_code=otp_code,
        )
        return True, delivery_channel, destination, None, 0

    if send_errors:
        if len(send_errors) == 1:
            return False, None, None, send_errors[0], 0
        return False, None, None, f"Delivery failed. {send_errors[0]}", 0
    if rate_limit_message:
        return False, None, None, rate_limit_message, rate_cooldown
    return False, None, None, "Unable to resend verification code.", 0


def generate_numeric_otp(length=6):
    if length <= 0:
        length = 6
    return "".join(str(secrets.randbelow(10)) for _ in range(length))


def mask_destination(destination, channel):
    destination = (destination or "").strip()
    if not destination:
        return ""
    if channel == 'email' and '@' in destination:
        username, domain = destination.split('@', 1)
        if len(username) <= 2:
            masked_user = username[0] + "*" * max(0, len(username) - 1)
        else:
            masked_user = username[0] + "*" * (len(username) - 2) + username[-1]
        return f"{masked_user}@{domain}"

    compact = normalize_phone_for_match(destination)
    if len(compact) <= 4:
        return "*" * len(compact)
    return "*" * (len(compact) - 4) + compact[-4:]


def send_password_reset_email(to_email, otp_code):
    smtp_host = os.getenv("SMTP_HOST", "").strip()
    smtp_port = int(os.getenv("SMTP_PORT", "587") or "587")
    smtp_user = os.getenv("SMTP_USER", "").strip()
    smtp_password = os.getenv("SMTP_PASSWORD", "").strip()
    smtp_from = os.getenv("SMTP_FROM", smtp_user).strip()
    smtp_use_tls = os.getenv("SMTP_USE_TLS", "1").strip().lower() in {"1", "true", "yes", "on"}

    if not smtp_host or not smtp_from:
        return False, "Email service is not configured yet."
    if not smtp_password or smtp_password.upper().startswith("CHANGE_ME"):
        return False, "Set SMTP_PASSWORD in .env (for Gmail, use an App Password)."

    subject = "NCIT SIS Password Reset Code"
    body = (
        f"Your NCIT SIS password reset code is: {otp_code}\n\n"
        f"This code expires in {PASSWORD_RESET_OTP_EXP_MINUTES} minutes.\n"
        "If you did not request this, please ignore this message."
    )

    message = MIMEMultipart()
    message["From"] = smtp_from
    message["To"] = to_email
    message["Subject"] = subject
    message.attach(MIMEText(body, "plain"))

    try:
        with smtplib.SMTP(smtp_host, smtp_port, timeout=20) as server:
            if smtp_use_tls:
                server.starttls()
            if smtp_user:
                server.login(smtp_user, smtp_password)
            server.sendmail(smtp_from, [to_email], message.as_string())
        return True, None
    except Exception as e:
        error_text = str(e)
        if "535" in error_text or "Username and Password not accepted" in error_text:
            return False, "SMTP login failed. For Gmail, use a 16-character App Password in SMTP_PASSWORD."
        return False, f"Failed to send email code: {e}"


def send_password_reset_sms(phone_no, otp_code):
    account_sid = os.getenv("TWILIO_ACCOUNT_SID", "").strip()
    auth_token = os.getenv("TWILIO_AUTH_TOKEN", "").strip()
    from_number = os.getenv("TWILIO_FROM_NUMBER", "").strip()

    if not account_sid or not auth_token or not from_number:
        return False, "SMS service is not configured yet."

    url = f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json"
    message_body = (
        f"NCIT SIS reset code: {otp_code}. "
        f"Expires in {PASSWORD_RESET_OTP_EXP_MINUTES} minutes. "
        "Do not share this code."
    )
    payload = urllib_parse.urlencode({
        "From": from_number,
        "To": phone_no,
        "Body": message_body,
    }).encode("utf-8")

    auth_value = base64.b64encode(f"{account_sid}:{auth_token}".encode("utf-8")).decode("utf-8")
    req = urllib_request.Request(url, data=payload, method="POST")
    req.add_header("Authorization", f"Basic {auth_value}")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")

    try:
        with urllib_request.urlopen(req, timeout=20) as response:
            if 200 <= response.status < 300:
                return True, None
            return False, f"SMS provider returned status {response.status}."
    except Exception as e:
        return False, f"Failed to send SMS code: {e}"


def dispatch_password_reset_code(channel, destination, otp_code):
    if channel == 'email':
        return send_password_reset_email(destination, otp_code)
    if channel == 'phone':
        return send_password_reset_sms(destination, otp_code)
    return False, "Unsupported delivery channel."


def clear_password_reset_session():
    for key in [
        'pwd_reset_otp_id',
        'pwd_reset_user_id',
        'pwd_reset_verified_otp_id',
        'pwd_reset_channel',
        'pwd_reset_destination',
    ]:
        session.pop(key, None)


def get_request_ip():
    forwarded_for = (request.headers.get("X-Forwarded-For") or "").split(",")[0].strip()
    if forwarded_for:
        return forwarded_for[:45]
    return (request.remote_addr or "unknown")[:45]


def get_otp_resend_cooldown_seconds(sent_at):
    if not sent_at:
        return 0
    elapsed = int((datetime.now() - sent_at).total_seconds())
    remaining = PASSWORD_RESET_SEND_COOLDOWN_SECONDS - elapsed
    return max(0, remaining)


def validate_password_reset_send_rate(conn, user_id, destination, request_ip):
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute("""
            SELECT sent_at
            FROM password_reset_otps
            WHERE user_id = %s AND destination = %s
            ORDER BY sent_at DESC
            LIMIT 1
        """, (user_id, destination))
        latest = cur.fetchone()
        cooldown = get_otp_resend_cooldown_seconds(latest['sent_at']) if latest else 0
        if cooldown > 0:
            return False, f"Please wait {cooldown} seconds before requesting another code.", cooldown

        cur.execute("""
            SELECT COUNT(*) AS cnt
            FROM password_reset_otps
            WHERE request_ip = %s
              AND sent_at >= (NOW() - INTERVAL 1 HOUR)
        """, (request_ip,))
        ip_cnt = int(cur.fetchone()['cnt'] or 0)
        if ip_cnt >= PASSWORD_RESET_MAX_SENDS_PER_IP_HOUR:
            return False, "Too many reset requests from this network. Try again after 1 hour.", 0

        cur.execute("""
            SELECT COUNT(*) AS cnt
            FROM password_reset_otps
            WHERE user_id = %s
              AND sent_at >= (NOW() - INTERVAL 1 HOUR)
        """, (user_id,))
        user_cnt = int(cur.fetchone()['cnt'] or 0)
        if user_cnt >= PASSWORD_RESET_MAX_SENDS_PER_USER_HOUR:
            return False, "Too many reset requests for this account. Try again after 1 hour.", 0

        return True, None, 0
    finally:
        cur.close()


DB_NORMALIZATION_DONE = False
DB_NORMALIZATION_ERROR = None


def ensure_database_normalization_once():
    global DB_NORMALIZATION_DONE
    if DB_NORMALIZATION_DONE:
        return

    conn = get_db()
    try:
        ensure_users_date_of_birth_column(conn)
        ensure_users_profile_photo_column(conn)
        ensure_courses_credit_hour_column(conn)
        ensure_student_results_metadata_columns(conn)
        ensure_assignment_tables(conn)
        ensure_password_reset_table(conn)
        ensure_reference_domain_tables(conn)
        ensure_student_results_grading_triggers(conn)
        DB_NORMALIZATION_DONE = True
    finally:
        conn.close()


# ==========================================
# AUTHENTICATION
# ==========================================


@app.before_request
def bootstrap_normalized_schema():
    global DB_NORMALIZATION_ERROR
    if DB_NORMALIZATION_DONE or DB_NORMALIZATION_ERROR:
        return
    try:
        ensure_database_normalization_once()
    except mysql.connector.Error as e:
        DB_NORMALIZATION_ERROR = str(e)
        app.logger.error("Schema normalization failed: %s", e)

@app.route('/')
def home():
    if 'user_id' in session:
        return redirect(url_for(f"{session['role']}_dashboard"))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        
        conn = get_db()
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT user_id, full_name, role, password FROM users WHERE email=%s", (email,))
        user = cur.fetchone()
        
        if user and verify_password(user['password'], password):
            if not is_password_hashed(user['password']):
                new_hash = generate_password_hash(password)
                cur.execute("UPDATE users SET password=%s WHERE user_id=%s", (new_hash, user['user_id']))
                conn.commit()
            session['user_id'] = user['user_id']
            session['name'] = user['full_name']
            session['role'] = user['role']
            conn.close()
            return redirect(url_for(f"{user['role']}_dashboard"))
        else:
            conn.close()
            flash("Invalid Credentials! Please try again.")
            
    return render_template('login.html')


@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    entered_identifier = (request.form.get('identifier') or '').strip() if request.method == 'POST' else ''

    if request.method == 'POST':
        if not entered_identifier:
            flash("Enter your registered email or phone number.", "warning")
            return render_template('forgot_password.html', entered_identifier=entered_identifier)

        is_email_input = '@' in entered_identifier
        normalized_email = normalize_email_for_match(entered_identifier)
        normalized_phone = normalize_phone_for_match(entered_identifier)

        if is_email_input and not is_valid_email(normalized_email):
            flash("Please enter a valid email address.", "warning")
            return render_template('forgot_password.html', entered_identifier=entered_identifier)
        if not is_email_input and not is_valid_phone(entered_identifier):
            flash("Please enter a valid phone number.", "warning")
            return render_template('forgot_password.html', entered_identifier=entered_identifier)

        conn = get_db()
        try:
            ensure_password_reset_table(conn)
        except mysql.connector.Error as e:
            conn.close()
            flash(f"Database error while preparing password reset: {e}", "danger")
            return render_template('forgot_password.html', entered_identifier=entered_identifier)

        cur = conn.cursor(dictionary=True)
        if is_email_input:
            cur.execute("""
                SELECT user_id, full_name, email, contact_no
                FROM users
                WHERE LOWER(email) = %s
                LIMIT 1
            """, (normalized_email,))
        else:
            cur.execute("""
                SELECT user_id, full_name, email, contact_no
                FROM users
                WHERE REPLACE(REPLACE(TRIM(contact_no), ' ', ''), '-', '') = %s
                LIMIT 1
            """, (normalized_phone,))
        user = cur.fetchone()

        if not user:
            conn.close()
            flash("No user account found with the provided email/phone.", "danger")
            return render_template('forgot_password.html', entered_identifier=entered_identifier)

        preferred_channel = 'email' if is_email_input else 'phone'
        candidates = get_password_reset_delivery_candidates(user, preferred_channel)
        if PASSWORD_RESET_ALLOW_LOCAL_TEST_CODE:
            # In local test mode, stick to the entered channel to avoid confusing fallback errors.
            candidates = candidates[:1]
        if not candidates:
            conn.close()
            flash("No valid email or phone destination found for this account.", "danger")
            return render_template('forgot_password.html', entered_identifier=entered_identifier)

        request_ip = get_request_ip()
        try:
            sent, otp_id, delivery_channel, destination, error_message, cooldown = create_password_reset_otp_with_fallback(
                conn,
                user['user_id'],
                candidates,
                request_ip,
            )
        except mysql.connector.Error as e:
            conn.rollback()
            conn.close()
            flash(f"Database error while creating reset code: {e}", "danger")
            return render_template('forgot_password.html', entered_identifier=entered_identifier)
        if not sent:
            if PASSWORD_RESET_ALLOW_LOCAL_TEST_CODE:
                preview_candidate = candidates[0]
                preview_channel = preview_candidate['channel']
                preview_destination = preview_candidate['destination']
                allowed_preview, preview_rate_msg, preview_cooldown = validate_password_reset_send_rate(
                    conn,
                    user['user_id'],
                    preview_destination,
                    request_ip,
                )
                if not allowed_preview:
                    conn.close()
                    flash(preview_rate_msg, "warning")
                    return render_template(
                        'forgot_password.html',
                        entered_identifier=entered_identifier,
                        resend_cooldown_seconds=preview_cooldown,
                    )

                try:
                    otp_id, test_otp_code = create_password_reset_otp_record(
                        conn,
                        user['user_id'],
                        preview_channel,
                        preview_destination,
                        request_ip,
                    )
                except mysql.connector.Error as e:
                    conn.rollback()
                    conn.close()
                    flash(f"Database error while preparing local test code: {e}", "danger")
                    return render_template('forgot_password.html', entered_identifier=entered_identifier)

                conn.close()
                clear_password_reset_session()
                session['pwd_reset_otp_id'] = otp_id
                session['pwd_reset_user_id'] = user['user_id']
                session['pwd_reset_channel'] = preview_channel
                session['pwd_reset_destination'] = preview_destination

                masked_preview = mask_destination(preview_destination, preview_channel)
                flash(
                    f"Delivery service unavailable. Local test mode code: {test_otp_code}",
                    "warning",
                )
                flash(f"Verification code prepared for {masked_preview}.", "info")
                return redirect(url_for('forgot_password_verify'))

            conn.close()
            flash(error_message or "Unable to send verification code.", "warning")
            return render_template(
                'forgot_password.html',
                entered_identifier=entered_identifier,
                resend_cooldown_seconds=cooldown,
            )

        conn.close()
        clear_password_reset_session()
        session['pwd_reset_otp_id'] = otp_id
        session['pwd_reset_user_id'] = user['user_id']
        session['pwd_reset_channel'] = delivery_channel
        session['pwd_reset_destination'] = destination

        masked = mask_destination(destination, delivery_channel)
        flash(f"Verification code sent to {masked}.", "success")
        return redirect(url_for('forgot_password_verify'))

    return render_template('forgot_password.html', entered_identifier=entered_identifier)


@app.route('/forgot-password/verify', methods=['GET', 'POST'])
def forgot_password_verify():
    otp_id = session.get('pwd_reset_otp_id')
    user_id = session.get('pwd_reset_user_id')
    if not otp_id or not user_id:
        flash("Start password reset first.", "warning")
        return redirect(url_for('forgot_password'))

    conn = get_db()
    try:
        ensure_password_reset_table(conn)
    except mysql.connector.Error as e:
        conn.close()
        flash(f"Database error while verifying code: {e}", "danger")
        return redirect(url_for('forgot_password'))

    cur = conn.cursor(dictionary=True)
    cur.execute("""
        SELECT o.otp_id, o.user_id, o.delivery_channel, o.destination, o.otp_hash, o.expires_at,
               o.attempts, o.verified_at, o.used_at, o.sent_at,
               u.email, u.contact_no
        FROM password_reset_otps o
        JOIN users u ON u.user_id = o.user_id
        WHERE o.otp_id = %s AND o.user_id = %s
        LIMIT 1
    """, (otp_id, user_id))
    otp_row = cur.fetchone()

    if not otp_row or otp_row['used_at'] is not None:
        conn.close()
        clear_password_reset_session()
        flash("Reset request is invalid or already used.", "warning")
        return redirect(url_for('forgot_password'))

    if otp_row['expires_at'] <= datetime.now():
        conn.close()
        clear_password_reset_session()
        flash("Reset code expired. Please request a new code.", "warning")
        return redirect(url_for('forgot_password'))

    if request.method == 'POST':
        action = (request.form.get('action') or 'verify').strip().lower()

        if action == 'resend':
            request_ip = get_request_ip()
            candidates = get_password_reset_delivery_candidates(
                {'email': otp_row.get('email'), 'contact_no': otp_row.get('contact_no')},
                otp_row['delivery_channel']
            )
            if PASSWORD_RESET_ALLOW_LOCAL_TEST_CODE:
                candidates = candidates[:1]
            try:
                sent, delivery_channel, destination, error_message, cooldown = resend_password_reset_otp_with_fallback(
                    conn,
                    otp_id,
                    user_id,
                    candidates,
                    request_ip,
                )
            except mysql.connector.Error as e:
                conn.rollback()
                conn.close()
                flash(f"Database error while resending code: {e}", "danger")
                return redirect(url_for('forgot_password_verify'))
            if not sent:
                if PASSWORD_RESET_ALLOW_LOCAL_TEST_CODE:
                    preview_candidate = candidates[0] if candidates else None
                    if preview_candidate:
                        preview_channel = preview_candidate['channel']
                        preview_destination = preview_candidate['destination']
                        allowed_preview, preview_rate_msg, preview_cooldown = validate_password_reset_send_rate(
                            conn,
                            user_id,
                            preview_destination,
                            request_ip,
                        )
                        if not allowed_preview:
                            conn.close()
                            flash(preview_rate_msg, "warning")
                            return redirect(url_for('forgot_password_verify'))
                        try:
                            test_otp_code = refresh_password_reset_otp_record(
                                conn,
                                otp_id,
                                user_id,
                                preview_channel,
                                preview_destination,
                                request_ip,
                            )
                        except mysql.connector.Error as e:
                            conn.rollback()
                            conn.close()
                            flash(f"Database error while preparing local test code: {e}", "danger")
                            return redirect(url_for('forgot_password_verify'))

                        conn.close()
                        session['pwd_reset_channel'] = preview_channel
                        session['pwd_reset_destination'] = preview_destination
                        masked_preview = mask_destination(preview_destination, preview_channel)
                        flash(
                            f"Delivery service unavailable. Local test mode code: {test_otp_code}",
                            "warning",
                        )
                        flash(f"New verification code prepared for {masked_preview}.", "info")
                        return redirect(url_for('forgot_password_verify'))

                conn.close()
                flash(error_message or "Unable to resend verification code.", "warning")
                return redirect(url_for('forgot_password_verify'))
            conn.close()
            session['pwd_reset_channel'] = delivery_channel
            session['pwd_reset_destination'] = destination
            masked = mask_destination(destination, delivery_channel)
            flash(f"New verification code sent to {masked}.", "success")
            return redirect(url_for('forgot_password_verify'))

        otp_input = (request.form.get('otp_code') or '').strip()
        otp_pattern = r"[0-9]{" + str(PASSWORD_RESET_OTP_LENGTH) + r"}"
        if not re.fullmatch(otp_pattern, otp_input):
            conn.close()
            flash(f"Enter a valid {PASSWORD_RESET_OTP_LENGTH}-digit code.", "warning")
            return redirect(url_for('forgot_password_verify'))

        if otp_row['attempts'] >= PASSWORD_RESET_MAX_VERIFY_ATTEMPTS:
            conn.close()
            clear_password_reset_session()
            flash("Too many invalid attempts. Request a new code.", "danger")
            return redirect(url_for('forgot_password'))

        if check_password_hash(otp_row['otp_hash'], otp_input):
            cur.execute("""
                UPDATE password_reset_otps
                SET verified_at = NOW()
                WHERE otp_id = %s AND user_id = %s
            """, (otp_id, user_id))
            conn.commit()
            conn.close()
            session['pwd_reset_verified_otp_id'] = otp_id
            flash("Code verified. Set your new password.", "success")
            return redirect(url_for('forgot_password_reset'))

        cur.execute("""
            UPDATE password_reset_otps
            SET attempts = attempts + 1
            WHERE otp_id = %s AND user_id = %s
        """, (otp_id, user_id))
        conn.commit()
        conn.close()
        flash("Invalid verification code.", "danger")
        return redirect(url_for('forgot_password_verify'))

    conn.close()
    return render_template(
        'forgot_password_verify.html',
        masked_destination=mask_destination(otp_row['destination'], otp_row['delivery_channel']),
        delivery_channel=otp_row['delivery_channel'],
        expires_at=otp_row['expires_at'],
        attempts_left=max(0, PASSWORD_RESET_MAX_VERIFY_ATTEMPTS - int(otp_row['attempts'])),
        resend_cooldown_seconds=get_otp_resend_cooldown_seconds(otp_row.get('sent_at')),
        otp_length=PASSWORD_RESET_OTP_LENGTH,
    )


@app.route('/forgot-password/reset', methods=['GET', 'POST'])
def forgot_password_reset():
    otp_id = session.get('pwd_reset_otp_id')
    user_id = session.get('pwd_reset_user_id')
    verified_id = session.get('pwd_reset_verified_otp_id')

    if not otp_id or not user_id or verified_id != otp_id:
        flash("Verify your reset code first.", "warning")
        return redirect(url_for('forgot_password'))

    conn = get_db()
    try:
        ensure_password_reset_table(conn)
    except mysql.connector.Error as e:
        conn.close()
        flash(f"Database error while resetting password: {e}", "danger")
        return redirect(url_for('forgot_password'))

    cur = conn.cursor(dictionary=True)
    cur.execute("""
        SELECT o.otp_id, o.user_id, o.expires_at, o.verified_at, o.used_at,
               u.full_name
        FROM password_reset_otps o
        JOIN users u ON u.user_id = o.user_id
        WHERE o.otp_id = %s AND o.user_id = %s
        LIMIT 1
    """, (otp_id, user_id))
    otp_row = cur.fetchone()

    if not otp_row or otp_row['used_at'] is not None or otp_row['verified_at'] is None:
        conn.close()
        clear_password_reset_session()
        flash("Reset request is invalid. Start again.", "warning")
        return redirect(url_for('forgot_password'))

    if otp_row['expires_at'] <= datetime.now():
        conn.close()
        clear_password_reset_session()
        flash("Reset code expired. Please request a new one.", "warning")
        return redirect(url_for('forgot_password'))

    if request.method == 'POST':
        new_password = (request.form.get('new_password') or '').strip()
        confirm_password = (request.form.get('confirm_password') or '').strip()

        if len(new_password) < 6:
            conn.close()
            flash("New password must be at least 6 characters.", "warning")
            return redirect(url_for('forgot_password_reset'))
        if new_password != confirm_password:
            conn.close()
            flash("New password and confirmation do not match.", "warning")
            return redirect(url_for('forgot_password_reset'))

        try:
            password_hash = generate_password_hash(new_password)
            cur.execute("""
                UPDATE users
                SET password = %s
                WHERE user_id = %s
            """, (password_hash, user_id))
            cur.execute("""
                UPDATE password_reset_otps
                SET used_at = NOW()
                WHERE otp_id = %s AND user_id = %s
            """, (otp_id, user_id))
            conn.commit()
        except mysql.connector.Error as e:
            conn.rollback()
            conn.close()
            flash(f"Database error while updating password: {e}", "danger")
            return redirect(url_for('forgot_password_reset'))

        conn.close()
        clear_password_reset_session()
        flash("Password reset successful. Please login with your new password.", "success")
        return redirect(url_for('login'))

    conn.close()
    return render_template('forgot_password_reset.html', user_name=otp_row['full_name'])


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# ==========================================
# PROFILE & SETTINGS (COMMON FOR ALL USERS)
# ==========================================

@app.route('/profile', methods=['GET', 'POST'])
def profile():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    conn = get_db()
    cur = conn.cursor(dictionary=True)

    if request.method == 'POST':
        full_name = normalize_spaces(request.form['full_name'])
        email = request.form['email'].strip().lower()
        contact_no = request.form.get('contact_no', '').strip()
        address = request.form.get('address', '').strip()
        gender = request.form.get('gender', '').strip().title()

        if not is_valid_name(full_name):
            flash("Full name can contain letters, spaces, apostrophes, periods, and hyphens only.", "warning")
            cur.close()
            conn.close()
            return redirect(url_for('profile'))

        if not is_valid_email(email):
            flash("Please enter a valid email address.", "warning")
            cur.close()
            conn.close()
            return redirect(url_for('profile'))

        if contact_no and not is_valid_phone(contact_no):
            flash("Contact number can contain digits, spaces, '+', and '-' only.", "warning")
            cur.close()
            conn.close()
            return redirect(url_for('profile'))

        if gender and gender not in ALLOWED_GENDERS:
            flash("Please select a valid gender option.", "warning")
            cur.close()
            conn.close()
            return redirect(url_for('profile'))
        try:
            cur.execute("""
                UPDATE users 
                SET full_name = %s, email = %s, contact_no = %s, address = %s, gender = %s
                WHERE user_id = %s
            """, (full_name, email, contact_no, address, gender, session['user_id']))
            conn.commit()
            session['name'] = full_name
            flash('Profile updated successfully!', 'success')
        except mysql.connector.Error as e:
            conn.rollback()
            flash(f'Error updating profile: {e}', 'danger')
        finally:
            cur.close()
            conn.close()

        return redirect(url_for('profile'))

    # GET request — fetch user data
    cur.execute("SELECT * FROM users WHERE user_id = %s", (session['user_id'],))
    user = cur.fetchone()
    cur.close()
    conn.close()

    if not user:
        flash('User not found.', 'danger')
        return redirect(url_for('logout'))

    return render_template('profile.html', user=user)

@app.route('/settings', methods=['GET', 'POST'])
def settings():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    conn = get_db()
    cur = conn.cursor(dictionary=True)

    if request.method == 'POST':
        current_pass = request.form['current_password']
        new_pass = request.form['new_password']
        confirm_pass = request.form['confirm_password']

        cur.execute("SELECT password FROM users WHERE user_id = %s", (session['user_id'],))
        stored = cur.fetchone()

        if stored and verify_password(stored['password'], current_pass):
            if new_pass == confirm_pass and new_pass.strip() != '':
                try:
                    new_hash = generate_password_hash(new_pass)
                    cur.execute("UPDATE users SET password = %s WHERE user_id = %s",
                                (new_hash, session['user_id']))
                    conn.commit()
                    flash('Password changed successfully!', 'success')
                except mysql.connector.Error as e:
                    conn.rollback()
                    flash(f'Error changing password: {e}', 'danger')
            else:
                flash('New passwords do not match or are empty!', 'danger')
        else:
            flash('Incorrect current password!', 'danger')

        cur.close()
        conn.close()
        return redirect(url_for('settings'))

    cur.close()
    conn.close()
    return render_template('settings.html')

# ==========================================
# ADMIN DASHBOARD
# ==========================================
@app.route('/admin')
def admin_dashboard():
    if not check_auth('admin'):
        return redirect(url_for('login'))

    conn = get_db()
    cur = conn.cursor()

    # Dashboard statistics
    stats = {}
    queries = {
        's': "SELECT COUNT(*) FROM users WHERE role='student'",
        't': "SELECT COUNT(*) FROM users WHERE role='teacher'",
        'd': "SELECT COUNT(*) FROM departments",
        'c': "SELECT COUNT(*) FROM courses",
        'f': "SELECT COUNT(*) FROM fees WHERE status='Pending'",
        'e': "SELECT COUNT(*) FROM exam_schedule"
    }

    for k, q in queries.items():
        cur.execute(q)
        stats[k] = cur.fetchone()[0]

    # Fetch recent notices (tuple format)
    cur.execute("""
        SELECT notice_id, title, content
        FROM notices
        ORDER BY date_posted DESC
        LIMIT 3
    """)
    notices = cur.fetchall()

    conn.close()

    return render_template(
        'admin_dash.html',
        stats=stats,
        notices=notices
    )

# ==========================================
# ADMIN LIBRARY MODULE
# ==========================================

@app.route('/admin/library', methods=['GET', 'POST'])
def admin_library():
    if not check_auth('admin'): return redirect(url_for('login'))
    
    conn = get_db()
    cur = conn.cursor(dictionary=True)
    edit_book = None
    
    try:
        # --- 1. Handle POST Actions (Delete Book) ---
        if request.method == 'POST':
            if 'delete_book' in request.form:
                book_id_del = request.form['book_id']
                # Check if currently borrowed (unreturned)
                cur.execute("SELECT * FROM borrows WHERE book_id = %s AND return_date IS NULL", (book_id_del,))
                if cur.fetchone():
                    flash("Cannot delete: Book is currently borrowed.", "danger")
                else:
                    cur.execute("DELETE FROM library_books WHERE book_id = %s", (book_id_del,))
                    conn.commit()
                    align_auto_increment_for_table(conn, "library_books")
                    flash("Book deleted successfully.", "success")
            # Redirect to clear POST data so refresh doesn't re-submit
            return redirect(url_for('admin_library'))

        # --- 2. Search Logic ---
        search_query = request.args.get('search_query')
        edit_book_id = request.args.get('edit_book_id', type=int)

        if edit_book_id:
            cur.execute("""
                SELECT book_id, title, author, category_id, isbn, copies_total
                FROM library_books
                WHERE book_id = %s
            """, (edit_book_id,))
            edit_book = cur.fetchone()
            if not edit_book:
                flash("Book not found for editing.", "danger")

        # --- 3. Fetch Categories (Always fetch all for the "Add Book" dropdown) ---
        cur.execute("SELECT * FROM book_categories ORDER BY name")
        categories = cur.fetchall()
        
        # --- 4. Fetch Books (Filtered) ---
        books_sql = """
            SELECT b.book_id, b.title, b.author, c.name as category_name, b.isbn, b.copies_total 
            FROM library_books b
            LEFT JOIN book_categories c ON b.category_id = c.category_id
        """
        
        if search_query:
            books_sql += """
                WHERE b.title LIKE %s OR b.author LIKE %s OR c.name LIKE %s OR b.isbn LIKE %s
            """
            wc = f"%{search_query}%"
            params = (wc, wc, wc, wc)
            cur.execute(books_sql + " ORDER BY b.book_id DESC", params)
        else:
            cur.execute(books_sql + " ORDER BY b.book_id DESC")
            
        books = cur.fetchall()

        # --- 5. Calculate Availability ---
        # We calculate this only for the books we fetched (whether filtered or all)
        for book in books:
            cur.execute("""
                SELECT COUNT(*) as borrowed_count 
                FROM borrows 
                WHERE book_id = %s AND return_date IS NULL
            """, (book['book_id'],))
            borrowed = cur.fetchone()['borrowed_count']
            
            total = book['copies_total'] if book['copies_total'] else 0
            book['copies_available'] = total - borrowed

        # --- 6. Fetch Borrow History (Filtered) ---
        borrows_sql = """
            SELECT br.*, b.title as book_title, u.full_name as student_name, u.semester
            FROM borrows br
            JOIN library_books b ON br.book_id = b.book_id
            JOIN users u ON br.student_id = u.user_id
        """

        if search_query:
            borrows_sql += """
                WHERE b.title LIKE %s OR u.full_name LIKE %s
            """
            wc = f"%{search_query}%"
            cur.execute(borrows_sql + " ORDER BY br.borrow_date DESC", (wc, wc))
        else:
            cur.execute(borrows_sql + " ORDER BY br.borrow_date DESC")
            
        borrows = cur.fetchall()

    except Exception as e:
        print(f"LIBRARY ERROR: {e}")
        flash(f"System Error: {e}", "danger")
        categories = []
        books = []
        borrows = []
        edit_book = None
    
    finally:
        cur.close()
        conn.close()
        
    return render_template(
        'admin_library.html',
        categories=categories,
        books=books,
        borrows=borrows,
        edit_book=edit_book
    )

@app.route('/admin/library/add_category', methods=['POST'])
def add_category():
    if not check_auth('admin'): return redirect(url_for('login'))
    name = normalize_spaces(request.form.get('name'))
    if not is_valid_dept_name(name):
        flash("Category name can contain letters, numbers, spaces, '&', '/', '.', and '-'.", "warning")
        return redirect(url_for('admin_library'))
    if name:
        try:
            conn = get_db()
            cur = conn.cursor()
            align_auto_increment_for_table(conn, "book_categories")
            cur.execute("INSERT INTO book_categories (name) VALUES (%s)", (name,))
            conn.commit()
            conn.close()
            flash('Category added successfully!', 'success')
        except mysql.connector.Error:
            flash('Category already exists!', 'danger')
    return redirect(url_for('admin_library'))

@app.route('/admin/library/add_book', methods=['POST'])
def add_book():
    if not check_auth('admin'): return redirect(url_for('login'))
    
    book_id = request.form.get('book_id')
    title = normalize_spaces(request.form.get('title'))
    author = normalize_spaces(request.form.get('author'))
    category_id = parse_positive_int(request.form.get('category'))
    isbn = request.form.get('isbn', '').strip()
    copies = parse_positive_int(request.form.get('copies'))

    if title and author and category_id and isbn and copies:
        if len(title) > 255:
            flash('Title is too long (max 255 characters).', 'warning')
            return redirect(url_for('admin_library'))
        if not is_valid_name(author):
            flash("Author name can contain letters, spaces, apostrophes, periods, and hyphens only.", 'warning')
            return redirect(url_for('admin_library'))
        if not is_valid_isbn(isbn):
            flash("ISBN must be 7-20 characters and use digits, X, or hyphens.", 'warning')
            return redirect(url_for('admin_library'))
        try:
            conn = get_db()
            cur = conn.cursor()
            if book_id:
                parsed_book_id = parse_positive_int(book_id)
                if not parsed_book_id:
                    flash("Invalid book id.", "warning")
                    conn.close()
                    return redirect(url_for('admin_library'))
                cur.execute("""
                    UPDATE library_books
                    SET title = %s, author = %s, category_id = %s, isbn = %s, copies_total = %s
                    WHERE book_id = %s
                """, (title, author, category_id, isbn, copies, parsed_book_id))
                flash('Book updated successfully!', 'success')
            else:
                align_auto_increment_for_table(conn, "library_books")
                cur.execute("""
                    INSERT INTO library_books (title, author, category_id, isbn, copies_total) 
                    VALUES (%s, %s, %s, %s, %s)
                """, (title, author, category_id, isbn, copies))
                flash('Book added successfully!', 'success')
            conn.commit()
            conn.close()
        except mysql.connector.Error as err:
            flash(f'Error adding book: {err}', 'danger')
    else:
        flash('Please fill in all fields.', 'warning')
        
    return redirect(url_for('admin_library'))

@app.route('/admin/library/edit_borrow', methods=['POST'])
def edit_borrow():
    if not check_auth('admin'): return redirect(url_for('login'))
    
    borrow_id = parse_positive_int(request.form.get('borrow_id'))
    due_date = request.form.get('due_date')
    fine = parse_non_negative_decimal(request.form.get('fine'))
    return_date = request.form.get('return_date')
    
    if not return_date:
        return_date = None
    if fine is None:
        flash("Fine must be a non-negative number.", "warning")
        return redirect(url_for('admin_library'))
    if not due_date:
        flash("Due date is required.", "warning")
        return redirect(url_for('admin_library'))

    if borrow_id:
        try:
            conn = get_db()
            cur = conn.cursor()
            cur.execute("""
                UPDATE borrows 
                SET due_date = %s, fine = %s, return_date = %s
                WHERE borrow_id = %s
            """, (due_date, fine, return_date, borrow_id))
            conn.commit()
            conn.close()
            flash('Borrow record updated!', 'success')
        except Exception as e:
            flash(f"Error updating: {e}", "danger")
        
    return redirect(url_for('admin_library'))


# ==========================================
# OTHER ADMIN MODULES
# ==========================================

@app.route('/admin/departments', methods=['GET', 'POST'])
def manage_departments():
    if 'user_id' not in session or session.get('role') != 'admin':
        return redirect(url_for('login'))
    
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    edit_department = None

    # --- Handle Adding New Department ---
    if request.method == 'POST':
        dept_name = normalize_spaces(request.form['dept_name'])
        hod_name = normalize_spaces(request.form.get('hod_name')) # Optional field
        edit_id = request.form.get('edit_id')

        if not is_valid_dept_name(dept_name):
            flash("Department name can contain letters, numbers, spaces, '&', '/', '.', and '-'.", "warning")
            conn.close()
            return redirect(url_for('manage_departments'))

        if hod_name and not is_valid_name(hod_name):
            flash("HOD name can contain letters, spaces, apostrophes, periods, and hyphens only.", "warning")
            conn.close()
            return redirect(url_for('manage_departments'))

        try:
            if edit_id:
                parsed_edit_id = parse_positive_int(edit_id)
                if not parsed_edit_id:
                    flash("Invalid department id.", "warning")
                    conn.close()
                    return redirect(url_for('manage_departments'))
                cursor.execute(
                    "UPDATE departments SET dept_name = %s, hod_name = %s WHERE dept_id = %s",
                    (dept_name, hod_name if hod_name else None, parsed_edit_id)
                )
                flash('Department updated successfully!', 'success')
            else:
                align_auto_increment_for_table(conn, "departments")
                cursor.execute(
                    "INSERT INTO departments (dept_name, hod_name) VALUES (%s, %s)",
                    (dept_name, hod_name if hod_name else None)
                )
                flash('Department added successfully!', 'success')

            conn.commit()
        except mysql.connector.Error as e:
            conn.rollback()
            if e.errno == 1062:
                flash("Department name already exists.", "danger")
            else:
                flash(f"Error saving department: {e}", "danger")

        conn.close()
        return redirect(url_for('manage_departments'))

    # --- Handle Search & Listing ---
    search_query = request.args.get('search_query')

    if search_query:
        # Search by Department Name OR HOD Name
        # Using % wildcard for partial matches
        query = """
            SELECT * FROM departments 
            WHERE dept_name LIKE %s OR hod_name LIKE %s
            ORDER BY dept_id DESC
        """
        like_val = f"%{search_query}%"
        cursor.execute(query, (like_val, like_val))
    else:
        # Default view: Show all departments
        cursor.execute("SELECT * FROM departments ORDER BY dept_id DESC")
    
    departments = cursor.fetchall()
    edit_id = request.args.get('edit_id', type=int)
    if edit_id:
        cursor.execute(
            "SELECT dept_id, dept_name, hod_name FROM departments WHERE dept_id = %s",
            (edit_id,)
        )
        edit_department = cursor.fetchone()
        if not edit_department:
            flash("Department not found for editing.", "danger")

    conn.close()

    return render_template(
        'admin_departments.html',
        departments=departments,
        edit_department=edit_department
    )

@app.route('/admin/delete_dept/<int:id>')
def delete_department(id):
    if not check_auth('admin'): return redirect(url_for('login'))
    conn = get_db(); cur = conn.cursor()
    try:
        cur.execute("DELETE FROM departments WHERE dept_id=%s", (id,))
        conn.commit()
        align_auto_increment_for_table(conn, "departments")
        flash("Department Deleted")
    except: flash("Error: Cannot delete department. Dependent records exist.")
    conn.close()
    return redirect(url_for('manage_departments'))



@app.route('/admin/students', methods=['GET', 'POST'])
def manage_students():
    if not check_auth('admin'):
        return redirect(url_for('login'))

    conn = get_db()
    try:
        ensure_users_date_of_birth_column(conn)
        ensure_users_profile_photo_column(conn)
    except mysql.connector.Error as e:
        conn.close()
        flash(f"Database error while preparing Student columns: {e}", "danger")
        return redirect(url_for('admin_dashboard'))

    cur = conn.cursor(dictionary=True)
    edit_student = None

    # --- 1. HANDLE ADDING NEW STUDENT (POST) ---
    if request.method == 'POST':
        mode = (request.form.get('mode') or 'single').strip().lower()
        edit_id = request.form.get('edit_id')
        if mode == 'bulk' and not edit_id:
            row_count = parse_positive_int(request.form.get('row_count'))
            if not row_count:
                conn.close()
                flash("Please enter a valid number of student records for bulk entry.", "warning")
                return redirect(url_for('manage_students'))
            if row_count > MAX_BULK_STUDENTS:
                conn.close()
                flash(f"Bulk entry limit is {MAX_BULK_STUDENTS} students at once.", "warning")
                return redirect(url_for('manage_students'))

            bulk_rows = []
            seen_roll_row = {}
            seen_email_row = {}
            parse_errors = []

            for idx in range(1, row_count + 1):
                roll_no = (request.form.get(f'roll_no_{idx}') or '').strip().upper()
                full_name = normalize_spaces(request.form.get(f'full_name_{idx}'))
                email = (request.form.get(f'email_{idx}') or '').strip().lower()
                contact_no = (request.form.get(f'contact_no_{idx}') or '').strip()
                gender = (request.form.get(f'gender_{idx}') or '').strip().title()
                address = (request.form.get(f'address_{idx}') or '').strip()
                dept_id = parse_positive_int(request.form.get(f'dept_id_{idx}'))
                semester = (request.form.get(f'semester_{idx}') or '').strip()
                date_of_birth = (request.form.get(f'date_of_birth_{idx}') or '').strip()
                enroll_date = (request.form.get(f'enroll_date_{idx}') or '').strip()
                plain_password = (request.form.get(f'password_{idx}') or '').strip()
                profile_photo_file = request.files.get(f'profile_photo_{idx}')

                row_error = None
                if not roll_no or not full_name or not email or not contact_no or not gender or not address or not dept_id or not semester or not date_of_birth or not plain_password:
                    row_error = f"Row {idx}: all fields are required."
                elif not is_valid_roll_no(roll_no):
                    row_error = f"Row {idx}: invalid roll no format."
                elif roll_no in seen_roll_row:
                    row_error = f"Row {idx}: duplicate roll no within bulk sheet (already in row {seen_roll_row[roll_no]})."
                elif not is_valid_name(full_name):
                    row_error = f"Row {idx}: invalid student name."
                elif not is_valid_email(email):
                    row_error = f"Row {idx}: invalid email format."
                elif email in seen_email_row:
                    row_error = f"Row {idx}: duplicate email within bulk sheet (already in row {seen_email_row[email]})."
                elif not is_valid_phone(contact_no):
                    row_error = f"Row {idx}: invalid contact number."
                elif gender not in ALLOWED_GENDERS:
                    row_error = f"Row {idx}: invalid gender."
                elif semester not in ALLOWED_SEMESTERS:
                    row_error = f"Row {idx}: invalid semester."
                elif len(plain_password) < 6:
                    row_error = f"Row {idx}: password must be at least 6 characters."
                else:
                    photo_error = validate_profile_photo_upload(profile_photo_file)
                    if photo_error:
                        row_error = f"Row {idx}: {photo_error}"

                dob_date = parse_iso_date(date_of_birth)
                enroll_date_obj = parse_iso_date(enroll_date)
                if not row_error and not is_valid_date_of_birth(dob_date):
                    row_error = f"Row {idx}: invalid date of birth."
                if not row_error and not enroll_date_obj:
                    row_error = f"Row {idx}: invalid enrollment date."
                if not row_error and dob_date > enroll_date_obj:
                    row_error = f"Row {idx}: date of birth cannot be after enrollment date."

                if row_error:
                    parse_errors.append(row_error)
                    continue

                seen_roll_row[roll_no] = idx
                seen_email_row[email] = idx
                bulk_rows.append({
                    'roll_no': roll_no,
                    'full_name': full_name,
                    'email': email,
                    'contact_no': contact_no,
                    'gender': gender,
                    'address': address,
                    'dept_id': dept_id,
                    'semester': semester,
                    'date_of_birth': dob_date,
                    'enroll_date': enroll_date_obj,
                    'password_hash': generate_password_hash(plain_password),
                    'profile_photo_file': profile_photo_file,
                    'row_index': idx,
                })

            if not bulk_rows:
                conn.close()
                if parse_errors:
                    preview = "; ".join(parse_errors[:6])
                    more = " ..." if len(parse_errors) > 6 else ""
                    flash(f"No rows were saved. {preview}{more}", "warning")
                else:
                    flash("No valid bulk rows found to save.", "warning")
                return redirect(url_for('manage_students'))

            inserted_count = 0
            skipped_errors = list(parse_errors)
            align_auto_increment_for_table(conn, "users")
            for row in bulk_rows:
                profile_photo_name = None
                photo_upload = row.get('profile_photo_file')
                if photo_upload and (photo_upload.filename or "").strip():
                    profile_photo_name, _, photo_error = save_profile_photo(photo_upload)
                    if photo_error:
                        skipped_errors.append(f"Row {row['row_index']}: {photo_error}")
                        continue

                try:
                    cur.execute("""
                        INSERT INTO users
                        (roll_no, full_name, email, password, role, dept_id, semester,
                         date_of_birth, enroll_date, contact_no, gender, address, profile_photo)
                        VALUES (%s, %s, %s, %s, 'student', %s, %s, %s, %s, %s, %s, %s, %s)
                    """, (
                        row['roll_no'],
                        row['full_name'],
                        row['email'],
                        row['password_hash'],
                        row['dept_id'],
                        row['semester'],
                        row['date_of_birth'],
                        row['enroll_date'],
                        row['contact_no'],
                        row['gender'],
                        row['address'],
                        profile_photo_name,
                    ))
                    conn.commit()
                    inserted_count += 1
                except mysql.connector.Error as e:
                    conn.rollback()
                    if profile_photo_name:
                        remove_uploaded_file_if_exists(UPLOAD_PROFILE_PHOTOS_DIR, profile_photo_name)
                    if e.errno == 1062:
                        if 'roll_no' in str(e):
                            skipped_errors.append(f"Row {row['row_index']}: roll no already exists.")
                        elif 'email' in str(e):
                            skipped_errors.append(f"Row {row['row_index']}: email already exists.")
                        else:
                            skipped_errors.append(f"Row {row['row_index']}: duplicate data.")
                    else:
                        skipped_errors.append(f"Row {row['row_index']}: database error.")

            if inserted_count:
                flash(f"{inserted_count} students added successfully.", "success")
            if skipped_errors:
                preview = "; ".join(skipped_errors[:6])
                more = " ..." if len(skipped_errors) > 6 else ""
                flash(f"{len(skipped_errors)} row(s) skipped. {preview}{more}", "warning")

            conn.close()
            return redirect(url_for('manage_students'))

        saved_profile_photo = None
        old_profile_photo = None
        try:
            roll_no = request.form['roll_no'].strip().upper()
            contact_no = request.form['contact_no'].strip()
            gender = request.form['gender'].strip().title()
            address = request.form['address'].strip()
            enroll_date = request.form.get('enroll_date', '').strip()
            date_of_birth = request.form.get('date_of_birth', '').strip()
            full_name = normalize_spaces(request.form['full_name'])
            email = request.form['email'].strip().lower()
            dept_id = parse_positive_int(request.form['dept_id'])
            semester = request.form['semester'].strip()
            uploaded_profile_photo = request.files.get('profile_photo')
            has_new_profile_photo = bool(uploaded_profile_photo and (uploaded_profile_photo.filename or "").strip())

            profile_photo_error = validate_profile_photo_upload(uploaded_profile_photo)
            if profile_photo_error:
                flash(profile_photo_error, "warning")
                return redirect(url_for('manage_students'))

            if not is_valid_roll_no(roll_no):
                flash("Roll no can contain only letters, digits, and hyphens.", "warning")
                return redirect(url_for('manage_students'))
            if not is_valid_name(full_name):
                flash("Student name can contain letters, spaces, apostrophes, periods, and hyphens only.", "warning")
                return redirect(url_for('manage_students'))
            if not is_valid_email(email):
                flash("Please enter a valid student email.", "warning")
                return redirect(url_for('manage_students'))
            if not dept_id:
                flash("Please select a valid department.", "warning")
                return redirect(url_for('manage_students'))
            if semester not in ALLOWED_SEMESTERS:
                flash("Please select a valid semester.", "warning")
                return redirect(url_for('manage_students'))
            if not is_valid_phone(contact_no):
                flash("Contact number can contain digits, spaces, '+', and '-' only.", "warning")
                return redirect(url_for('manage_students'))
            if gender not in ALLOWED_GENDERS:
                flash("Please select a valid gender.", "warning")
                return redirect(url_for('manage_students'))
            if not address:
                flash("Address is required.", "warning")
                return redirect(url_for('manage_students'))
            dob_date = parse_iso_date(date_of_birth)
            if not is_valid_date_of_birth(dob_date):
                flash("Date of birth is invalid.", "warning")
                return redirect(url_for('manage_students'))
            enroll_date_obj = parse_iso_date(enroll_date)
            if not enroll_date_obj:
                flash("Enrollment date is invalid.", "warning")
                return redirect(url_for('manage_students'))
            if dob_date > enroll_date_obj:
                flash("Date of birth cannot be after enrollment date.", "warning")
                return redirect(url_for('manage_students'))

            if edit_id:
                parsed_edit_id = parse_positive_int(edit_id)
                if not parsed_edit_id:
                    flash("Invalid student id.", "warning")
                    return redirect(url_for('manage_students'))
                cur.execute(
                    "SELECT user_id, profile_photo FROM users WHERE user_id = %s AND role = 'student'",
                    (parsed_edit_id,)
                )
                existing_student = cur.fetchone()
                if not existing_student:
                    flash("Student not found.", "danger")
                else:
                    old_profile_photo = existing_student.get('profile_photo')
                    if has_new_profile_photo:
                        saved_profile_photo, _, save_error = save_profile_photo(uploaded_profile_photo)
                        if save_error:
                            flash(save_error, "warning")
                            return redirect(url_for('manage_students'))
                    new_password = request.form.get('password', '').strip()
                    if new_password:
                        password_hash = generate_password_hash(new_password)
                        if saved_profile_photo:
                            cur.execute("""
                                UPDATE users
                                SET roll_no = %s, full_name = %s, email = %s, password = %s,
                                    dept_id = %s, semester = %s, date_of_birth = %s, enroll_date = %s,
                                    contact_no = %s, gender = %s, address = %s, profile_photo = %s
                                WHERE user_id = %s AND role = 'student'
                            """, (
                                roll_no, full_name, email, password_hash, dept_id, semester,
                                dob_date,
                                enroll_date_obj,
                                contact_no, gender, address, saved_profile_photo, parsed_edit_id
                            ))
                        else:
                            cur.execute("""
                                UPDATE users
                                SET roll_no = %s, full_name = %s, email = %s, password = %s,
                                    dept_id = %s, semester = %s, date_of_birth = %s, enroll_date = %s,
                                    contact_no = %s, gender = %s, address = %s
                                WHERE user_id = %s AND role = 'student'
                            """, (
                                roll_no, full_name, email, password_hash, dept_id, semester,
                                dob_date,
                                enroll_date_obj,
                                contact_no, gender, address, parsed_edit_id
                            ))
                    else:
                        if saved_profile_photo:
                            cur.execute("""
                                UPDATE users
                                SET roll_no = %s, full_name = %s, email = %s,
                                    dept_id = %s, semester = %s, date_of_birth = %s, enroll_date = %s,
                                    contact_no = %s, gender = %s, address = %s, profile_photo = %s
                                WHERE user_id = %s AND role = 'student'
                            """, (
                                roll_no, full_name, email, dept_id, semester,
                                dob_date,
                                enroll_date_obj,
                                contact_no, gender, address, saved_profile_photo, parsed_edit_id
                            ))
                        else:
                            cur.execute("""
                                UPDATE users
                                SET roll_no = %s, full_name = %s, email = %s,
                                    dept_id = %s, semester = %s, date_of_birth = %s, enroll_date = %s,
                                    contact_no = %s, gender = %s, address = %s
                                WHERE user_id = %s AND role = 'student'
                            """, (
                                roll_no, full_name, email, dept_id, semester,
                                dob_date,
                                enroll_date_obj,
                                contact_no, gender, address, parsed_edit_id
                            ))
                    conn.commit()
                    if saved_profile_photo and old_profile_photo and old_profile_photo != saved_profile_photo:
                        remove_uploaded_file_if_exists(UPLOAD_PROFILE_PHOTOS_DIR, old_profile_photo)
                    flash("Student updated successfully.", "success")
            else:
                plain_password = request.form.get('password', '').strip()
                if len(plain_password) < 6:
                    flash("Password must be at least 6 characters.", "warning")
                    return redirect(url_for('manage_students'))
                password_hash = generate_password_hash(plain_password)
                if has_new_profile_photo:
                    saved_profile_photo, _, save_error = save_profile_photo(uploaded_profile_photo)
                    if save_error:
                        flash(save_error, "warning")
                        return redirect(url_for('manage_students'))
                align_auto_increment_for_table(conn, "users")
                cur.execute("""INSERT INTO users 
                               (roll_no, full_name, email, password, role, dept_id, semester, 
                                date_of_birth, enroll_date, contact_no, gender, address, profile_photo) 
                               VALUES (%s, %s, %s, %s, 'student', %s, %s, %s, %s, %s, %s, %s, %s)""",
                            (roll_no,
                             full_name,
                             email,
                             password_hash,
                             dept_id,
                             semester,
                             dob_date,
                             enroll_date_obj,
                             contact_no,
                             gender,
                             address,
                             saved_profile_photo))
                conn.commit()
                flash("Student added successfully.", "success")
        except mysql.connector.Error as e:
            conn.rollback()
            if saved_profile_photo:
                remove_uploaded_file_if_exists(UPLOAD_PROFILE_PHOTOS_DIR, saved_profile_photo)
            if e.errno == 1062:  # Duplicate entry
                if 'roll_no' in str(e):
                    flash("Error: This Roll No already exists.", "danger")
                elif 'email' in str(e):
                    flash("Error: This Email already exists.", "danger")
                else:
                    flash("Error: Duplicate entry (Roll No or Email).", "danger")
            else:
                flash(f"Error adding student: {e}", "danger")
        finally:
            conn.close()
        return redirect(url_for('manage_students'))

    # --- 2. HANDLE GLOBAL SEARCH & LISTING (GET) ---
    search_query = request.args.get('search_query')

    # Base query: Join users with departments
    base_query = """
        SELECT u.user_id, u.roll_no, u.full_name, u.email, u.semester, 
               d.dept_name, u.date_of_birth, u.enroll_date, u.contact_no, u.gender, u.address,
               u.profile_photo
        FROM users u 
        LEFT JOIN departments d ON u.dept_id = d.dept_id 
        WHERE u.role = 'student'
    """

    if search_query:
        # Search across ALL meaningful columns
        # We use CAST(u.enroll_date AS CHAR) to allow string searching on dates
        sql = base_query + """
            AND (
                u.full_name LIKE %s OR 
                u.roll_no LIKE %s OR 
                d.dept_name LIKE %s OR 
                u.email LIKE %s OR 
                u.contact_no LIKE %s OR 
                u.gender LIKE %s OR 
                u.address LIKE %s OR 
                u.semester LIKE %s OR 
                CAST(u.date_of_birth AS CHAR) LIKE %s OR
                CAST(u.enroll_date AS CHAR) LIKE %s
            )
            ORDER BY u.roll_no ASC
        """
        wildcard = f"%{search_query}%"
        # We must provide the wildcard variable once for every %s placeholder above (10 times)
        cur.execute(sql, (wildcard, wildcard, wildcard, wildcard, wildcard, wildcard, wildcard, wildcard, wildcard, wildcard))
    else:
        # Default: Show all students ordered by Roll No
        cur.execute(base_query + " ORDER BY u.roll_no ASC")
    
    students = cur.fetchall()

    # --- 3. FETCH DEPARTMENTS (For Dropdown) ---
    cur.execute("SELECT dept_id, dept_name FROM departments ORDER BY dept_name")
    departments = cur.fetchall()

    edit_id = request.args.get('edit_id', type=int)
    if edit_id:
        cur.execute("""
            SELECT user_id, roll_no, full_name, email, dept_id, semester,
                   date_of_birth, enroll_date, contact_no, gender, address, profile_photo
            FROM users
            WHERE user_id = %s AND role = 'student'
        """, (edit_id,))
        edit_student = cur.fetchone()
        if not edit_student:
            flash("Student not found for editing.", "danger")

    today = date.today().isoformat()

    conn.close()

    return render_template(
        'admin_students.html',
        students=students,
        departments=departments,
        today=today,
        edit_student=edit_student
    )


@app.route('/admin/student/<int:id>/profile')
def admin_student_resume(id):
    if not check_auth('admin'):
        return redirect(url_for('login'))

    conn = get_db()
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute("""
            SELECT u.user_id, u.roll_no, u.full_name, u.email, u.contact_no, u.gender, u.address,
                   u.semester, u.date_of_birth, u.enroll_date, u.profile_photo, d.dept_name
            FROM users u
            LEFT JOIN departments d ON d.dept_id = u.dept_id
            WHERE u.user_id = %s AND u.role = 'student'
            LIMIT 1
        """, (id,))
        student = cur.fetchone()
    finally:
        cur.close()
        conn.close()

    if not student:
        flash("Student profile not found.", "danger")
        return redirect(url_for('manage_students'))

    return render_template('admin_student_resume.html', student=student)


@app.route('/admin/delete_student/<int:id>', methods=['GET', 'POST'])
def delete_student(id):
    if not check_auth('admin'):
        return redirect(url_for('login'))

    if request.method == 'POST':
        # Separate connection for POST (delete operation)
        conn = get_db()
        cur = conn.cursor(dictionary=True)

        try:
            # Fetch student name for success message
            cur.execute("""
                SELECT u.full_name, u.profile_photo
                FROM users u
                WHERE u.user_id = %s AND u.role = 'student'
            """, (id,))
            student = cur.fetchone()

            if not student:
                flash("Student not found.", "danger")
                conn.close()
                return redirect(url_for('manage_students'))

            # Start manual transaction
            conn.autocommit = False

            # Delete related records (child tables first)
            related_tables = [
                'borrows',
                'fees',
                'student_results',
                'attendance',
                'student_enrollments'
            ]

            for table in related_tables:
                cur.execute(f"DELETE FROM {table} WHERE student_id = %s", (id,))

            # Delete the student record
            cur.execute("DELETE FROM users WHERE user_id = %s AND role = 'student'", (id,))

            conn.commit()
            align_auto_increment_for_tables(conn, (
                "borrows",
                "fees",
                "student_results",
                "attendance",
                "student_enrollments",
                "users",
            ))
            if student.get('profile_photo'):
                remove_uploaded_file_if_exists(UPLOAD_PROFILE_PHOTOS_DIR, student['profile_photo'])
            flash(f"Student '{student['full_name']}' and all related records deleted successfully.", "success")

        except Exception as e:
            conn.rollback()
            flash(f"Error force deleting student: {str(e)}", "danger")
        finally:
            conn.autocommit = True
            cur.close()
            conn.close()

        return redirect(url_for('manage_students'))

    # GET request: Confirmation page (separate connection)
    conn = get_db()
    cur = conn.cursor(dictionary=True)

    # Fetch student details
    cur.execute("""
        SELECT u.user_id, u.full_name, u.email, u.semester, d.dept_name
        FROM users u
        LEFT JOIN departments d ON u.dept_id = d.dept_id
        WHERE u.user_id = %s AND u.role = 'student'
    """, (id,))
    student = cur.fetchone()

    if not student:
        flash("Student not found.", "danger")
        conn.close()
        return redirect(url_for('manage_students'))

    # Count related records
    counts = {}
    for table, label in [
        ('borrows', 'borrows'),
        ('fees', 'fees'),
        ('student_results', 'results'),
        ('attendance', 'attendance'),
        ('student_enrollments', 'enrollments')
    ]:
        cur.execute(f"SELECT COUNT(*) AS cnt FROM {table} WHERE student_id = %s", (id,))
        counts[label] = cur.fetchone()['cnt']

    total_related = sum(counts.values())

    conn.close()

    return render_template(
        'admin_delete_student_confirm.html',
        student=student,
        counts=counts,
        total_related=total_related
    )

@app.route('/admin/teachers', methods=['GET', 'POST'])
def manage_teachers():
    if not check_auth('admin'):
        return redirect(url_for('login'))

    conn = get_db()
    try:
        ensure_users_profile_photo_column(conn)
    except mysql.connector.Error as e:
        conn.close()
        flash(f"Database error while preparing Teacher columns: {e}", "danger")
        return redirect(url_for('admin_dashboard'))

    cur = conn.cursor(dictionary=True)
    edit_teacher = None

    # --- 1. HANDLE ADDING NEW TEACHER (POST) ---
    if request.method == 'POST':
        edit_id = request.form.get('edit_id')
        saved_profile_photo = None
        old_profile_photo = None
        try:
            contact_no = request.form['contact_no'].strip()
            gender = request.form['gender'].strip().title()
            address = request.form['address'].strip()
            full_name = normalize_spaces(request.form['full_name'])
            email = request.form['email'].strip().lower()
            dept_id = parse_positive_int(request.form['dept_id'])
            uploaded_profile_photo = request.files.get('profile_photo')
            has_new_profile_photo = bool(uploaded_profile_photo and (uploaded_profile_photo.filename or "").strip())

            profile_photo_error = validate_profile_photo_upload(uploaded_profile_photo)
            if profile_photo_error:
                flash(profile_photo_error, "warning")
                return redirect(url_for('manage_teachers'))

            if not is_valid_name(full_name):
                flash("Teacher name can contain letters, spaces, apostrophes, periods, and hyphens only.", "warning")
                return redirect(url_for('manage_teachers'))
            if not is_valid_email(email):
                flash("Please enter a valid teacher email.", "warning")
                return redirect(url_for('manage_teachers'))
            if not dept_id:
                flash("Please select a valid department.", "warning")
                return redirect(url_for('manage_teachers'))
            if not is_valid_phone(contact_no):
                flash("Contact number can contain digits, spaces, '+', and '-' only.", "warning")
                return redirect(url_for('manage_teachers'))
            if gender not in ALLOWED_GENDERS:
                flash("Please select a valid gender.", "warning")
                return redirect(url_for('manage_teachers'))
            if not address:
                flash("Address is required.", "warning")
                return redirect(url_for('manage_teachers'))

            if edit_id:
                parsed_edit_id = parse_positive_int(edit_id)
                if not parsed_edit_id:
                    flash("Invalid teacher id.", "warning")
                    return redirect(url_for('manage_teachers'))
                cur.execute(
                    "SELECT user_id, profile_photo FROM users WHERE user_id = %s AND role = 'teacher'",
                    (parsed_edit_id,)
                )
                existing_teacher = cur.fetchone()
                if not existing_teacher:
                    flash("Teacher not found.", "danger")
                else:
                    old_profile_photo = existing_teacher.get('profile_photo')
                    if has_new_profile_photo:
                        saved_profile_photo, _, save_error = save_profile_photo(uploaded_profile_photo)
                        if save_error:
                            flash(save_error, "warning")
                            return redirect(url_for('manage_teachers'))
                    new_password = request.form.get('password', '').strip()
                    if new_password:
                        password_hash = generate_password_hash(new_password)
                        if saved_profile_photo:
                            cur.execute("""
                                UPDATE users
                                SET full_name = %s, email = %s, password = %s, dept_id = %s,
                                    contact_no = %s, gender = %s, address = %s, profile_photo = %s
                                WHERE user_id = %s AND role = 'teacher'
                            """, (full_name, email, password_hash, dept_id, contact_no, gender, address, saved_profile_photo, parsed_edit_id))
                        else:
                            cur.execute("""
                                UPDATE users
                                SET full_name = %s, email = %s, password = %s, dept_id = %s,
                                    contact_no = %s, gender = %s, address = %s
                                WHERE user_id = %s AND role = 'teacher'
                            """, (full_name, email, password_hash, dept_id, contact_no, gender, address, parsed_edit_id))
                    else:
                        if saved_profile_photo:
                            cur.execute("""
                                UPDATE users
                                SET full_name = %s, email = %s, dept_id = %s,
                                    contact_no = %s, gender = %s, address = %s, profile_photo = %s
                                WHERE user_id = %s AND role = 'teacher'
                            """, (full_name, email, dept_id, contact_no, gender, address, saved_profile_photo, parsed_edit_id))
                        else:
                            cur.execute("""
                                UPDATE users
                                SET full_name = %s, email = %s, dept_id = %s,
                                    contact_no = %s, gender = %s, address = %s
                                WHERE user_id = %s AND role = 'teacher'
                            """, (full_name, email, dept_id, contact_no, gender, address, parsed_edit_id))
                    conn.commit()
                    if saved_profile_photo and old_profile_photo and old_profile_photo != saved_profile_photo:
                        remove_uploaded_file_if_exists(UPLOAD_PROFILE_PHOTOS_DIR, old_profile_photo)
                    flash("Teacher updated successfully.", "success")
            else:
                plain_password = request.form.get('password', '').strip()
                if len(plain_password) < 6:
                    flash("Password must be at least 6 characters.", "warning")
                    return redirect(url_for('manage_teachers'))
                password_hash = generate_password_hash(plain_password)
                if has_new_profile_photo:
                    saved_profile_photo, _, save_error = save_profile_photo(uploaded_profile_photo)
                    if save_error:
                        flash(save_error, "warning")
                        return redirect(url_for('manage_teachers'))
                align_auto_increment_for_table(conn, "users")
                cur.execute("""INSERT INTO users 
                               (full_name, email, password, role, dept_id, 
                                contact_no, gender, address, profile_photo) 
                               VALUES (%s, %s, %s, 'teacher', %s, %s, %s, %s, %s)""",
                            (full_name, email, password_hash, dept_id, contact_no, gender, address, saved_profile_photo))
                conn.commit()
                flash("Teacher added successfully.", "success")
        except mysql.connector.Error as e:
            conn.rollback()
            if saved_profile_photo:
                remove_uploaded_file_if_exists(UPLOAD_PROFILE_PHOTOS_DIR, saved_profile_photo)
            if e.errno == 1062:  # Duplicate entry
                if 'email' in str(e):
                    flash("Error: This Email already exists.", "danger")
                else:
                    flash("Error: Duplicate entry (Email).", "danger")
            else:
                flash(f"Error adding teacher: {e}", "danger")
        finally:
            conn.close()
        return redirect(url_for('manage_teachers'))

    # --- 2. HANDLE SEARCH & LISTING (GET) ---
    search_query = request.args.get('search_query')

    # Base query: Join users with departments
    base_query = """
        SELECT u.user_id, u.full_name, u.email, 
               d.dept_name, u.contact_no, u.gender, u.address, u.profile_photo
        FROM users u 
        LEFT JOIN departments d ON u.dept_id = d.dept_id 
        WHERE u.role = 'teacher'
    """

    if search_query:
        # Search across Name, Dept, Email, Contact, Gender, Address
        sql = base_query + """
            AND (
                u.full_name LIKE %s OR 
                d.dept_name LIKE %s OR 
                u.email LIKE %s OR 
                u.contact_no LIKE %s OR 
                u.gender LIKE %s OR 
                u.address LIKE %s
            )
            ORDER BY u.full_name ASC
        """
        wildcard = f"%{search_query}%"
        # Provide wildcard for each placeholder (6 times)
        cur.execute(sql, (wildcard, wildcard, wildcard, wildcard, wildcard, wildcard))
    else:
        # Default: Show all teachers
        cur.execute(base_query + " ORDER BY u.full_name ASC")
    
    teachers = cur.fetchall()

    # --- 3. FETCH DEPARTMENTS (For Dropdown) ---
    cur.execute("SELECT dept_id, dept_name FROM departments ORDER BY dept_name")
    departments = cur.fetchall()

    edit_id = request.args.get('edit_id', type=int)
    if edit_id:
        cur.execute("""
            SELECT user_id, full_name, email, dept_id, contact_no, gender, address, profile_photo
            FROM users
            WHERE user_id = %s AND role = 'teacher'
        """, (edit_id,))
        edit_teacher = cur.fetchone()
        if not edit_teacher:
            flash("Teacher not found for editing.", "danger")

    conn.close()

    return render_template(
        'admin_teachers.html',
        teachers=teachers,
        departments=departments,
        edit_teacher=edit_teacher
    )

@app.route('/admin/delete_teacher/<int:id>')
def delete_teacher(id):
    if not check_auth('admin'): return redirect(url_for('login'))
    conn = get_db()
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT full_name, profile_photo FROM users WHERE user_id=%s AND role='teacher'", (id,))
    teacher = cur.fetchone()
    if not teacher:
        conn.close()
        flash("Teacher not found.", "danger")
        return redirect(url_for('manage_teachers'))

    cur.execute("DELETE FROM users WHERE user_id=%s AND role='teacher'", (id,))
    conn.commit()
    align_auto_increment_for_table(conn, "users")
    if teacher.get('profile_photo'):
        remove_uploaded_file_if_exists(UPLOAD_PROFILE_PHOTOS_DIR, teacher['profile_photo'])
    flash("Teacher Deleted")
    conn.close()
    return redirect(url_for('manage_teachers'))

@app.route('/admin/courses', methods=['GET', 'POST'])
def manage_courses():
    if not check_auth('admin'): return redirect(url_for('login'))
    conn = get_db()
    try:
        ensure_courses_credit_hour_column(conn)
    except mysql.connector.Error as e:
        conn.close()
        flash(f"Database error while preparing course credit hours: {e}", "danger")
        return redirect(url_for('admin_dashboard'))

    cur = conn.cursor(dictionary=True)
    edit_course = None

    if request.method == 'POST':
        edit_id = request.form.get('edit_id')
        try:
            course_name = normalize_spaces(request.form['course_name'])
            course_code = request.form['course_code'].strip().upper()
            dept_id = parse_positive_int(request.form['dept_id'])
            credit_hour = parse_non_negative_decimal(request.form.get('credit_hour'))

            if not is_valid_course_name(course_name):
                flash("Course name contains invalid characters.", "warning")
                return redirect(url_for('manage_courses'))
            if not is_valid_course_code(course_code):
                flash("Course code must be uppercase letters/numbers and may include hyphen.", "warning")
                return redirect(url_for('manage_courses'))
            if not dept_id:
                flash("Please select a valid department.", "warning")
                return redirect(url_for('manage_courses'))
            if credit_hour is None or credit_hour <= 0 or credit_hour > 10:
                flash("Credit hour must be a number greater than 0 and at most 10.", "warning")
                return redirect(url_for('manage_courses'))

            if edit_id:
                parsed_edit_id = parse_positive_int(edit_id)
                if not parsed_edit_id:
                    flash("Invalid course id.", "warning")
                    return redirect(url_for('manage_courses'))
                cur.execute("""
                    UPDATE courses
                    SET course_name = %s, course_code = %s, dept_id = %s, credit_hour = %s
                    WHERE course_id = %s
                """, (course_name, course_code, dept_id, credit_hour, parsed_edit_id))
                flash("Course Updated")
            else:
                align_auto_increment_for_table(conn, "courses")
                cur.execute("""
                    INSERT INTO courses (course_name, course_code, dept_id, credit_hour)
                    VALUES (%s, %s, %s, %s)
                """, (course_name, course_code, dept_id, credit_hour))
                flash("Course Added")
            conn.commit()
        except mysql.connector.Error as e:
            conn.rollback()
            if e.errno == 1062:
                flash("Error: Course code already exists.", "danger")
            else:
                flash(f"Error saving course: {e}", "danger")
        return redirect(url_for('manage_courses'))
    cur.execute("""
        SELECT c.course_id, c.course_name, c.course_code, c.credit_hour, c.dept_id, d.dept_name
        FROM courses c
        LEFT JOIN departments d ON c.dept_id = d.dept_id
    """)
    courses = cur.fetchall()
    cur.execute("SELECT * FROM departments")
    depts = cur.fetchall()

    edit_id = request.args.get('edit_id', type=int)
    if edit_id:
        cur.execute("""
            SELECT course_id, course_name, course_code, credit_hour, dept_id
            FROM courses
            WHERE course_id = %s
        """, (edit_id,))
        edit_course = cur.fetchone()
        if not edit_course:
            flash("Course not found for editing.", "danger")

    conn.close()
    return render_template('admin_courses.html', courses=courses, departments=depts, edit_course=edit_course)

@app.route('/admin/delete_course/<int:id>')
def delete_course(id):
    if not check_auth('admin'): return redirect(url_for('login'))
    conn = get_db(); cur = conn.cursor()
    cur.execute("DELETE FROM courses WHERE course_id=%s", (id,))
    conn.commit()
    align_auto_increment_for_table(conn, "courses")
    flash("Course Deleted")
    conn.close()
    return redirect(url_for('manage_courses'))

@app.route('/admin/assign', methods=['GET', 'POST'])
def assign_course():
    if not check_auth('admin'): return redirect(url_for('login'))
    conn = get_db(); cur = conn.cursor(dictionary=True)
    if request.method == 'POST':
        teacher_id = parse_positive_int(request.form.get('teacher_id'))
        course_id = parse_positive_int(request.form.get('course_id'))
        if not teacher_id or not course_id:
            flash("Please select a valid teacher and course.", "warning")
            conn.close()
            return redirect(url_for('assign_course'))
        try:
            align_auto_increment_for_table(conn, "teacher_courses")
            cur.execute("INSERT INTO teacher_courses (teacher_id, course_id) VALUES (%s, %s)", 
                        (teacher_id, course_id))
            conn.commit(); flash("Assigned Successfully")
        except mysql.connector.Error as e:
            conn.rollback()
            if e.errno == 1062:
                flash("This teacher is already assigned to that course.", "danger")
            else:
                flash(f"Error assigning course: {e}", "danger")
        return redirect(url_for('assign_course'))
    cur.execute("SELECT tc.assign_id, u.full_name, c.course_name FROM teacher_courses tc JOIN users u ON tc.teacher_id=u.user_id JOIN courses c ON tc.course_id=c.course_id")
    assignments = cur.fetchall()
    cur.execute("SELECT user_id, full_name FROM users WHERE role='teacher'")
    teachers = cur.fetchall()
    cur.execute("SELECT course_id, course_name FROM courses")
    courses = cur.fetchall()
    conn.close()
    return render_template('admin_assign.html', assignments=assignments, teachers=teachers, courses=courses)

@app.route('/admin/delete_assign/<int:id>')
def delete_assignment(id):
    if not check_auth('admin'): return redirect(url_for('login'))
    conn = get_db(); cur = conn.cursor()
    cur.execute("DELETE FROM teacher_courses WHERE assign_id=%s", (id,))
    conn.commit()
    align_auto_increment_for_table(conn, "teacher_courses")
    flash("Assignment Removed")
    conn.close()
    return redirect(url_for('assign_course'))

@app.route('/admin/exams', methods=['GET', 'POST'])
def manage_exams():
    if not check_auth('admin'): return redirect(url_for('login'))
    conn = get_db(); cur = conn.cursor(dictionary=True)
    edit_exam = None

    if request.method == 'POST':
        edit_id = request.form.get('edit_id')
        course_id = parse_positive_int(request.form.get('course_id'))
        exam_date = request.form.get('exam_date', '').strip()
        exam_time = request.form.get('exam_time', '').strip()
        room_no = normalize_spaces(request.form.get('room_no'))

        if not course_id:
            flash("Please select a valid course.", "warning")
            return redirect(url_for('manage_exams'))
        if not exam_date:
            flash("Exam date is required.", "warning")
            return redirect(url_for('manage_exams'))
        if not exam_time:
            flash("Exam time is required.", "warning")
            return redirect(url_for('manage_exams'))
        if not is_valid_room(room_no):
            flash("Room value contains invalid characters.", "warning")
            return redirect(url_for('manage_exams'))

        try:
            datetime.strptime(exam_date, "%Y-%m-%d")
            try:
                datetime.strptime(exam_time, "%H:%M")
            except ValueError:
                datetime.strptime(exam_time, "%H:%M:%S")
        except ValueError:
            flash("Invalid exam date or time format.", "warning")
            return redirect(url_for('manage_exams'))

        try:
            if edit_id:
                parsed_edit_id = parse_positive_int(edit_id)
                if not parsed_edit_id:
                    flash("Invalid exam id.", "warning")
                    return redirect(url_for('manage_exams'))
                cur.execute("""
                    UPDATE exam_schedule
                    SET course_id = %s, exam_date = %s, start_time = %s, room_no = %s
                    WHERE exam_id = %s
                """, (
                    course_id,
                    exam_date,
                    exam_time,
                    room_no,
                    parsed_edit_id
                ))
                conn.commit(); flash("Exam Updated")
            else:
                align_auto_increment_for_table(conn, "exam_schedule")
                cur.execute("""
                    INSERT INTO exam_schedule (course_id, exam_date, start_time, room_no)
                    VALUES (%s, %s, %s, %s)
                """, (
                    course_id,
                    exam_date,
                    exam_time,
                    room_no
                ))
                conn.commit(); flash("Exam Scheduled")
        except mysql.connector.Error as e:
            conn.rollback()
            if e.errno == 1062:
                flash("Duplicate exam slot for this course.", "danger")
            else:
                flash(f"Error saving exam: {e}", "danger")
        return redirect(url_for('manage_exams'))
    cur.execute("""
        SELECT e.exam_id, e.course_id, c.course_name, e.exam_date, e.start_time, e.room_no
        FROM exam_schedule e
        JOIN courses c ON e.course_id = c.course_id
        ORDER BY e.exam_date
    """)
    exams = cur.fetchall()
    cur.execute("SELECT course_id, course_name FROM courses")
    courses = cur.fetchall()

    edit_id = request.args.get('edit_id', type=int)
    if edit_id:
        cur.execute("""
            SELECT exam_id, course_id, exam_date, start_time, room_no
            FROM exam_schedule
            WHERE exam_id = %s
        """, (edit_id,))
        edit_exam = cur.fetchone()
        if not edit_exam:
            flash("Exam not found for editing.", "danger")

    conn.close()
    return render_template('admin_exams.html', exams=exams, courses=courses, edit_exam=edit_exam)

@app.route('/admin/delete_exam/<int:id>')
def delete_exam(id):
    if not check_auth('admin'): return redirect(url_for('login'))
    conn = get_db(); cur = conn.cursor()
    cur.execute("DELETE FROM exam_schedule WHERE exam_id=%s", (id,))
    conn.commit()
    align_auto_increment_for_table(conn, "exam_schedule")
    flash("Exam Deleted")
    conn.close()
    return redirect(url_for('manage_exams'))

@app.route('/admin/fees', methods=['GET', 'POST'])
def manage_fees():
    if not check_auth('admin'): return redirect(url_for('login'))
    conn = get_db(); cur = conn.cursor(dictionary=True)
    edit_fee = None

    if request.method == 'POST':
        edit_id = request.form.get('edit_id')
        student_id = parse_positive_int(request.form.get('student_id'))
        amount = parse_non_negative_decimal(request.form.get('amount'))
        description = normalize_spaces(request.form.get('description'))
        status = request.form.get('status', '').strip()

        if not student_id:
            flash("Please select a valid student.", "warning")
            return redirect(url_for('manage_fees'))
        if amount is None:
            flash("Amount must be a non-negative number.", "warning")
            return redirect(url_for('manage_fees'))
        if not description:
            flash("Description is required.", "warning")
            return redirect(url_for('manage_fees'))
        if status not in ALLOWED_FEE_STATUS:
            flash("Invalid fee status.", "warning")
            return redirect(url_for('manage_fees'))

        try:
            if edit_id:
                parsed_edit_id = parse_positive_int(edit_id)
                if not parsed_edit_id:
                    flash("Invalid fee record id.", "warning")
                    return redirect(url_for('manage_fees'))
                cur.execute("""
                    UPDATE fees
                    SET student_id = %s, amount = %s, description = %s, status = %s
                    WHERE fee_id = %s
                """, (
                    student_id,
                    amount,
                    description,
                    status,
                    parsed_edit_id
                ))
                conn.commit(); flash("Invoice Updated")
            else:
                align_auto_increment_for_table(conn, "fees")
                cur.execute("""
                    INSERT INTO fees (student_id, amount, description, status)
                    VALUES (%s, %s, %s, %s)
                """, (
                    student_id,
                    amount,
                    description,
                    status
                ))
                conn.commit(); flash("Invoice Created")
        except mysql.connector.Error as e:
            conn.rollback()
            flash(f"Error saving fee record: {e}", "danger")
        return redirect(url_for('manage_fees'))
    cur.execute("""
        SELECT f.fee_id, f.student_id, u.full_name, f.amount, f.description, f.status
        FROM fees f
        JOIN users u ON f.student_id = u.user_id
        ORDER BY f.fee_id DESC
    """)
    fees = cur.fetchall()
    cur.execute("SELECT user_id, full_name FROM users WHERE role='student'")
    students = cur.fetchall()

    edit_id = request.args.get('edit_id', type=int)
    if edit_id:
        cur.execute("""
            SELECT fee_id, student_id, amount, description, status
            FROM fees
            WHERE fee_id = %s
        """, (edit_id,))
        edit_fee = cur.fetchone()
        if not edit_fee:
            flash("Invoice not found for editing.", "danger")

    conn.close()
    return render_template('admin_fees.html', fees=fees, students=students, edit_fee=edit_fee)

@app.route('/admin/delete_fee/<int:id>')
def delete_fee(id):
    if not check_auth('admin'): return redirect(url_for('login'))
    conn = get_db(); cur = conn.cursor()
    cur.execute("DELETE FROM fees WHERE fee_id=%s", (id,))
    conn.commit()
    align_auto_increment_for_table(conn, "fees")
    flash("Record Deleted")
    conn.close()
    return redirect(url_for('manage_fees'))

@app.route('/admin/notices', methods=['GET', 'POST'])
def manage_notices():
    if not check_auth('admin'): return redirect(url_for('login'))
    conn = get_db(); cur = conn.cursor(dictionary=True)
    if request.method == 'POST':
        title = normalize_spaces(request.form.get('title'))
        content = (request.form.get('content') or '').strip()
        target_role = request.form.get('target_role', '').strip()

        if not title:
            flash("Notice title is required.", "warning")
            return redirect(url_for('manage_notices'))
        if not content:
            flash("Notice content is required.", "warning")
            return redirect(url_for('manage_notices'))
        if target_role not in ALLOWED_NOTICE_TARGET:
            flash("Invalid notice target role.", "warning")
            return redirect(url_for('manage_notices'))

        try:
            align_auto_increment_for_table(conn, "notices")
            cur.execute("INSERT INTO notices (title, content, target_role) VALUES (%s, %s, %s)",
                        (title, content, target_role))
            conn.commit(); flash("Notice Published")
        except mysql.connector.Error as e:
            conn.rollback()
            flash(f"Error publishing notice: {e}", "danger")
        return redirect(url_for('manage_notices'))
    cur.execute("SELECT * FROM notices ORDER BY date_posted DESC")
    notices = cur.fetchall()
    conn.close()
    return render_template('admin_notices.html', notices=notices)

@app.route('/admin/delete_notice/<int:id>')
def delete_notice(id):
    if not check_auth('admin'): return redirect(url_for('login'))
    conn = get_db(); cur = conn.cursor()
    cur.execute("DELETE FROM notices WHERE notice_id=%s", (id,))
    conn.commit()
    align_auto_increment_for_table(conn, "notices")
    flash("Notice Deleted")
    conn.close()
    return redirect(url_for('manage_notices'))

# ==========================================
# ADMIN RESULT MODULE
# ==========================================

@app.route('/admin/results', methods=['GET', 'POST'])
def admin_results():
    if not check_auth('admin'):
        return redirect(url_for('login'))

    conn = get_db()
    try:
        ensure_users_date_of_birth_column(conn)
        ensure_student_results_metadata_columns(conn)
    except mysql.connector.Error as e:
        conn.close()
        flash(f"Database error while preparing result search fields: {e}", "danger")
        return redirect(url_for('admin_dashboard'))

    cur = conn.cursor(dictionary=True)

    if request.method == 'POST':
        mode = request.form.get('mode', '').strip().lower()
        course_id = parse_positive_int(request.form.get('course_id'))
        exam_type = request.form.get('exam_type', '').strip()
        academic_year = parse_academic_year(request.form.get('academic_year'))
        full_marks = parse_non_negative_decimal(request.form.get('full_marks'))

        if not course_id:
            flash("Please choose a valid course.", "warning")
            conn.close()
            return redirect(url_for('admin_results'))

        if exam_type not in ALLOWED_EXAM_TYPES:
            flash("Please choose a valid exam type.", "warning")
            conn.close()
            return redirect(url_for('admin_results', course_id=course_id))

        if academic_year is None:
            flash(f"Academic year must be a 4-digit value between {MIN_ACADEMIC_YEAR} and {MAX_ACADEMIC_YEAR}.", "warning")
            conn.close()
            return redirect(url_for('admin_results', course_id=course_id, exam_type=exam_type))

        if full_marks is None or full_marks <= 0:
            flash("Full marks must be greater than zero.", "warning")
            conn.close()
            return redirect(url_for('admin_results', course_id=course_id, exam_type=exam_type, academic_year=academic_year))

        # Ensure selected course exists
        cur.execute("SELECT course_id FROM courses WHERE course_id=%s", (course_id,))
        if not cur.fetchone():
            flash("Selected course was not found.", "danger")
            conn.close()
            return redirect(url_for('admin_results'))

        cur.execute("""
            SELECT user_id, full_name, roll_no, semester
            FROM users
            WHERE role = 'student'
            ORDER BY roll_no, full_name
        """)
        all_students = cur.fetchall()
        students_map = {row['user_id']: row for row in all_students}
        if not all_students:
            flash("No students found in the system.", "warning")
            conn.close()
            return redirect(url_for('admin_results', course_id=course_id, exam_type=exam_type, academic_year=academic_year))

        align_auto_increment_for_tables(conn, ("student_enrollments", "student_results"))

        def ensure_student_enrollment(student_id):
            cur.execute("""
                INSERT IGNORE INTO student_enrollments (student_id, course_id, date_enrolled)
                VALUES (%s, %s, CURDATE())
            """, (student_id, course_id))

        def upsert_result(student_id, marks_value):
            grade, gpa = calculate_grade_gpa(float(marks_value), float(full_marks))
            cur.execute("""
                SELECT result_id FROM student_results
                WHERE student_id=%s AND course_id=%s AND exam_type=%s AND academic_year=%s
            """, (student_id, course_id, exam_type, academic_year))
            exists = cur.fetchone()
            if exists:
                cur.execute("""
                    UPDATE student_results
                    SET marks_obtained=%s, full_marks=%s, grade=%s, gpa=%s, academic_year=%s
                    WHERE result_id=%s
                """, (marks_value, full_marks, grade, gpa, academic_year, exists['result_id']))
                return 'updated'
            cur.execute("""
                INSERT INTO student_results
                (student_id, course_id, marks_obtained, full_marks, grade, gpa, exam_type, academic_year)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (student_id, course_id, marks_value, full_marks, grade, gpa, exam_type, academic_year))
            return 'inserted'

        try:
            if mode == 'single':
                edit_result_id = parse_positive_int(request.form.get('edit_result_id'))
                student_id = parse_positive_int(request.form.get('student_id'))
                marks = parse_non_negative_decimal(request.form.get('marks'))
                semester_value = (request.form.get('semester') or '').strip()

                if not student_id:
                    flash("Please select a valid student.", "warning")
                    return redirect(url_for('admin_results', course_id=course_id, exam_type=exam_type, academic_year=academic_year))
                if marks is None:
                    flash("Marks must be a non-negative number.", "warning")
                    return redirect(url_for('admin_results', course_id=course_id, exam_type=exam_type, academic_year=academic_year))
                if marks > full_marks:
                    flash("Marks obtained cannot be greater than full marks.", "warning")
                    return redirect(url_for('admin_results', course_id=course_id, exam_type=exam_type, academic_year=academic_year))
                if semester_value not in ALLOWED_SEMESTERS:
                    flash("Please choose a valid semester.", "warning")
                    return redirect(url_for('admin_results', course_id=course_id, exam_type=exam_type, academic_year=academic_year))
                if student_id not in students_map:
                    flash("Selected student was not found.", "danger")
                    return redirect(url_for('admin_results', course_id=course_id, exam_type=exam_type, academic_year=academic_year))
                cur.execute("UPDATE users SET semester = %s WHERE user_id = %s", (semester_value, student_id))
                ensure_student_enrollment(student_id)

                if edit_result_id:
                    cur.execute("""
                        SELECT result_id
                        FROM student_results
                        WHERE result_id = %s AND course_id = %s
                    """, (edit_result_id, course_id))
                    target = cur.fetchone()
                    if not target:
                        flash("Result not found for editing.", "danger")
                        return redirect(url_for('admin_results', course_id=course_id, exam_type=exam_type, academic_year=academic_year))

                    cur.execute("""
                        SELECT result_id
                        FROM student_results
                        WHERE student_id = %s AND course_id = %s AND exam_type = %s AND academic_year = %s AND result_id <> %s
                    """, (student_id, course_id, exam_type, academic_year, edit_result_id))
                    if cur.fetchone():
                        flash("A result for this student and assessment already exists.", "warning")
                        return redirect(url_for('admin_results', course_id=course_id, exam_type=exam_type, academic_year=academic_year, edit_result_id=edit_result_id))

                    grade, gpa = calculate_grade_gpa(float(marks), float(full_marks))
                    cur.execute("""
                        UPDATE student_results
                        SET student_id = %s, exam_type = %s, marks_obtained = %s,
                            full_marks = %s, grade = %s, gpa = %s, academic_year = %s
                        WHERE result_id = %s AND course_id = %s
                    """, (
                        student_id, exam_type, marks, full_marks, grade, gpa, academic_year,
                        edit_result_id, course_id
                    ))
                    conn.commit()
                    flash("Result updated successfully.", "success")
                    return redirect(url_for('admin_results', course_id=course_id, exam_type=exam_type, academic_year=academic_year))

                action = upsert_result(student_id, marks)
                conn.commit()
                flash("Result saved successfully." if action == 'inserted' else "Result updated successfully.", "success")
                return redirect(url_for('admin_results', course_id=course_id, exam_type=exam_type, academic_year=academic_year))

            if mode == 'bulk':
                if not all_students:
                    flash("No students found in the system.", "warning")
                    return redirect(url_for('admin_results', course_id=course_id, exam_type=exam_type, academic_year=academic_year))

                parsed_rows = []
                invalid_rows = []
                row_count = parse_positive_int(request.form.get('row_count'))

                # New format: generated row sheet (same style as bulk student entry)
                if row_count:
                    if row_count > MAX_BULK_RESULTS:
                        flash(f"Bulk result entry limit is {MAX_BULK_RESULTS} records at once.", "warning")
                        return redirect(url_for('admin_results', course_id=course_id, exam_type=exam_type, academic_year=academic_year))

                    seen_students = set()
                    for idx in range(1, row_count + 1):
                        student_id = parse_positive_int(request.form.get(f"student_id_{idx}"))
                        raw_marks = (request.form.get(f"marks_{idx}") or '').strip()
                        raw_semester = (request.form.get(f"semester_{idx}") or '').strip()

                        # Completely empty row means skipped row
                        if not student_id and raw_marks == '' and raw_semester == '':
                            continue

                        if not student_id or raw_marks == '' or raw_semester == '':
                            invalid_rows.append(f"Row {idx}")
                            continue
                        if student_id in seen_students:
                            invalid_rows.append(f"Row {idx} (duplicate student)")
                            continue
                        seen_students.add(student_id)

                        if student_id not in students_map:
                            invalid_rows.append(f"Row {idx} (invalid student)")
                            continue

                        marks = parse_non_negative_decimal(raw_marks)
                        if marks is None or marks > full_marks:
                            invalid_rows.append(f"Row {idx}")
                            continue
                        if raw_semester not in ALLOWED_SEMESTERS:
                            invalid_rows.append(f"Row {idx} (invalid semester)")
                            continue
                        parsed_rows.append((student_id, marks, raw_semester))
                else:
                    # Legacy fallback format: marks_<student_id>
                    for s in all_students:
                        raw_marks = (request.form.get(f"marks_{s['user_id']}") or '').strip()
                        if raw_marks == '':
                            continue
                        marks = parse_non_negative_decimal(raw_marks)
                        if marks is None or marks > full_marks:
                            invalid_rows.append(s['roll_no'] or s['full_name'])
                            continue
                        semester_value = (s.get('semester') or '').strip()
                        if semester_value not in ALLOWED_SEMESTERS:
                            invalid_rows.append(f"{s['roll_no'] or s['full_name']} (missing semester)")
                            continue
                        parsed_rows.append((s['user_id'], marks, semester_value))

                if not parsed_rows:
                    if invalid_rows:
                        names = ", ".join(invalid_rows[:6])
                        more = " ..." if len(invalid_rows) > 6 else ""
                        flash(f"No valid rows to save. Skipped: {names}{more}", "warning")
                    else:
                        flash("Enter marks for at least one student to save bulk results.", "warning")
                    return redirect(url_for('admin_results', course_id=course_id, exam_type=exam_type, academic_year=academic_year))

                inserted = 0
                updated = 0
                db_failed_rows = []
                for student_id, marks_value, semester_value in parsed_rows:
                    try:
                        cur.execute("UPDATE users SET semester = %s WHERE user_id = %s", (semester_value, student_id))
                        ensure_student_enrollment(student_id)
                        action = upsert_result(student_id, marks_value)
                        conn.commit()
                        if action == 'inserted':
                            inserted += 1
                        else:
                            updated += 1
                    except mysql.connector.Error:
                        conn.rollback()
                        student_label = students_map.get(student_id, {}).get('roll_no') or students_map.get(student_id, {}).get('full_name') or f"student {student_id}"
                        db_failed_rows.append(student_label)

                if inserted or updated:
                    flash(f"Bulk save complete. Inserted: {inserted}, Updated: {updated}.", "success")

                skipped_rows = invalid_rows + db_failed_rows
                if skipped_rows:
                    names = ", ".join(skipped_rows[:6])
                    more = " ..." if len(skipped_rows) > 6 else ""
                    flash(f"{len(skipped_rows)} row(s) skipped: {names}{more}", "warning")

                return redirect(url_for('admin_results', course_id=course_id, exam_type=exam_type, academic_year=academic_year))

            flash("Invalid submit mode.", "warning")
            return redirect(url_for('admin_results', course_id=course_id, exam_type=exam_type, academic_year=academic_year))

        except mysql.connector.Error as e:
            conn.rollback()
            flash(f"Database error while saving results: {e}", "danger")
            return redirect(url_for('admin_results', course_id=course_id, exam_type=exam_type, academic_year=academic_year))
        finally:
            conn.close()

    selected_course_id = request.args.get('course_id', type=int)
    selected_exam_type = request.args.get('exam_type', default='Final')
    selected_academic_year = parse_academic_year(request.args.get('academic_year')) or DEFAULT_ACADEMIC_YEAR
    selected_edit_result_id = request.args.get('edit_result_id', type=int)
    search_query = normalize_spaces(request.args.get('search_query'))
    if len(search_query) > 100:
        search_query = search_query[:100]
    if selected_exam_type not in ALLOWED_EXAM_TYPES:
        selected_exam_type = 'Final'

    cur.execute("""
        SELECT c.course_id, c.course_name, c.course_code, d.dept_name
        FROM courses c
        LEFT JOIN departments d ON c.dept_id = d.dept_id
        ORDER BY c.course_code, c.course_name
    """)
    courses = cur.fetchall()

    selected_course = None
    enrolled_students = []
    results = []
    existing_marks = {}
    edit_result = None

    if selected_course_id:
        cur.execute("""
            SELECT c.course_id, c.course_name, c.course_code, d.dept_name
            FROM courses c
            LEFT JOIN departments d ON c.dept_id = d.dept_id
            WHERE c.course_id = %s
        """, (selected_course_id,))
        selected_course = cur.fetchone()

        if selected_course:
            if selected_edit_result_id:
                cur.execute("""
                    SELECT result_id, student_id, exam_type, marks_obtained, full_marks, academic_year
                    FROM student_results
                    WHERE result_id = %s AND course_id = %s
                """, (selected_edit_result_id, selected_course_id))
                edit_result = cur.fetchone()
                if edit_result and edit_result['exam_type'] in ALLOWED_EXAM_TYPES:
                    selected_exam_type = edit_result['exam_type']
                    selected_academic_year = int(edit_result.get('academic_year') or selected_academic_year)
                elif not edit_result:
                    flash("Result not found for editing.", "warning")

            cur.execute("""
                SELECT u.user_id, u.full_name, u.roll_no, u.semester,
                       CASE WHEN se.student_id IS NULL THEN 0 ELSE 1 END AS is_enrolled
                FROM users u
                LEFT JOIN student_enrollments se
                       ON se.student_id = u.user_id AND se.course_id = %s
                WHERE u.role = 'student'
                ORDER BY is_enrolled DESC, u.roll_no, u.full_name
            """, (selected_course_id,))
            enrolled_students = cur.fetchall()

            results_sql = """
                SELECT r.result_id, r.student_id, u.full_name, u.roll_no, u.semester,
                       u.date_of_birth, u.email, u.contact_no, u.gender, u.address,
                       d.dept_name AS program_name, r.academic_year,
                       r.exam_type, r.marks_obtained, r.full_marks, r.grade, r.gpa
                FROM student_results r
                JOIN users u ON r.student_id = u.user_id
                JOIN courses c ON c.course_id = r.course_id
                LEFT JOIN departments d ON d.dept_id = c.dept_id
                WHERE r.course_id = %s AND r.exam_type = %s AND r.academic_year = %s
            """
            results_params = [selected_course_id, selected_exam_type, selected_academic_year]

            if search_query:
                wildcard = f"%{search_query}%"
                results_sql += """
                    AND (
                        CAST(u.user_id AS CHAR) LIKE %s OR
                        u.full_name LIKE %s OR
                        u.roll_no LIKE %s OR
                        CAST(u.date_of_birth AS CHAR) LIKE %s OR
                        u.email LIKE %s OR
                        u.contact_no LIKE %s OR
                        u.gender LIKE %s OR
                        u.address LIKE %s OR
                        u.semester LIKE %s OR
                        d.dept_name LIKE %s OR
                        CAST(r.academic_year AS CHAR) LIKE %s OR
                        r.exam_type LIKE %s OR
                        r.grade LIKE %s OR
                        CAST(r.marks_obtained AS CHAR) LIKE %s OR
                        CAST(r.full_marks AS CHAR) LIKE %s OR
                        CAST(r.gpa AS CHAR) LIKE %s
                    )
                """
                results_params.extend([wildcard] * 16)

            results_sql += " ORDER BY u.roll_no, u.full_name"
            cur.execute(results_sql, tuple(results_params))
            results = cur.fetchall()
            existing_marks = {row['student_id']: row['marks_obtained'] for row in results}
        else:
            flash("Selected course not found.", "warning")

    conn.close()
    return render_template(
        'admin_results.html',
        courses=courses,
        selected_course_id=selected_course_id,
        selected_course=selected_course,
        selected_exam_type=selected_exam_type,
        selected_academic_year=selected_academic_year,
        min_academic_year=MIN_ACADEMIC_YEAR,
        max_academic_year=MAX_ACADEMIC_YEAR,
        semesters=SEMESTER_OPTIONS,
        exam_types=ALLOWED_EXAM_TYPES,
        enrolled_students=enrolled_students,
        results=results,
        existing_marks=existing_marks,
        edit_result=edit_result,
        search_query=search_query,
    )


@app.route('/admin/result/delete/<int:result_id>', methods=['POST'])
def admin_delete_result(result_id):
    if not check_auth('admin'):
        return redirect(url_for('login'))

    requested_course_id = parse_positive_int(request.form.get('course_id'))
    requested_exam_type = (request.form.get('exam_type') or '').strip()
    requested_academic_year = parse_academic_year(request.form.get('academic_year'))
    requested_search_query = normalize_spaces(request.form.get('search_query'))
    if requested_exam_type not in ALLOWED_EXAM_TYPES:
        requested_exam_type = ''

    conn = get_db()
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute("""
            SELECT course_id, exam_type, academic_year
            FROM student_results
            WHERE result_id = %s
        """, (result_id,))
        row = cur.fetchone()
        if not row:
            flash("Result not found.", "warning")
        else:
            cur.execute("DELETE FROM student_results WHERE result_id = %s", (result_id,))
            conn.commit()
            align_auto_increment_for_table(conn, "student_results")
            flash("Result deleted successfully.", "success")
            if not requested_course_id:
                requested_course_id = row['course_id']
            if not requested_exam_type and row['exam_type'] in ALLOWED_EXAM_TYPES:
                requested_exam_type = row['exam_type']
            if requested_academic_year is None:
                requested_academic_year = parse_academic_year(str(row.get('academic_year')))
    except mysql.connector.Error as e:
        conn.rollback()
        flash(f"Database error while deleting result: {e}", "danger")
    finally:
        conn.close()

    redirect_kwargs = {}
    if requested_course_id:
        redirect_kwargs['course_id'] = requested_course_id
    if requested_exam_type:
        redirect_kwargs['exam_type'] = requested_exam_type
    if requested_academic_year:
        redirect_kwargs['academic_year'] = requested_academic_year
    if requested_search_query:
        redirect_kwargs['search_query'] = requested_search_query

    if redirect_kwargs:
        return redirect(url_for('admin_results', **redirect_kwargs))
    return redirect(url_for('admin_results'))

# ==========================================
# TEACHER DASHBOARD
# ==========================================

@app.route('/teacher')
def teacher_dashboard():
    if not check_auth('teacher'):
        return redirect(url_for('login'))

    conn = get_db()
    cur = conn.cursor(dictionary=True)
    uid = session['user_id']

    # Count of teacher courses
    cur.execute("SELECT COUNT(*) AS cnt FROM teacher_courses WHERE teacher_id=%s", (uid,))
    classes_cnt = cur.fetchone()['cnt']

    # Count of distinct students across assigned courses
    cur.execute("""
        SELECT COUNT(DISTINCT se.student_id) AS cnt
        FROM teacher_courses tc
        LEFT JOIN student_enrollments se ON tc.course_id = se.course_id
        WHERE tc.teacher_id = %s
    """, (uid,))
    students_cnt = cur.fetchone()['cnt']

    # Count of all result rows entered in assigned courses
    cur.execute("""
        SELECT COUNT(*) AS cnt
        FROM student_results r
        JOIN teacher_courses tc ON tc.course_id = r.course_id
        WHERE tc.teacher_id = %s
    """, (uid,))
    results_cnt = cur.fetchone()['cnt']

    # Count of attendance rows saved for today in assigned courses
    cur.execute("""
        SELECT COUNT(*) AS cnt
        FROM attendance a
        JOIN teacher_courses tc ON tc.course_id = a.course_id
        WHERE tc.teacher_id = %s AND a.attendance_date = %s
    """, (uid, date.today()))
    today_attendance_cnt = cur.fetchone()['cnt']

    # Quick preview of assigned courses
    cur.execute("""
        SELECT c.course_id, c.course_name, c.course_code, d.dept_name,
               COUNT(DISTINCT se.student_id) AS student_count
        FROM teacher_courses tc
        JOIN courses c ON tc.course_id = c.course_id
        LEFT JOIN departments d ON c.dept_id = d.dept_id
        LEFT JOIN student_enrollments se ON se.course_id = c.course_id
        WHERE tc.teacher_id = %s
        GROUP BY c.course_id, c.course_name, c.course_code, d.dept_name
        ORDER BY c.course_code, c.course_name
        LIMIT 6
    """, (uid,))
    courses_preview = cur.fetchall()

    # Fetch notices for teachers (or all)
    cur.execute("""
        SELECT notice_id, title, content
        FROM notices
        WHERE target_role IN ('all', 'teacher')
        ORDER BY date_posted DESC
    """)
    notices = cur.fetchall()

    conn.close()

    return render_template(
        'teacher_dash.html',
        classes_count=classes_cnt,
        students_count=students_cnt,
        results_count=results_cnt,
        today_attendance_count=today_attendance_cnt,
        notices=notices,
        courses_preview=courses_preview,
        today=date.today().isoformat(),
    )


@app.route('/teacher/results')
def teacher_results_module():
    if not check_auth('teacher'):
        return redirect(url_for('login'))

    conn = get_db()
    cur = conn.cursor(dictionary=True)
    cur.execute("""
        SELECT c.course_id, c.course_name, c.course_code, d.dept_name,
               COUNT(DISTINCT se.student_id) AS enrolled_students,
               COUNT(r.result_id) AS total_results
        FROM teacher_courses tc
        JOIN courses c ON tc.course_id = c.course_id
        LEFT JOIN departments d ON c.dept_id = d.dept_id
        LEFT JOIN student_enrollments se ON se.course_id = c.course_id
        LEFT JOIN student_results r ON r.course_id = c.course_id
        WHERE tc.teacher_id = %s
        GROUP BY c.course_id, c.course_name, c.course_code, d.dept_name
        ORDER BY c.course_code, c.course_name
    """, (session['user_id'],))
    courses = cur.fetchall()
    conn.close()
    return render_template('teacher_results_module.html', courses=courses)


@app.route('/teacher/attendance')
def teacher_attendance_module():
    if not check_auth('teacher'):
        return redirect(url_for('login'))

    conn = get_db()
    cur = conn.cursor(dictionary=True)
    cur.execute("""
        SELECT c.course_id, c.course_name, c.course_code, d.dept_name,
               COUNT(DISTINCT se.student_id) AS enrolled_students,
               MAX(a.attendance_date) AS last_marked_date
        FROM teacher_courses tc
        JOIN courses c ON tc.course_id = c.course_id
        LEFT JOIN departments d ON c.dept_id = d.dept_id
        LEFT JOIN student_enrollments se ON se.course_id = c.course_id
        LEFT JOIN attendance a ON a.course_id = c.course_id
        WHERE tc.teacher_id = %s
        GROUP BY c.course_id, c.course_name, c.course_code, d.dept_name
        ORDER BY c.course_code, c.course_name
    """, (session['user_id'],))
    courses = cur.fetchall()
    conn.close()
    return render_template('teacher_attendance_module.html', courses=courses)


@app.route('/teacher/students')
def teacher_students_module():
    if not check_auth('teacher'):
        return redirect(url_for('login'))

    search_query = normalize_spaces(request.args.get('search_query'))
    if len(search_query) > 100:
        search_query = search_query[:100]

    conn = get_db()
    try:
        ensure_users_date_of_birth_column(conn)
    except mysql.connector.Error as e:
        conn.close()
        flash(f"Database error while preparing student module: {e}", "danger")
        return redirect(url_for('teacher_dashboard'))

    cur = conn.cursor(dictionary=True)
    sql = """
        SELECT u.user_id, u.full_name, u.roll_no, u.email, u.semester, u.date_of_birth,
               COUNT(DISTINCT tc.course_id) AS assigned_course_count,
               GROUP_CONCAT(DISTINCT c.course_code ORDER BY c.course_code SEPARATOR ', ') AS assigned_courses
        FROM teacher_courses tc
        JOIN student_enrollments se ON se.course_id = tc.course_id
        JOIN users u ON u.user_id = se.student_id
        JOIN courses c ON c.course_id = tc.course_id
        WHERE tc.teacher_id = %s
    """
    params = [session['user_id']]
    if search_query:
        wildcard = f"%{search_query}%"
        sql += """
            AND (
                CAST(u.user_id AS CHAR) LIKE %s OR
                u.full_name LIKE %s OR
                u.roll_no LIKE %s OR
                u.email LIKE %s OR
                u.semester LIKE %s OR
                CAST(u.date_of_birth AS CHAR) LIKE %s OR
                c.course_code LIKE %s OR
                c.course_name LIKE %s
            )
        """
        params.extend([wildcard] * 8)

    sql += """
        GROUP BY u.user_id, u.full_name, u.roll_no, u.email, u.semester, u.date_of_birth
        ORDER BY u.roll_no, u.full_name
    """
    cur.execute(sql, tuple(params))
    students = cur.fetchall()
    conn.close()
    return render_template(
        'teacher_students_module.html',
        students=students,
        search_query=search_query,
    )


@app.route('/teacher/assignments')
def teacher_assignments_module():
    if not check_auth('teacher'):
        return redirect(url_for('login'))

    conn = get_db()
    try:
        ensure_assignment_tables(conn)
    except mysql.connector.Error as e:
        conn.close()
        flash(f"Database error while loading assignments module: {e}", "danger")
        return redirect(url_for('teacher_dashboard'))

    cur = conn.cursor(dictionary=True)
    cur.execute("""
        SELECT c.course_id, c.course_name, c.course_code, d.dept_name,
               (
                   SELECT COUNT(*)
                   FROM student_enrollments se
                   WHERE se.course_id = c.course_id
               ) AS enrolled_students,
               (
                   SELECT COUNT(*)
                   FROM teacher_assignments ta
                   WHERE ta.course_id = c.course_id
                     AND ta.teacher_id = tc.teacher_id
               ) AS assignment_count,
               (
                   SELECT COUNT(*)
                   FROM assignment_submissions s
                   JOIN teacher_assignments ta2 ON ta2.assignment_id = s.assignment_id
                   WHERE ta2.course_id = c.course_id
                     AND ta2.teacher_id = tc.teacher_id
                     AND s.status = 'submitted'
               ) AS submitted_count
        FROM teacher_courses tc
        JOIN courses c ON tc.course_id = c.course_id
        LEFT JOIN departments d ON c.dept_id = d.dept_id
        WHERE tc.teacher_id = %s
        ORDER BY c.course_code, c.course_name
    """, (session['user_id'],))
    courses = cur.fetchall()
    conn.close()

    return render_template('teacher_assignments_module.html', courses=courses)


@app.route('/teacher/assignments/<int:course_id>', methods=['GET', 'POST'])
def teacher_course_assignments(course_id):
    if not check_auth('teacher'):
        return redirect(url_for('login'))

    conn = get_db()
    try:
        ensure_assignment_tables(conn)
    except mysql.connector.Error as e:
        conn.close()
        flash(f"Database error while preparing assignment data: {e}", "danger")
        return redirect(url_for('teacher_assignments_module'))

    cur = conn.cursor(dictionary=True)
    teacher_id = session['user_id']

    cur.execute("""
        SELECT c.course_id, c.course_name, c.course_code, d.dept_name
        FROM teacher_courses tc
        JOIN courses c ON tc.course_id = c.course_id
        LEFT JOIN departments d ON c.dept_id = d.dept_id
        WHERE tc.teacher_id = %s AND tc.course_id = %s
    """, (teacher_id, course_id))
    course = cur.fetchone()
    if not course:
        conn.close()
        flash("You are not assigned to this course.", "danger")
        return redirect(url_for('teacher_assignments_module'))

    if request.method == 'POST':
        title = sanitize_assignment_text(request.form.get('title'), MAX_ASSIGNMENT_TITLE_LENGTH)
        notice = sanitize_assignment_text(request.form.get('notice'), MAX_ASSIGNMENT_NOTICE_LENGTH)
        description = sanitize_assignment_text(request.form.get('description'), MAX_ASSIGNMENT_DESCRIPTION_LENGTH)
        due_mode = (request.form.get('due_mode') or 'date').strip().lower()
        due_date = parse_iso_date(request.form.get('due_date'))
        due_time = parse_iso_time(request.form.get('due_time'))
        uploaded_attachment = request.files.get('attachment')
        attachment_path = None
        attachment_name = None

        if not title:
            flash("Assignment title is required.", "warning")
            conn.close()
            return redirect(url_for('teacher_course_assignments', course_id=course_id))

        if due_mode == 'none':
            due_date = None
            due_time = None
        elif not due_date or due_time is None:
            flash("Please provide a valid due date and due time, or choose no due date.", "warning")
            conn.close()
            return redirect(url_for('teacher_course_assignments', course_id=course_id))

        if uploaded_attachment and (uploaded_attachment.filename or '').strip():
            attachment_path, attachment_name = save_uploaded_file(uploaded_attachment, UPLOAD_ASSIGNMENTS_DIR)
            if not attachment_path:
                flash("Invalid attachment file name.", "warning")
                conn.close()
                return redirect(url_for('teacher_course_assignments', course_id=course_id))

        try:
            align_auto_increment_for_table(conn, "teacher_assignments")
            cur.execute("""
                INSERT INTO teacher_assignments
                (course_id, teacher_id, title, notice, description, due_date, due_time, attachment_path, attachment_name)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                course_id,
                teacher_id,
                title,
                notice if notice else None,
                description if description else None,
                due_date,
                due_time,
                attachment_path,
                attachment_name
            ))
            conn.commit()
            flash("Assignment posted successfully.", "success")
        except mysql.connector.Error as e:
            conn.rollback()
            remove_uploaded_file_if_exists(UPLOAD_ASSIGNMENTS_DIR, attachment_path)
            flash(f"Database error while posting assignment: {e}", "danger")
        finally:
            conn.close()

        return redirect(url_for('teacher_course_assignments', course_id=course_id))

    cur.execute("""
        SELECT ta.assignment_id, ta.title, ta.notice, ta.description, ta.due_date, ta.due_time,
               ta.attachment_path, ta.attachment_name, ta.created_at,
               COUNT(DISTINCT se.student_id) AS enrolled_students,
               COALESCE(SUM(CASE WHEN se.student_id IS NOT NULL AND s.status = 'submitted' THEN 1 ELSE 0 END), 0) AS submitted_count,
               COALESCE(SUM(CASE WHEN se.student_id IS NOT NULL AND s.status = 'turned_in' THEN 1 ELSE 0 END), 0) AS turned_in_count,
               COALESCE(SUM(
                   CASE
                       WHEN se.student_id IS NOT NULL AND (s.status = 'not_submitted' OR s.status IS NULL)
                       THEN 1
                       ELSE 0
                   END
               ), 0) AS pending_count
        FROM teacher_assignments ta
        LEFT JOIN student_enrollments se ON se.course_id = ta.course_id
        LEFT JOIN assignment_submissions s
               ON s.assignment_id = ta.assignment_id
              AND s.student_id = se.student_id
        WHERE ta.course_id = %s
          AND ta.teacher_id = %s
        GROUP BY ta.assignment_id, ta.title, ta.notice, ta.description, ta.due_date, ta.due_time,
                 ta.attachment_path, ta.attachment_name, ta.created_at
        ORDER BY ta.created_at DESC, ta.assignment_id DESC
    """, (course_id, teacher_id))
    assignments = cur.fetchall()
    conn.close()

    return render_template(
        'teacher_course_assignments.html',
        course=course,
        assignments=assignments,
    )


@app.route('/teacher/assignment/<int:assignment_id>/submissions')
def teacher_assignment_submissions(assignment_id):
    if not check_auth('teacher'):
        return redirect(url_for('login'))

    search_query = normalize_spaces(request.args.get('search_query'))
    if len(search_query) > 100:
        search_query = search_query[:100]

    conn = get_db()
    try:
        ensure_assignment_tables(conn)
    except mysql.connector.Error as e:
        conn.close()
        flash(f"Database error while loading submissions: {e}", "danger")
        return redirect(url_for('teacher_assignments_module'))

    cur = conn.cursor(dictionary=True)
    teacher_id = session['user_id']

    cur.execute("""
        SELECT ta.assignment_id, ta.course_id, ta.title, ta.notice, ta.description, ta.due_date, ta.due_time,
               ta.attachment_path, ta.attachment_name, ta.created_at,
               c.course_name, c.course_code
        FROM teacher_assignments ta
        JOIN courses c ON c.course_id = ta.course_id
        JOIN teacher_courses tc
          ON tc.course_id = ta.course_id
         AND tc.teacher_id = %s
        WHERE ta.assignment_id = %s
    """, (teacher_id, assignment_id))
    assignment = cur.fetchone()
    if not assignment:
        conn.close()
        flash("Assignment not found or access denied.", "danger")
        return redirect(url_for('teacher_assignments_module'))

    sql = """
        SELECT u.user_id, u.full_name, u.roll_no, u.email, u.date_of_birth,
               s.submission_id,
               COALESCE(s.status, 'not_submitted') AS submission_status,
               s.submission_name, s.submitted_at, s.is_late
        FROM student_enrollments se
        JOIN users u ON u.user_id = se.student_id
        LEFT JOIN assignment_submissions s
               ON s.assignment_id = %s
              AND s.student_id = u.user_id
        WHERE se.course_id = %s
    """
    params = [assignment_id, assignment['course_id']]
    if search_query:
        wildcard = f"%{search_query}%"
        sql += """
            AND (
                CAST(u.user_id AS CHAR) LIKE %s OR
                u.full_name LIKE %s OR
                u.roll_no LIKE %s OR
                u.email LIKE %s OR
                CAST(u.date_of_birth AS CHAR) LIKE %s OR
                COALESCE(s.status, 'not_submitted') LIKE %s
            )
        """
        params.extend([wildcard] * 6)
    sql += " ORDER BY u.roll_no, u.full_name"

    cur.execute(sql, tuple(params))
    submissions = cur.fetchall()
    conn.close()

    stats = {
        'submitted': 0,
        'turned_in': 0,
        'not_submitted': 0,
    }
    for row in submissions:
        status = row.get('submission_status') or 'not_submitted'
        if status not in stats:
            status = 'not_submitted'
        stats[status] += 1

    return render_template(
        'teacher_assignment_submissions.html',
        assignment=assignment,
        submissions=submissions,
        stats=stats,
        search_query=search_query,
    )


@app.route('/teacher/assignment/<int:assignment_id>/submission/<int:student_id>', methods=['GET', 'POST'])
def teacher_assignment_submission_detail(assignment_id, student_id):
    if not check_auth('teacher'):
        return redirect(url_for('login'))

    conn = get_db()
    try:
        ensure_assignment_tables(conn)
    except mysql.connector.Error as e:
        conn.close()
        flash(f"Database error while loading assignment conversation: {e}", "danger")
        return redirect(url_for('teacher_assignments_module'))

    cur = conn.cursor(dictionary=True)
    teacher_id = session['user_id']

    cur.execute("""
        SELECT ta.assignment_id, ta.course_id, ta.title, ta.notice, ta.description, ta.due_date, ta.due_time,
               ta.attachment_path, ta.attachment_name, ta.created_at,
               c.course_name, c.course_code
        FROM teacher_assignments ta
        JOIN courses c ON c.course_id = ta.course_id
        JOIN teacher_courses tc
          ON tc.course_id = ta.course_id
         AND tc.teacher_id = %s
        WHERE ta.assignment_id = %s
    """, (teacher_id, assignment_id))
    assignment = cur.fetchone()
    if not assignment:
        conn.close()
        flash("Assignment not found or access denied.", "danger")
        return redirect(url_for('teacher_assignments_module'))

    cur.execute("""
        SELECT u.user_id, u.full_name, u.roll_no, u.email, u.date_of_birth
        FROM student_enrollments se
        JOIN users u ON u.user_id = se.student_id
        WHERE se.course_id = %s AND se.student_id = %s
    """, (assignment['course_id'], student_id))
    student = cur.fetchone()
    if not student:
        conn.close()
        flash("Student is not enrolled in this course.", "danger")
        return redirect(url_for('teacher_assignment_submissions', assignment_id=assignment_id))

    submission = get_or_create_assignment_submission(conn, cur, assignment_id, student_id)
    conn.commit()

    if request.method == 'POST':
        action = (request.form.get('action') or '').strip().lower()
        if action != 'comment':
            conn.close()
            flash("Invalid action.", "warning")
            return redirect(url_for('teacher_assignment_submission_detail', assignment_id=assignment_id, student_id=student_id))

        comment_text = sanitize_assignment_text(request.form.get('comment_text'), MAX_ASSIGNMENT_COMMENT_LENGTH)
        if not comment_text:
            conn.close()
            flash("Comment cannot be empty.", "warning")
            return redirect(url_for('teacher_assignment_submission_detail', assignment_id=assignment_id, student_id=student_id))

        try:
            align_auto_increment_for_table(conn, "assignment_comments")
            cur.execute("""
                INSERT INTO assignment_comments (submission_id, sender_id, sender_role, comment_text)
                VALUES (%s, %s, 'teacher', %s)
            """, (submission['submission_id'], teacher_id, comment_text))
            conn.commit()
            flash("Private comment posted.", "success")
        except mysql.connector.Error as e:
            conn.rollback()
            flash(f"Database error while posting comment: {e}", "danger")
        finally:
            conn.close()

        return redirect(url_for('teacher_assignment_submission_detail', assignment_id=assignment_id, student_id=student_id))

    cur.execute("""
        SELECT c.comment_id, c.comment_text, c.created_at, c.sender_role, u.full_name AS sender_name
        FROM assignment_comments c
        JOIN users u ON u.user_id = c.sender_id
        WHERE c.submission_id = %s
        ORDER BY c.created_at ASC, c.comment_id ASC
    """, (submission['submission_id'],))
    comments = cur.fetchall()
    conn.close()

    return render_template(
        'teacher_assignment_submission_detail.html',
        assignment=assignment,
        student=student,
        submission=submission,
        comments=comments,
    )


@app.route('/teacher/classes')
def teacher_classes():
    if not check_auth('teacher'): return redirect(url_for('login'))
    conn = get_db(); cur = conn.cursor(dictionary=True)
    cur.execute("""
        SELECT c.course_id, c.course_name, c.course_code, d.dept_name 
        FROM teacher_courses tc 
        JOIN courses c ON tc.course_id=c.course_id 
        JOIN departments d ON c.dept_id=d.dept_id 
        WHERE tc.teacher_id=%s
    """, (session['user_id'],))
    courses = cur.fetchall()
    conn.close()
    return render_template('teacher_classes.html', courses=courses)

@app.route('/teacher/result/<int:course_id>', methods=['GET', 'POST'])
def teacher_enter_result(course_id):
    if not check_auth('teacher'):
        return redirect(url_for('login'))

    conn = get_db()
    try:
        ensure_users_date_of_birth_column(conn)
        ensure_student_results_metadata_columns(conn)
    except mysql.connector.Error as e:
        conn.close()
        flash(f"Database error while preparing grading data: {e}", "danger")
        return redirect(url_for('teacher_classes'))

    cur = conn.cursor(dictionary=True)
    teacher_id = session['user_id']

    # Teachers can only grade courses assigned to them.
    cur.execute("""
        SELECT c.course_id, c.course_name, c.course_code, d.dept_name
        FROM teacher_courses tc
        JOIN courses c ON tc.course_id = c.course_id
        LEFT JOIN departments d ON c.dept_id = d.dept_id
        WHERE tc.teacher_id = %s AND tc.course_id = %s
    """, (teacher_id, course_id))
    course = cur.fetchone()
    if not course:
        conn.close()
        flash("You are not assigned to this course.", "danger")
        return redirect(url_for('teacher_classes'))

    def redirect_to_grading(exam_type_value=None, academic_year_value=None, search_query_value=None, edit_result_id=None):
        kwargs = {'course_id': course_id}
        if exam_type_value in ALLOWED_EXAM_TYPES:
            kwargs['exam_type'] = exam_type_value
        parsed_year = parse_academic_year(str(academic_year_value)) if academic_year_value is not None else None
        if parsed_year:
            kwargs['academic_year'] = parsed_year
        normalized_search = normalize_spaces(search_query_value)
        if normalized_search:
            kwargs['search_query'] = normalized_search
        if edit_result_id:
            kwargs['edit_result_id'] = edit_result_id
        return redirect(url_for('teacher_enter_result', **kwargs))

    if request.method == 'POST':
        mode = request.form.get('mode', '').strip().lower()
        exam_type = (request.form.get('exam_type') or '').strip()
        academic_year = parse_academic_year(request.form.get('academic_year'))
        full_marks = parse_non_negative_decimal(request.form.get('full_marks'))
        search_query_context = normalize_spaces(request.form.get('search_query'))

        if exam_type not in ALLOWED_EXAM_TYPES:
            flash("Please choose a valid exam type.", "warning")
            conn.close()
            return redirect_to_grading(search_query_value=search_query_context, academic_year_value=academic_year)
        if academic_year is None:
            flash(f"Academic year must be a 4-digit value between {MIN_ACADEMIC_YEAR} and {MAX_ACADEMIC_YEAR}.", "warning")
            conn.close()
            return redirect_to_grading(exam_type_value=exam_type, academic_year_value=academic_year, search_query_value=search_query_context)
        if full_marks is None or full_marks <= 0:
            flash("Full marks must be greater than zero.", "warning")
            conn.close()
            return redirect_to_grading(exam_type_value=exam_type, academic_year_value=academic_year, search_query_value=search_query_context)

        align_auto_increment_for_table(conn, "student_results")

        def upsert_result(student_id, marks_value):
            grade, gpa = calculate_grade_gpa(float(marks_value), float(full_marks))
            cur.execute("""
                SELECT result_id FROM student_results
                WHERE student_id = %s AND course_id = %s AND exam_type = %s AND academic_year = %s
            """, (student_id, course_id, exam_type, academic_year))
            exists = cur.fetchone()
            if exists:
                cur.execute("""
                    UPDATE student_results
                    SET marks_obtained = %s, full_marks = %s, grade = %s, gpa = %s,
                        teacher_id = %s, academic_year = %s
                    WHERE result_id = %s
                """, (marks_value, full_marks, grade, gpa, teacher_id, academic_year, exists['result_id']))
                return 'updated'

            cur.execute("""
                INSERT INTO student_results
                (student_id, course_id, teacher_id, marks_obtained, full_marks, grade, gpa, exam_type, academic_year)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (student_id, course_id, teacher_id, marks_value, full_marks, grade, gpa, exam_type, academic_year))
            return 'inserted'

        try:
            if mode == 'single':
                edit_result_id = parse_positive_int(request.form.get('edit_result_id'))
                student_id = parse_positive_int(request.form.get('student_id'))
                marks = parse_non_negative_decimal(request.form.get('marks'))
                semester_value = (request.form.get('semester') or '').strip()

                if not student_id:
                    flash("Please select a valid student.", "warning")
                    return redirect_to_grading(exam_type_value=exam_type, academic_year_value=academic_year, search_query_value=search_query_context)
                if marks is None:
                    flash("Marks must be a non-negative number.", "warning")
                    return redirect_to_grading(exam_type_value=exam_type, academic_year_value=academic_year, search_query_value=search_query_context)
                if marks > full_marks:
                    flash("Marks obtained cannot be greater than full marks.", "warning")
                    return redirect_to_grading(exam_type_value=exam_type, academic_year_value=academic_year, search_query_value=search_query_context)
                if semester_value not in ALLOWED_SEMESTERS:
                    flash("Please choose a valid semester.", "warning")
                    return redirect_to_grading(exam_type_value=exam_type, academic_year_value=academic_year, search_query_value=search_query_context)

                cur.execute("""
                    SELECT 1
                    FROM student_enrollments
                    WHERE student_id = %s AND course_id = %s
                """, (student_id, course_id))
                if not cur.fetchone():
                    flash("Selected student is not enrolled in this course.", "danger")
                    return redirect_to_grading(exam_type_value=exam_type, academic_year_value=academic_year, search_query_value=search_query_context)
                cur.execute("UPDATE users SET semester = %s WHERE user_id = %s", (semester_value, student_id))

                if edit_result_id:
                    cur.execute("""
                        SELECT result_id
                        FROM student_results
                        WHERE result_id = %s AND course_id = %s
                    """, (edit_result_id, course_id))
                    target = cur.fetchone()
                    if not target:
                        flash("Result not found for editing.", "danger")
                        return redirect_to_grading(exam_type_value=exam_type, academic_year_value=academic_year, search_query_value=search_query_context)

                    cur.execute("""
                        SELECT result_id
                        FROM student_results
                        WHERE student_id = %s AND course_id = %s AND exam_type = %s AND academic_year = %s AND result_id <> %s
                    """, (student_id, course_id, exam_type, academic_year, edit_result_id))
                    if cur.fetchone():
                        flash("A result for this student and assessment already exists.", "warning")
                        return redirect_to_grading(exam_type_value=exam_type, academic_year_value=academic_year, search_query_value=search_query_context, edit_result_id=edit_result_id)

                    grade, gpa = calculate_grade_gpa(float(marks), float(full_marks))
                    cur.execute("""
                        UPDATE student_results
                        SET student_id = %s, exam_type = %s, marks_obtained = %s,
                            full_marks = %s, grade = %s, gpa = %s, teacher_id = %s, academic_year = %s
                        WHERE result_id = %s AND course_id = %s
                    """, (
                        student_id, exam_type, marks, full_marks, grade, gpa, teacher_id, academic_year,
                        edit_result_id, course_id
                    ))
                    conn.commit()
                    flash("Result updated successfully.", "success")
                    return redirect_to_grading(exam_type_value=exam_type, academic_year_value=academic_year, search_query_value=search_query_context)

                action = upsert_result(student_id, marks)
                conn.commit()
                flash("Result saved successfully." if action == 'inserted' else "Result updated successfully.", "success")
                return redirect_to_grading(exam_type_value=exam_type, academic_year_value=academic_year, search_query_value=search_query_context)

            if mode == 'bulk':
                cur.execute("""
                    SELECT u.user_id, u.full_name, u.roll_no
                    FROM student_enrollments se
                    JOIN users u ON se.student_id = u.user_id
                    WHERE se.course_id = %s
                    ORDER BY u.roll_no, u.full_name
                """, (course_id,))
                enrolled_students = cur.fetchall()
                if not enrolled_students:
                    flash("No enrolled students found for this course.", "warning")
                    return redirect_to_grading(exam_type_value=exam_type, academic_year_value=academic_year, search_query_value=search_query_context)

                enrolled_map = {s['user_id']: s for s in enrolled_students}
                parsed_rows = []
                invalid_rows = []
                row_count = parse_positive_int(request.form.get('row_count'))

                if row_count:
                    if row_count > MAX_BULK_RESULTS:
                        flash(f"Bulk result entry limit is {MAX_BULK_RESULTS} records at once.", "warning")
                        return redirect_to_grading(exam_type_value=exam_type, academic_year_value=academic_year, search_query_value=search_query_context)

                    seen_students = set()
                    for idx in range(1, row_count + 1):
                        student_id = parse_positive_int(request.form.get(f"student_id_{idx}"))
                        raw_marks = (request.form.get(f"marks_{idx}") or '').strip()
                        raw_semester = (request.form.get(f"semester_{idx}") or '').strip()

                        if not student_id and raw_marks == '' and raw_semester == '':
                            continue
                        if not student_id or raw_marks == '' or raw_semester == '':
                            invalid_rows.append(f"Row {idx}")
                            continue
                        if student_id in seen_students:
                            invalid_rows.append(f"Row {idx} (duplicate student)")
                            continue
                        seen_students.add(student_id)
                        if student_id not in enrolled_map:
                            invalid_rows.append(f"Row {idx} (student not in course)")
                            continue

                        marks = parse_non_negative_decimal(raw_marks)
                        if marks is None or marks > full_marks:
                            invalid_rows.append(f"Row {idx}")
                            continue
                        if raw_semester not in ALLOWED_SEMESTERS:
                            invalid_rows.append(f"Row {idx} (invalid semester)")
                            continue
                        parsed_rows.append((student_id, marks, raw_semester))
                else:
                    # Backward compatible fallback
                    for s in enrolled_students:
                        raw_marks = (request.form.get(f"marks_{s['user_id']}") or '').strip()
                        if raw_marks == '':
                            continue
                        marks = parse_non_negative_decimal(raw_marks)
                        if marks is None or marks > full_marks:
                            invalid_rows.append(s['roll_no'] or s['full_name'])
                            continue
                        cur.execute("SELECT semester FROM users WHERE user_id = %s", (s['user_id'],))
                        sem_row = cur.fetchone()
                        semester_value = (sem_row['semester'] if sem_row else '') or ''
                        if semester_value not in ALLOWED_SEMESTERS:
                            invalid_rows.append(f"{s['roll_no'] or s['full_name']} (missing semester)")
                            continue
                        parsed_rows.append((s['user_id'], marks, semester_value))

                if not parsed_rows:
                    if invalid_rows:
                        names = ", ".join(invalid_rows[:6])
                        more = " ..." if len(invalid_rows) > 6 else ""
                        flash(f"No valid rows to save. Skipped: {names}{more}", "warning")
                    else:
                        flash("Enter marks for at least one student to save bulk results.", "warning")
                    return redirect_to_grading(exam_type_value=exam_type, academic_year_value=academic_year, search_query_value=search_query_context)

                inserted = 0
                updated = 0
                db_failed_rows = []
                for student_id, marks_value, semester_value in parsed_rows:
                    try:
                        cur.execute("UPDATE users SET semester = %s WHERE user_id = %s", (semester_value, student_id))
                        action = upsert_result(student_id, marks_value)
                        conn.commit()
                        if action == 'inserted':
                            inserted += 1
                        else:
                            updated += 1
                    except mysql.connector.Error:
                        conn.rollback()
                        student_label = enrolled_map.get(student_id, {}).get('roll_no') or enrolled_map.get(student_id, {}).get('full_name') or f"student {student_id}"
                        db_failed_rows.append(student_label)

                if inserted or updated:
                    flash(f"Bulk save complete. Inserted: {inserted}, Updated: {updated}.", "success")

                skipped_rows = invalid_rows + db_failed_rows
                if skipped_rows:
                    names = ", ".join(skipped_rows[:6])
                    more = " ..." if len(skipped_rows) > 6 else ""
                    flash(f"{len(skipped_rows)} row(s) skipped: {names}{more}", "warning")

                return redirect_to_grading(exam_type_value=exam_type, academic_year_value=academic_year, search_query_value=search_query_context)

            flash("Invalid submit mode.", "warning")
            return redirect_to_grading(exam_type_value=exam_type, academic_year_value=academic_year, search_query_value=search_query_context)

        except mysql.connector.Error as e:
            conn.rollback()
            flash(f"Database error while saving result: {e}", "danger")
            return redirect_to_grading(exam_type_value=exam_type, academic_year_value=academic_year, search_query_value=search_query_context)
        finally:
            conn.close()

    selected_exam_type = request.args.get('exam_type', default='Final')
    selected_academic_year = parse_academic_year(request.args.get('academic_year')) or DEFAULT_ACADEMIC_YEAR
    selected_edit_result_id = request.args.get('edit_result_id', type=int)
    search_query = normalize_spaces(request.args.get('search_query'))
    if len(search_query) > 100:
        search_query = search_query[:100]
    if selected_exam_type not in ALLOWED_EXAM_TYPES:
        selected_exam_type = 'Final'

    edit_result = None
    if selected_edit_result_id:
        cur.execute("""
            SELECT result_id, student_id, exam_type, marks_obtained, full_marks, academic_year
            FROM student_results
            WHERE result_id = %s AND course_id = %s
        """, (selected_edit_result_id, course_id))
        edit_result = cur.fetchone()
        if edit_result and edit_result['exam_type'] in ALLOWED_EXAM_TYPES:
            selected_exam_type = edit_result['exam_type']
            selected_academic_year = int(edit_result.get('academic_year') or selected_academic_year)
        elif not edit_result:
            flash("Result not found for editing.", "warning")

    # Students enrolled in this teacher-assigned course
    cur.execute("""
        SELECT u.user_id, u.full_name, u.roll_no, u.semester, u.date_of_birth
        FROM student_enrollments se
        JOIN users u ON se.student_id = u.user_id
        WHERE se.course_id = %s
        ORDER BY u.roll_no, u.full_name
    """, (course_id,))
    students = cur.fetchall()

    results_sql = """
        SELECT r.result_id, r.student_id, u.full_name, u.roll_no, u.semester,
               u.date_of_birth, u.email, u.contact_no, u.gender, u.address,
               d.dept_name AS program_name, r.academic_year,
               r.exam_type, r.marks_obtained, r.full_marks, r.grade, r.gpa
        FROM student_results r
        JOIN users u ON r.student_id = u.user_id
        JOIN courses c ON c.course_id = r.course_id
        LEFT JOIN departments d ON d.dept_id = c.dept_id
        WHERE r.course_id = %s AND r.exam_type = %s AND r.academic_year = %s
    """
    results_params = [course_id, selected_exam_type, selected_academic_year]
    if search_query:
        wildcard = f"%{search_query}%"
        results_sql += """
            AND (
                CAST(u.user_id AS CHAR) LIKE %s OR
                u.full_name LIKE %s OR
                u.roll_no LIKE %s OR
                CAST(u.date_of_birth AS CHAR) LIKE %s OR
                u.email LIKE %s OR
                u.contact_no LIKE %s OR
                u.gender LIKE %s OR
                u.address LIKE %s OR
                u.semester LIKE %s OR
                d.dept_name LIKE %s OR
                CAST(r.academic_year AS CHAR) LIKE %s OR
                r.exam_type LIKE %s OR
                r.grade LIKE %s OR
                CAST(r.marks_obtained AS CHAR) LIKE %s OR
                CAST(r.full_marks AS CHAR) LIKE %s OR
                CAST(r.gpa AS CHAR) LIKE %s
            )
        """
        results_params.extend([wildcard] * 16)
    results_sql += " ORDER BY u.roll_no, u.full_name"
    cur.execute(results_sql, tuple(results_params))
    results = cur.fetchall()
    existing_marks = {row['student_id']: row['marks_obtained'] for row in results}

    conn.close()

    return render_template(
        'teacher_enter_result.html',
        course=course,
        students=students,
        results=results,
        course_id=course_id,
        edit_result=edit_result,
        selected_exam_type=selected_exam_type,
        selected_academic_year=selected_academic_year,
        min_academic_year=MIN_ACADEMIC_YEAR,
        max_academic_year=MAX_ACADEMIC_YEAR,
        semesters=SEMESTER_OPTIONS,
        exam_types=ALLOWED_EXAM_TYPES,
        existing_marks=existing_marks,
        search_query=search_query,
        teacher_name=session.get('name'),
    )

@app.route('/teacher/result/delete/<int:result_id>', methods=['GET', 'POST'])
def teacher_delete_result(result_id):
    if not check_auth('teacher'):
        return redirect(url_for('login'))

    teacher_id = session['user_id']
    requested_exam_type = (request.values.get('exam_type') or '').strip()
    requested_academic_year = parse_academic_year(request.values.get('academic_year'))
    if requested_exam_type not in ALLOWED_EXAM_TYPES:
        requested_exam_type = ''
    requested_search_query = normalize_spaces(request.values.get('search_query'))

    conn = get_db()
    cur = conn.cursor(dictionary=True)

    if request.method == 'POST':
        # Teachers can delete only results from their assigned courses.
        cur.execute("""
            SELECT r.course_id, r.academic_year
            FROM student_results r
            JOIN teacher_courses tc
              ON tc.course_id = r.course_id
             AND tc.teacher_id = %s
            WHERE r.result_id = %s
        """, (teacher_id, result_id))
        res = cur.fetchone()
        if res:
            cur.execute("DELETE FROM student_results WHERE result_id=%s", (result_id,))
            conn.commit()
            align_auto_increment_for_table(conn, "student_results")
            flash("Result deleted successfully.", "success")
            conn.close()
            redirect_kwargs = {'course_id': res['course_id']}
            if requested_exam_type:
                redirect_kwargs['exam_type'] = requested_exam_type
            if requested_academic_year:
                redirect_kwargs['academic_year'] = requested_academic_year
            elif res.get('academic_year'):
                redirect_kwargs['academic_year'] = int(res['academic_year'])
            if requested_search_query:
                redirect_kwargs['search_query'] = requested_search_query
            return redirect(url_for('teacher_enter_result', **redirect_kwargs))

        conn.close()
        flash("Result not found or access denied.", "danger")
        return redirect(url_for('teacher_classes'))

    # GET: Show confirmation page only when this course belongs to the teacher.
    cur.execute("""
        SELECT 
            r.course_id, 
            c.course_name, 
            u.full_name AS student_name,
            r.exam_type,
            r.academic_year,
            r.marks_obtained,
            r.full_marks,
            r.grade,
            r.gpa
        FROM student_results r
        JOIN courses c ON r.course_id = c.course_id
        JOIN users u ON r.student_id = u.user_id
        JOIN teacher_courses tc
          ON tc.course_id = r.course_id
         AND tc.teacher_id = %s
        WHERE r.result_id = %s
    """, (teacher_id, result_id))

    result = cur.fetchone()
    conn.close()

    if not result:
        flash("Result not found or access denied.", "danger")
        return redirect(url_for('teacher_classes'))

    return render_template(
        'teacher_delete_result.html',
        course_id=result['course_id'],
        course_name=result['course_name'],
        student_name=result['student_name'],
        exam_type=result['exam_type'],
        academic_year=result['academic_year'],
        marks_obtained=result['marks_obtained'],
        full_marks=result['full_marks'],
        grade=result['grade'],
        gpa=result['gpa'],
        selected_exam_type=requested_exam_type,
        selected_academic_year=requested_academic_year or int(result['academic_year']),
        search_query=requested_search_query,
    )

@app.route('/teacher/attendance/<int:course_id>', methods=['GET', 'POST'])
def teacher_attendance(course_id):
    if not check_auth('teacher'):
        return redirect(url_for('login'))

    conn = get_db()
    cur = conn.cursor(dictionary=True)

    # Fetch course name
    cur.execute("SELECT course_name FROM courses WHERE course_id=%s", (course_id,))
    course_row = cur.fetchone()
    if not course_row:
        conn.close()
        flash("Course not found.", "danger")
        return redirect(url_for('teacher_classes'))
    course_name = course_row['course_name']

    # Get enrolled students
    cur.execute("""
        SELECT u.user_id, u.full_name
        FROM users u
        JOIN student_enrollments se ON u.user_id = se.student_id
        WHERE se.course_id = %s
        ORDER BY u.full_name
    """, (course_id,))
    students = cur.fetchall()

    if request.method == 'POST':
        dt = request.form['date']

        # Get list of enrolled student IDs for saving (only these students get attendance records)
        cur.execute("SELECT student_id AS user_id FROM student_enrollments WHERE course_id=%s", (course_id,))
        enrolled_ids = cur.fetchall()

        align_auto_increment_for_table(conn, "attendance")

        for s in enrolled_ids:
            status = 'Present' if f"status_{s['user_id']}" in request.form else 'Absent'
            # Delete any existing record for this date (to allow overwrite)
            cur.execute("""
                DELETE FROM attendance
                WHERE course_id=%s AND student_id=%s AND attendance_date=%s
            """, (course_id, s['user_id'], dt))
            # Insert the new record
            cur.execute("""
                INSERT INTO attendance (course_id, student_id, attendance_date, status)
                VALUES (%s, %s, %s, %s)
            """, (course_id, s['user_id'], dt, status))

        conn.commit()
        conn.close()
        flash("Attendance Saved", "success")
        return redirect(url_for('teacher_classes'))

    # GET request - prepare data for template
    today = date.today().isoformat()

    # Pre-fill today's attendance if it exists
    att_dict = {}
    cur.execute("""
        SELECT student_id, status
        FROM attendance
        WHERE course_id=%s AND attendance_date=%s
    """, (course_id, today))
    for row in cur.fetchall():
        att_dict[row['student_id']] = row['status']

    conn.close()

    return render_template(
        'teacher_attendance.html',
        course={'course_name': course_name},
        students=students,
        today=today,
        att_dict=att_dict
    )


@app.route('/assignment/attachment/<int:assignment_id>/download')
def assignment_attachment_download(assignment_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    role = session.get('role')
    user_id = session.get('user_id')
    fallback_endpoint = f"{role}_dashboard" if role in {'admin', 'teacher', 'student'} else 'home'

    conn = get_db()
    try:
        ensure_assignment_tables(conn)
    except mysql.connector.Error as e:
        conn.close()
        flash(f"Database error while downloading file: {e}", "danger")
        return redirect(request.referrer or url_for(fallback_endpoint))

    cur = conn.cursor(dictionary=True)
    if role == 'teacher':
        cur.execute("""
            SELECT ta.attachment_path, ta.attachment_name
            FROM teacher_assignments ta
            JOIN teacher_courses tc
              ON tc.course_id = ta.course_id
             AND tc.teacher_id = %s
            WHERE ta.assignment_id = %s
        """, (user_id, assignment_id))
    elif role == 'student':
        cur.execute("""
            SELECT ta.attachment_path, ta.attachment_name
            FROM teacher_assignments ta
            JOIN student_enrollments se
              ON se.course_id = ta.course_id
             AND se.student_id = %s
            WHERE ta.assignment_id = %s
        """, (user_id, assignment_id))
    elif role == 'admin':
        cur.execute("""
            SELECT attachment_path, attachment_name
            FROM teacher_assignments
            WHERE assignment_id = %s
        """, (assignment_id,))
    else:
        conn.close()
        flash("Access denied.", "danger")
        return redirect(url_for('login'))

    row = cur.fetchone()
    conn.close()

    if not row:
        flash("Attachment not found or access denied.", "danger")
        return redirect(request.referrer or url_for(fallback_endpoint))

    stored_name = row.get('attachment_path')
    original_name = row.get('attachment_name') or stored_name
    if not stored_name:
        flash("No attachment uploaded for this assignment.", "warning")
        return redirect(request.referrer or url_for(fallback_endpoint))

    file_path = os.path.join(UPLOAD_ASSIGNMENTS_DIR, stored_name)
    if not os.path.isfile(file_path):
        flash("Attachment file is missing from server storage.", "danger")
        return redirect(request.referrer or url_for(fallback_endpoint))

    return send_from_directory(
        UPLOAD_ASSIGNMENTS_DIR,
        stored_name,
        as_attachment=True,
        download_name=original_name
    )


@app.route('/assignment/submission/<int:submission_id>/download')
def assignment_submission_download(submission_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    role = session.get('role')
    user_id = session.get('user_id')
    fallback_endpoint = f"{role}_dashboard" if role in {'admin', 'teacher', 'student'} else 'home'

    conn = get_db()
    try:
        ensure_assignment_tables(conn)
    except mysql.connector.Error as e:
        conn.close()
        flash(f"Database error while downloading submission: {e}", "danger")
        return redirect(request.referrer or url_for(fallback_endpoint))

    cur = conn.cursor(dictionary=True)
    if role == 'teacher':
        cur.execute("""
            SELECT s.submission_path, s.submission_name
            FROM assignment_submissions s
            JOIN teacher_assignments ta ON ta.assignment_id = s.assignment_id
            JOIN teacher_courses tc
              ON tc.course_id = ta.course_id
             AND tc.teacher_id = %s
            WHERE s.submission_id = %s
        """, (user_id, submission_id))
    elif role == 'student':
        cur.execute("""
            SELECT submission_path, submission_name
            FROM assignment_submissions
            WHERE submission_id = %s AND student_id = %s
        """, (submission_id, user_id))
    elif role == 'admin':
        cur.execute("""
            SELECT submission_path, submission_name
            FROM assignment_submissions
            WHERE submission_id = %s
        """, (submission_id,))
    else:
        conn.close()
        flash("Access denied.", "danger")
        return redirect(url_for('login'))

    row = cur.fetchone()
    conn.close()

    if not row:
        flash("Submission file not found or access denied.", "danger")
        return redirect(request.referrer or url_for(fallback_endpoint))

    stored_name = row.get('submission_path')
    original_name = row.get('submission_name') or stored_name
    if not stored_name:
        flash("No submission file uploaded.", "warning")
        return redirect(request.referrer or url_for(fallback_endpoint))

    file_path = os.path.join(UPLOAD_SUBMISSIONS_DIR, stored_name)
    if not os.path.isfile(file_path):
        flash("Submission file is missing from server storage.", "danger")
        return redirect(request.referrer or url_for(fallback_endpoint))

    return send_from_directory(
        UPLOAD_SUBMISSIONS_DIR,
        stored_name,
        as_attachment=True,
        download_name=original_name
    )


@app.route('/uploads/profile_photos/<path:stored_name>')
def profile_photo_file(stored_name):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    file_path = os.path.join(UPLOAD_PROFILE_PHOTOS_DIR, stored_name)
    if not os.path.isfile(file_path):
        return redirect(url_for('static', filename='Logo.png'))

    return send_from_directory(UPLOAD_PROFILE_PHOTOS_DIR, stored_name)

# ==========================================
# STUDENT DASHBOARD
# ==========================================
@app.route('/student')
def student_dashboard():
    if not check_auth('student'):
        return redirect(url_for('login'))

    conn = get_db()
    cur = conn.cursor()
    sid = session['user_id']

    # Dashboard stats
    cur.execute("SELECT COUNT(*) FROM student_enrollments WHERE student_id=%s", (sid,))
    course_cnt = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM student_results WHERE student_id=%s", (sid,))
    res_count = cur.fetchone()[0]

    cur.execute("SELECT SUM(amount) FROM fees WHERE student_id=%s AND status='Pending'", (sid,))
    fee_row = cur.fetchone()
    fee_due = fee_row[0] if fee_row[0] else 0

    # Fetch notices for students
    cur.execute("""
        SELECT notice_id, title, content
        FROM notices
        WHERE target_role IN ('all', 'student')
        ORDER BY date_posted DESC
    """)
    notices = cur.fetchall()  # returns list of tuples

    conn.close()

    return render_template(
        'student_dash.html',
        course_cnt=course_cnt,
        res_count=res_count,
        fee_due=fee_due,
        notices=notices
    )



@app.route('/student/enroll', methods=['GET', 'POST'])
def student_enroll():
    if not check_auth('student'): return redirect(url_for('login'))
    conn = get_db(); cur = conn.cursor(dictionary=True)
    sid = session['user_id']
    if request.method == 'POST':
        cid = parse_positive_int(request.form.get('course_id'))
        if not cid:
            flash("Invalid course selection.", "warning")
            conn.close()
            return redirect(url_for('student_enroll'))
        cur.execute("SELECT * FROM student_enrollments WHERE student_id=%s AND course_id=%s", (sid, cid))
        if cur.fetchone(): flash("Already Enrolled")
        else:
            align_auto_increment_for_table(conn, "student_enrollments")
            cur.execute("INSERT INTO student_enrollments (student_id, course_id, date_enrolled) VALUES (%s, %s, %s)", (sid, cid, date.today()))
            conn.commit(); flash("Enrolled Successfully")
        return redirect(url_for('student_enroll'))
    cur.execute("SELECT dept_id FROM users WHERE user_id=%s", (sid,)); row = cur.fetchone()
    dept_id = row['dept_id'] if row else None
    if dept_id:
        cur.execute("SELECT c.course_id, c.course_code, c.course_name FROM courses c WHERE c.dept_id=%s AND c.course_id NOT IN (SELECT course_id FROM student_enrollments WHERE student_id=%s)", (dept_id, sid))
        available = cur.fetchall()
    else: available = []
    cur.execute("SELECT c.course_code, c.course_name, e.date_enrolled FROM student_enrollments e JOIN courses c ON e.course_id=c.course_id WHERE e.student_id=%s", (sid,))
    enrolled = cur.fetchall()
    conn.close()
    return render_template('student_enroll.html', available=available, enrolled=enrolled)


@app.route('/student/assignments')
def student_assignments():
    if not check_auth('student'):
        return redirect(url_for('login'))

    search_query = normalize_spaces(request.args.get('search_query'))
    if len(search_query) > 100:
        search_query = search_query[:100]

    conn = get_db()
    try:
        ensure_assignment_tables(conn)
    except mysql.connector.Error as e:
        conn.close()
        flash(f"Database error while loading assignments: {e}", "danger")
        return redirect(url_for('student_dashboard'))

    cur = conn.cursor(dictionary=True)
    student_id = session['user_id']
    sql = """
        SELECT ta.assignment_id, ta.title, ta.notice, ta.description, ta.due_date, ta.due_time,
               ta.attachment_path, ta.attachment_name, ta.created_at,
               c.course_id, c.course_name, c.course_code,
               t.full_name AS teacher_name,
               s.submission_id,
               COALESCE(s.status, 'not_submitted') AS submission_status,
               s.submission_name, s.submitted_at, s.is_late
        FROM student_enrollments se
        JOIN teacher_assignments ta ON ta.course_id = se.course_id
        JOIN courses c ON c.course_id = ta.course_id
        JOIN users t ON t.user_id = ta.teacher_id
        LEFT JOIN assignment_submissions s
               ON s.assignment_id = ta.assignment_id
              AND s.student_id = se.student_id
        WHERE se.student_id = %s
    """
    params = [student_id]
    if search_query:
        wildcard = f"%{search_query}%"
        sql += """
            AND (
                ta.title LIKE %s OR
                ta.notice LIKE %s OR
                ta.description LIKE %s OR
                c.course_name LIKE %s OR
                c.course_code LIKE %s OR
                t.full_name LIKE %s OR
                COALESCE(s.status, 'not_submitted') LIKE %s OR
                CAST(ta.due_date AS CHAR) LIKE %s OR
                CAST(ta.due_time AS CHAR) LIKE %s
            )
        """
        params.extend([wildcard] * 9)

    sql += """
        ORDER BY
            CASE WHEN ta.due_date IS NULL THEN 1 ELSE 0 END,
            ta.due_date ASC,
            ta.due_time ASC,
            ta.created_at DESC
    """
    cur.execute(sql, tuple(params))
    assignments = cur.fetchall()
    conn.close()

    stats = {
        'total': len(assignments),
        'submitted': 0,
        'turned_in': 0,
        'not_submitted': 0,
    }
    for row in assignments:
        status = row.get('submission_status') or 'not_submitted'
        if status == 'submitted':
            stats['submitted'] += 1
        elif status == 'turned_in':
            stats['turned_in'] += 1
        else:
            stats['not_submitted'] += 1

    return render_template(
        'student_assignments.html',
        assignments=assignments,
        stats=stats,
        search_query=search_query,
    )


@app.route('/student/assignment/<int:assignment_id>', methods=['GET', 'POST'])
def student_assignment_detail(assignment_id):
    if not check_auth('student'):
        return redirect(url_for('login'))

    conn = get_db()
    try:
        ensure_assignment_tables(conn)
    except mysql.connector.Error as e:
        conn.close()
        flash(f"Database error while loading assignment detail: {e}", "danger")
        return redirect(url_for('student_assignments'))

    cur = conn.cursor(dictionary=True)
    student_id = session['user_id']
    cur.execute("""
        SELECT ta.assignment_id, ta.course_id, ta.teacher_id, ta.title, ta.notice, ta.description, ta.due_date, ta.due_time,
               ta.attachment_path, ta.attachment_name, ta.created_at,
               c.course_name, c.course_code,
               u.full_name AS teacher_name
        FROM teacher_assignments ta
        JOIN student_enrollments se
          ON se.course_id = ta.course_id
         AND se.student_id = %s
        JOIN courses c ON c.course_id = ta.course_id
        JOIN users u ON u.user_id = ta.teacher_id
        WHERE ta.assignment_id = %s
    """, (student_id, assignment_id))
    assignment = cur.fetchone()
    if not assignment:
        conn.close()
        flash("Assignment not found or access denied.", "danger")
        return redirect(url_for('student_assignments'))

    submission = get_or_create_assignment_submission(conn, cur, assignment_id, student_id)
    conn.commit()

    if request.method == 'POST':
        action = (request.form.get('action') or '').strip().lower()

        if action == 'turned_in':
            if submission['status'] == 'submitted':
                conn.close()
                flash("Assignment is already submitted. Use submit to resubmit a new file.", "info")
                return redirect(url_for('student_assignment_detail', assignment_id=assignment_id))

            submitted_at = datetime.now()
            is_late = compute_submission_late_flag(assignment['due_date'], assignment.get('due_time'), submitted_at)
            try:
                cur.execute("""
                    UPDATE assignment_submissions
                    SET status = 'turned_in',
                        submitted_at = %s,
                        is_late = %s
                    WHERE submission_id = %s AND student_id = %s
                """, (submitted_at, is_late, submission['submission_id'], student_id))
                conn.commit()
                flash("Assignment marked as turned in.", "success")
            except mysql.connector.Error as e:
                conn.rollback()
                flash(f"Database error while updating status: {e}", "danger")

            conn.close()
            return redirect(url_for('student_assignment_detail', assignment_id=assignment_id))

        if action == 'submit':
            uploaded_file = request.files.get('submission_file')
            old_path = submission.get('submission_path')
            new_path = None
            new_name = None
            has_new_upload = bool(uploaded_file and (uploaded_file.filename or '').strip())

            if has_new_upload:
                new_path, new_name = save_uploaded_file(uploaded_file, UPLOAD_SUBMISSIONS_DIR)
                if not new_path:
                    conn.close()
                    flash("Invalid submission file name.", "warning")
                    return redirect(url_for('student_assignment_detail', assignment_id=assignment_id))
            elif not old_path:
                conn.close()
                flash("Please upload a file before submitting.", "warning")
                return redirect(url_for('student_assignment_detail', assignment_id=assignment_id))

            submitted_at = datetime.now()
            is_late = compute_submission_late_flag(assignment['due_date'], assignment.get('due_time'), submitted_at)
            try:
                if has_new_upload:
                    cur.execute("""
                        UPDATE assignment_submissions
                        SET status = 'submitted',
                            submission_path = %s,
                            submission_name = %s,
                            submitted_at = %s,
                            is_late = %s
                        WHERE submission_id = %s AND student_id = %s
                    """, (new_path, new_name, submitted_at, is_late, submission['submission_id'], student_id))
                else:
                    cur.execute("""
                        UPDATE assignment_submissions
                        SET status = 'submitted',
                            submitted_at = %s,
                            is_late = %s
                        WHERE submission_id = %s AND student_id = %s
                    """, (submitted_at, is_late, submission['submission_id'], student_id))
                conn.commit()
            except mysql.connector.Error as e:
                conn.rollback()
                remove_uploaded_file_if_exists(UPLOAD_SUBMISSIONS_DIR, new_path)
                conn.close()
                flash(f"Database error while submitting assignment: {e}", "danger")
                return redirect(url_for('student_assignment_detail', assignment_id=assignment_id))

            if has_new_upload and old_path and old_path != new_path:
                remove_uploaded_file_if_exists(UPLOAD_SUBMISSIONS_DIR, old_path)

            conn.close()
            flash("Assignment submitted successfully.", "success")
            return redirect(url_for('student_assignment_detail', assignment_id=assignment_id))

        if action == 'comment':
            comment_text = sanitize_assignment_text(request.form.get('comment_text'), MAX_ASSIGNMENT_COMMENT_LENGTH)
            if not comment_text:
                conn.close()
                flash("Comment cannot be empty.", "warning")
                return redirect(url_for('student_assignment_detail', assignment_id=assignment_id))

            try:
                align_auto_increment_for_table(conn, "assignment_comments")
                cur.execute("""
                    INSERT INTO assignment_comments (submission_id, sender_id, sender_role, comment_text)
                    VALUES (%s, %s, 'student', %s)
                """, (submission['submission_id'], student_id, comment_text))
                conn.commit()
                flash("Private comment sent.", "success")
            except mysql.connector.Error as e:
                conn.rollback()
                flash(f"Database error while posting comment: {e}", "danger")

            conn.close()
            return redirect(url_for('student_assignment_detail', assignment_id=assignment_id))

        conn.close()
        flash("Invalid action.", "warning")
        return redirect(url_for('student_assignment_detail', assignment_id=assignment_id))

    cur.execute("""
        SELECT submission_id, assignment_id, student_id, status, submission_path, submission_name,
               submitted_at, is_late, created_at, updated_at
        FROM assignment_submissions
        WHERE submission_id = %s
    """, (submission['submission_id'],))
    submission = cur.fetchone()

    cur.execute("""
        SELECT c.comment_id, c.comment_text, c.created_at, c.sender_role, u.full_name AS sender_name
        FROM assignment_comments c
        JOIN users u ON u.user_id = c.sender_id
        WHERE c.submission_id = %s
        ORDER BY c.created_at ASC, c.comment_id ASC
    """, (submission['submission_id'],))
    comments = cur.fetchall()
    conn.close()

    return render_template(
        'student_assignment_detail.html',
        assignment=assignment,
        submission=submission,
        comments=comments,
    )


@app.route('/student/results', methods=['GET', 'POST'])
def student_results():
    if not check_auth('student'):
        return redirect(url_for('login'))

    conn = get_db()
    try:
        ensure_users_date_of_birth_column(conn)
        ensure_courses_credit_hour_column(conn)
        ensure_student_results_metadata_columns(conn)
    except mysql.connector.Error as e:
        conn.close()
        flash(f"Database error while preparing transcript data: {e}", "danger")
        return redirect(url_for('student_dashboard'))

    cur = conn.cursor(dictionary=True)
    student_id = session['user_id']

    cur.execute("""
        SELECT user_id, full_name, roll_no, semester, date_of_birth
        FROM users
        WHERE user_id = %s AND role = 'student'
    """, (student_id,))
    student = cur.fetchone()
    if not student:
        conn.close()
        flash("Student account not found.", "danger")
        return redirect(url_for('student_dashboard'))

    entered_roll_no = ''
    entered_dob = ''
    verified = False
    transcript_rows = []
    total_credit_hours = Decimal('0.00')
    total_weighted_gpa = Decimal('0.00')
    weighted_average_gpa = Decimal('0.00')

    if request.method == 'POST':
        entered_roll_no = (request.form.get('roll_no') or '').strip().upper()
        entered_dob = (request.form.get('date_of_birth') or '').strip()
        parsed_dob = parse_iso_date(entered_dob)

        stored_roll_no = (student.get('roll_no') or '').strip().upper()
        stored_dob = student.get('date_of_birth')

        if not entered_roll_no or not parsed_dob:
            flash("Please enter valid roll number and date of birth.", "warning")
        elif not stored_roll_no or not stored_dob:
            flash("Your account is missing roll number or date of birth. Contact admin.", "danger")
        elif entered_roll_no != stored_roll_no or parsed_dob != stored_dob:
            flash("Roll number or date of birth did not match your account.", "danger")
        else:
            verified = True
            cur.execute("""
                SELECT
                    c.course_code,
                    c.course_name,
                    c.credit_hour,
                    d.dept_name AS program_name,
                    u.semester,
                    r.academic_year,
                    ROUND(AVG(r.gpa), 2) AS achieved_gpa
                FROM student_results r
                JOIN courses c ON r.course_id = c.course_id
                LEFT JOIN departments d ON d.dept_id = c.dept_id
                JOIN users u ON u.user_id = r.student_id
                WHERE r.student_id = %s
                GROUP BY c.course_id, c.course_code, c.course_name, c.credit_hour, d.dept_name, u.semester, r.academic_year
                ORDER BY r.academic_year DESC, c.course_code, c.course_name
            """, (student_id,))
            transcript_rows = cur.fetchall()

            for row in transcript_rows:
                credit_hour = Decimal(str(row.get('credit_hour') or 0))
                achieved_gpa = Decimal(str(row.get('achieved_gpa') or 0))
                total_gpa = Decimal('4.00')
                weighted_gpa = credit_hour * achieved_gpa

                row['credit_hour'] = credit_hour.quantize(Decimal('0.00'))
                row['total_gpa'] = total_gpa.quantize(Decimal('0.00'))
                row['achieved_gpa'] = achieved_gpa.quantize(Decimal('0.00'))
                row['weighted_gpa'] = weighted_gpa.quantize(Decimal('0.00'))

                total_credit_hours += credit_hour
                total_weighted_gpa += weighted_gpa

            total_credit_hours = total_credit_hours.quantize(Decimal('0.00'))
            total_weighted_gpa = total_weighted_gpa.quantize(Decimal('0.00'))
            if total_credit_hours > 0:
                weighted_average_gpa = (total_weighted_gpa / total_credit_hours).quantize(Decimal('0.00'))
            else:
                weighted_average_gpa = Decimal('0.00')

    conn.close()

    return render_template(
        'student_results.html',
        student=student,
        verified=verified,
        entered_roll_no=entered_roll_no,
        entered_dob=entered_dob,
        transcript_rows=transcript_rows,
        total_credit_hours=total_credit_hours,
        total_weighted_gpa=total_weighted_gpa,
        weighted_average_gpa=weighted_average_gpa,
        generated_on=datetime.now().strftime("%Y-%m-%d %H:%M"),
    )

@app.route('/student/attendance')
def student_attendance():
    if not check_auth('student'):
        return redirect(url_for('login'))

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT 
            c.course_name,
            COUNT(*) AS total_classes,
            SUM(CASE WHEN a.status='Present' THEN 1 ELSE 0 END) AS present_classes
        FROM attendance a
        JOIN courses c ON a.course_id = c.course_id
        WHERE a.student_id = %s
        GROUP BY c.course_id
    """, (session['user_id'],))

    records = cur.fetchall()
    conn.close()

    return render_template('student_attendance.html', records=records)


@app.route('/student/fees')
def student_fees():
    if not check_auth('student'):
        return redirect(url_for('login'))

    conn = get_db()
    cur = conn.cursor(dictionary=True)  # <- IMPORTANT
    cur.execute("SELECT * FROM fees WHERE student_id=%s", (session['user_id'],))
    fees = cur.fetchall()
    conn.close()

    return render_template('student_fees.html', fees=fees)


@app.route('/student/exams')
def student_exams():
    if not check_auth('student'):
        return redirect(url_for('login'))

    conn = get_db()
    cur = conn.cursor()   # ❗ NO dictionary=True

    cur.execute("""
        SELECT 
            c.course_name,
            e.exam_date,
            e.start_time,
            e.room_no
        FROM exam_schedule e
        JOIN courses c ON e.course_id = c.course_id
        ORDER BY e.exam_date, e.start_time
    """)

    exams = cur.fetchall()
    conn.close()

    return render_template('student_exams.html', exams=exams)

# ==========================================
# STUDENT LIBRARY ROUTES (ADDED)
# ==========================================

@app.route('/student/library')
def library_view():
    if not check_auth('student'):
        return redirect(url_for('login'))

    conn = get_db()
    cur = conn.cursor(dictionary=True)

    # Fetch books with calculated availability (Total - Unreturned Borrows)
    query = """
        SELECT b.book_id, b.title, b.author, b.isbn, b.copies_total, 
               c.name as category_name,
               (b.copies_total - (
                   SELECT COUNT(*) 
                   FROM borrows 
                   WHERE book_id = b.book_id AND return_date IS NULL
               )) as copies_available
        FROM library_books b
        LEFT JOIN book_categories c ON b.category_id = c.category_id
        ORDER BY b.title
    """
    cur.execute(query)
    books = cur.fetchall()

    # Sanitize None values in case database is fresh
    for book in books:
        if book['copies_available'] is None:
            book['copies_available'] = book['copies_total']

    # ✅ Fetch this student's borrowed details for "My Borrows" section
    student_id = session['user_id']
    my_borrows_query = """
        SELECT 
            br.borrow_id,
            b.title AS book_title,
            br.borrow_date,
            br.due_date,
            br.return_date,
            br.fine
        FROM borrows br
        JOIN library_books b ON br.book_id = b.book_id
        WHERE br.student_id = %s AND br.return_date IS NULL
        ORDER BY br.borrow_date DESC
    """
    cur.execute(my_borrows_query, (student_id,))
    my_borrows = cur.fetchall()

    # ✅ Compute is_overdue exactly how your template expects
    today = date.today()
    for br in my_borrows:
        br['fine'] = br['fine'] if br['fine'] is not None else 0
        br['is_overdue'] = (br['return_date'] is None and br['due_date'] is not None and br['due_date'] < today)

    conn.close()
    return render_template('library_view.html', books=books, my_borrows=my_borrows)


@app.route('/student/borrow/<int:book_id>')
def student_borrow_book(book_id):
    if not check_auth('student'):
        return redirect(url_for('login'))

    student_id = session['user_id']
    today = date.today()
    due_date = today + timedelta(days=14)  # 2 weeks due date

    conn = get_db()
    cur = conn.cursor(dictionary=True)

    # 1. Check if student already has THIS book borrowed and not returned
    cur.execute("""
        SELECT * FROM borrows 
        WHERE student_id = %s AND book_id = %s AND return_date IS NULL
    """, (student_id, book_id))
    existing_borrow = cur.fetchone()

    if existing_borrow:
        flash("You have already borrowed this book and haven't returned it yet.", "warning")
        conn.close()
        return redirect(url_for('library_view'))

    # 2. Check stock availability
    cur.execute("""
        SELECT (copies_total - (
            SELECT COUNT(*) FROM borrows WHERE book_id = %s AND return_date IS NULL
        )) as available
        FROM library_books WHERE book_id = %s
    """, (book_id, book_id))
    result = cur.fetchone()

    if result and result['available'] > 0:
        # 3. Issue the book
        align_auto_increment_for_table(conn, "borrows")
        cur.execute("""
            INSERT INTO borrows (book_id, student_id, borrow_date, due_date)
            VALUES (%s, %s, %s, %s)
        """, (book_id, student_id, today, due_date))
        conn.commit()
        flash(f"Book borrowed successfully! Please return by {due_date}", "success")
    else:
        flash("Sorry, this book is currently out of stock.", "danger")

    conn.close()
    return redirect(url_for('library_view'))


# ✅ This route is required because your library_view.html calls url_for('student_return_book', borrow_id=...)
@app.route('/student/return/<int:borrow_id>')
def student_return_book(borrow_id):
    if not check_auth('student'):
        return redirect(url_for('login'))

    student_id = session['user_id']
    today = date.today()

    conn = get_db()
    cur = conn.cursor(dictionary=True)

    # Only allow returning your own active borrow record
    cur.execute("""
        UPDATE borrows
        SET return_date = %s
        WHERE borrow_id = %s AND student_id = %s AND return_date IS NULL
    """, (today, borrow_id, student_id))

    conn.commit()
    conn.close()

    flash("Book returned successfully.", "success")
    return redirect(url_for('library_view'))


if __name__ == '__main__':
    app.run(debug=True)

