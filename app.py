from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv
import mysql.connector
from datetime import date, datetime, timedelta
import os

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "dev_secret_key")

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
# AUTHENTICATION
# ==========================================

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
        full_name = request.form['full_name'].strip()
        email = request.form['email'].strip()
        contact_no = request.form.get('contact_no', '').strip()
        address = request.form.get('address', '').strip()
        gender = request.form.get('gender', '').strip()
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
    name = request.form.get('name')
    if name:
        try:
            conn = get_db()
            cur = conn.cursor()
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
    title = request.form.get('title')
    author = request.form.get('author')
    category_id = request.form.get('category')
    isbn = request.form.get('isbn')
    copies = request.form.get('copies')

    if title and author and category_id and isbn and copies:
        try:
            conn = get_db()
            cur = conn.cursor()
            if book_id:
                cur.execute("""
                    UPDATE library_books
                    SET title = %s, author = %s, category_id = %s, isbn = %s, copies_total = %s
                    WHERE book_id = %s
                """, (title, author, category_id, isbn, copies, book_id))
                flash('Book updated successfully!', 'success')
            else:
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
    
    borrow_id = request.form.get('borrow_id')
    due_date = request.form.get('due_date')
    fine = request.form.get('fine')
    return_date = request.form.get('return_date')
    
    if not return_date:
        return_date = None

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
        dept_name = request.form['dept_name']
        hod_name = request.form.get('hod_name') # Optional field
        edit_id = request.form.get('edit_id')

        if edit_id:
            cursor.execute(
                "UPDATE departments SET dept_name = %s, hod_name = %s WHERE dept_id = %s",
                (dept_name, hod_name, edit_id)
            )
            flash('Department updated successfully!', 'success')
        else:
            cursor.execute(
                "INSERT INTO departments (dept_name, hod_name) VALUES (%s, %s)",
                (dept_name, hod_name)
            )
            flash('Department added successfully!', 'success')

        conn.commit()
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
        conn.commit(); flash("Department Deleted")
    except: flash("Error: Cannot delete department. Dependent records exist.")
    conn.close()
    return redirect(url_for('manage_departments'))



@app.route('/admin/students', methods=['GET', 'POST'])
def manage_students():
    if not check_auth('admin'):
        return redirect(url_for('login'))

    conn = get_db()
    cur = conn.cursor(dictionary=True)
    edit_student = None

    # --- 1. HANDLE ADDING NEW STUDENT (POST) ---
    if request.method == 'POST':
        edit_id = request.form.get('edit_id')
        try:
            roll_no = request.form['roll_no'].strip().upper()
            contact_no = request.form['contact_no'].strip()
            gender = request.form['gender']
            address = request.form['address'].strip()
            enroll_date = request.form['enroll_date']
            full_name = request.form['full_name'].strip()
            email = request.form['email'].strip()
            dept_id = request.form['dept_id']
            semester = request.form['semester']

            if edit_id:
                cur.execute(
                    "SELECT user_id FROM users WHERE user_id = %s AND role = 'student'",
                    (edit_id,)
                )
                if not cur.fetchone():
                    flash("Student not found.", "danger")
                else:
                    new_password = request.form.get('password', '').strip()
                    if new_password:
                        password_hash = generate_password_hash(new_password)
                        cur.execute("""
                            UPDATE users
                            SET roll_no = %s, full_name = %s, email = %s, password = %s,
                                dept_id = %s, semester = %s, enroll_date = %s,
                                contact_no = %s, gender = %s, address = %s
                            WHERE user_id = %s AND role = 'student'
                        """, (
                            roll_no, full_name, email, password_hash, dept_id, semester,
                            enroll_date if enroll_date else date.today(),
                            contact_no, gender, address, edit_id
                        ))
                    else:
                        cur.execute("""
                            UPDATE users
                            SET roll_no = %s, full_name = %s, email = %s,
                                dept_id = %s, semester = %s, enroll_date = %s,
                                contact_no = %s, gender = %s, address = %s
                            WHERE user_id = %s AND role = 'student'
                        """, (
                            roll_no, full_name, email, dept_id, semester,
                            enroll_date if enroll_date else date.today(),
                            contact_no, gender, address, edit_id
                        ))
                    conn.commit()
                    flash("Student updated successfully.", "success")
            else:
                password_hash = generate_password_hash(request.form['password'])
                cur.execute("""INSERT INTO users 
                               (roll_no, full_name, email, password, role, dept_id, semester, 
                                enroll_date, contact_no, gender, address) 
                               VALUES (%s, %s, %s, %s, 'student', %s, %s, %s, %s, %s, %s)""",
                            (roll_no,
                             full_name,
                             email,
                             password_hash,
                             dept_id,
                             semester,
                             enroll_date if enroll_date else date.today(),
                             contact_no,
                             gender,
                             address))
                conn.commit()
                flash("Student added successfully.", "success")
        except mysql.connector.Error as e:
            conn.rollback()
            if e.errno == 1062:  # Duplicate entry
                if 'roll_no' in str(e):
                    flash("Error: This Roll No already exists.", "danger")
                elif 'email' in str(e):
                    flash("Error: This Email already exists.", "danger")
                else:
                    flash("Error: Duplicate entry (Roll No or Email).", "danger")
            else:
                flash(f"Error adding student: {e}", "danger")
        return redirect(url_for('manage_students'))

    # --- 2. HANDLE GLOBAL SEARCH & LISTING (GET) ---
    search_query = request.args.get('search_query')

    # Base query: Join users with departments
    base_query = """
        SELECT u.user_id, u.roll_no, u.full_name, u.email, u.semester, 
               d.dept_name, u.enroll_date, u.contact_no, u.gender, u.address
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
                CAST(u.enroll_date AS CHAR) LIKE %s
            )
            ORDER BY u.roll_no ASC
        """
        wildcard = f"%{search_query}%"
        # We must provide the wildcard variable once for every %s placeholder above (9 times)
        cur.execute(sql, (wildcard, wildcard, wildcard, wildcard, wildcard, wildcard, wildcard, wildcard, wildcard))
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
                   enroll_date, contact_no, gender, address
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
                SELECT u.full_name
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
    cur = conn.cursor(dictionary=True)
    edit_teacher = None

    # --- 1. HANDLE ADDING NEW TEACHER (POST) ---
    if request.method == 'POST':
        edit_id = request.form.get('edit_id')
        try:
            contact_no = request.form['contact_no'].strip()
            gender = request.form['gender']
            address = request.form['address'].strip()
            full_name = request.form['full_name'].strip()
            email = request.form['email'].strip()
            dept_id = request.form['dept_id']

            if edit_id:
                cur.execute(
                    "SELECT user_id FROM users WHERE user_id = %s AND role = 'teacher'",
                    (edit_id,)
                )
                if not cur.fetchone():
                    flash("Teacher not found.", "danger")
                else:
                    new_password = request.form.get('password', '').strip()
                    if new_password:
                        password_hash = generate_password_hash(new_password)
                        cur.execute("""
                            UPDATE users
                            SET full_name = %s, email = %s, password = %s, dept_id = %s,
                                contact_no = %s, gender = %s, address = %s
                            WHERE user_id = %s AND role = 'teacher'
                        """, (full_name, email, password_hash, dept_id, contact_no, gender, address, edit_id))
                    else:
                        cur.execute("""
                            UPDATE users
                            SET full_name = %s, email = %s, dept_id = %s,
                                contact_no = %s, gender = %s, address = %s
                            WHERE user_id = %s AND role = 'teacher'
                        """, (full_name, email, dept_id, contact_no, gender, address, edit_id))
                    conn.commit()
                    flash("Teacher updated successfully.", "success")
            else:
                password_hash = generate_password_hash(request.form['password'])
                cur.execute("""INSERT INTO users 
                               (full_name, email, password, role, dept_id, 
                                contact_no, gender, address) 
                               VALUES (%s, %s, %s, 'teacher', %s, %s, %s, %s)""",
                            (full_name, email, password_hash, dept_id, contact_no, gender, address))
                conn.commit()
                flash("Teacher added successfully.", "success")
        except mysql.connector.Error as e:
            conn.rollback()
            if e.errno == 1062:  # Duplicate entry
                if 'email' in str(e):
                    flash("Error: This Email already exists.", "danger")
                else:
                    flash("Error: Duplicate entry (Email).", "danger")
            else:
                flash(f"Error adding teacher: {e}", "danger")
        return redirect(url_for('manage_teachers'))

    # --- 2. HANDLE SEARCH & LISTING (GET) ---
    search_query = request.args.get('search_query')

    # Base query: Join users with departments
    base_query = """
        SELECT u.user_id, u.full_name, u.email, 
               d.dept_name, u.contact_no, u.gender, u.address
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
            SELECT user_id, full_name, email, dept_id, contact_no, gender, address
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
    conn = get_db(); cur = conn.cursor()
    cur.execute("DELETE FROM users WHERE user_id=%s", (id,))
    conn.commit(); flash("Teacher Deleted")
    conn.close()
    return redirect(url_for('manage_teachers'))

@app.route('/admin/courses', methods=['GET', 'POST'])
def manage_courses():
    if not check_auth('admin'): return redirect(url_for('login'))
    conn = get_db(); cur = conn.cursor(dictionary=True)
    edit_course = None

    if request.method == 'POST':
        edit_id = request.form.get('edit_id')
        try:
            if edit_id:
                cur.execute("""
                    UPDATE courses
                    SET course_name = %s, course_code = %s, dept_id = %s
                    WHERE course_id = %s
                """, (request.form['course_name'], request.form['course_code'], request.form['dept_id'], edit_id))
                flash("Course Updated")
            else:
                cur.execute("""
                    INSERT INTO courses (course_name, course_code, dept_id)
                    VALUES (%s, %s, %s)
                """, (request.form['course_name'], request.form['course_code'], request.form['dept_id']))
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
        SELECT c.course_id, c.course_name, c.course_code, c.dept_id, d.dept_name
        FROM courses c
        LEFT JOIN departments d ON c.dept_id = d.dept_id
    """)
    courses = cur.fetchall()
    cur.execute("SELECT * FROM departments")
    depts = cur.fetchall()

    edit_id = request.args.get('edit_id', type=int)
    if edit_id:
        cur.execute("""
            SELECT course_id, course_name, course_code, dept_id
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
    conn.commit(); flash("Course Deleted")
    conn.close()
    return redirect(url_for('manage_courses'))

@app.route('/admin/assign', methods=['GET', 'POST'])
def assign_course():
    if not check_auth('admin'): return redirect(url_for('login'))
    conn = get_db(); cur = conn.cursor(dictionary=True)
    if request.method == 'POST':
        cur.execute("INSERT INTO teacher_courses (teacher_id, course_id) VALUES (%s, %s)", 
                    (request.form['teacher_id'], request.form['course_id']))
        conn.commit(); flash("Assigned Successfully")
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
    conn.commit(); flash("Assignment Removed")
    conn.close()
    return redirect(url_for('assign_course'))

@app.route('/admin/exams', methods=['GET', 'POST'])
def manage_exams():
    if not check_auth('admin'): return redirect(url_for('login'))
    conn = get_db(); cur = conn.cursor(dictionary=True)
    edit_exam = None

    if request.method == 'POST':
        edit_id = request.form.get('edit_id')
        if edit_id:
            cur.execute("""
                UPDATE exam_schedule
                SET course_id = %s, exam_date = %s, start_time = %s, room_no = %s
                WHERE exam_id = %s
            """, (
                request.form['course_id'],
                request.form['exam_date'],
                request.form['exam_time'],
                request.form['room_no'],
                edit_id
            ))
            conn.commit(); flash("Exam Updated")
        else:
            cur.execute("""
                INSERT INTO exam_schedule (course_id, exam_date, start_time, room_no)
                VALUES (%s, %s, %s, %s)
            """, (
                request.form['course_id'],
                request.form['exam_date'],
                request.form['exam_time'],
                request.form['room_no']
            ))
            conn.commit(); flash("Exam Scheduled")
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
    conn.commit(); flash("Exam Deleted")
    conn.close()
    return redirect(url_for('manage_exams'))

@app.route('/admin/fees', methods=['GET', 'POST'])
def manage_fees():
    if not check_auth('admin'): return redirect(url_for('login'))
    conn = get_db(); cur = conn.cursor(dictionary=True)
    edit_fee = None

    if request.method == 'POST':
        edit_id = request.form.get('edit_id')
        if edit_id:
            cur.execute("""
                UPDATE fees
                SET student_id = %s, amount = %s, description = %s, status = %s
                WHERE fee_id = %s
            """, (
                request.form['student_id'],
                request.form['amount'],
                request.form['description'],
                request.form['status'],
                edit_id
            ))
            conn.commit(); flash("Invoice Updated")
        else:
            cur.execute("""
                INSERT INTO fees (student_id, amount, description, status)
                VALUES (%s, %s, %s, %s)
            """, (
                request.form['student_id'],
                request.form['amount'],
                request.form['description'],
                request.form['status']
            ))
            conn.commit(); flash("Invoice Created")
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
    conn.commit(); flash("Record Deleted")
    conn.close()
    return redirect(url_for('manage_fees'))

@app.route('/admin/notices', methods=['GET', 'POST'])
def manage_notices():
    if not check_auth('admin'): return redirect(url_for('login'))
    conn = get_db(); cur = conn.cursor(dictionary=True)
    if request.method == 'POST':
        cur.execute("INSERT INTO notices (title, content, target_role) VALUES (%s, %s, %s)",
                    (request.form['title'], request.form['content'], request.form['target_role']))
        conn.commit(); flash("Notice Published")
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
    conn.commit(); flash("Notice Deleted")
    conn.close()
    return redirect(url_for('manage_notices'))

# ==========================================
# TEACHER DASHBOARD
# ==========================================

@app.route('/teacher')
def teacher_dashboard():
    if not check_auth('teacher'):
        return redirect(url_for('login'))

    conn = get_db()
    cur = conn.cursor()
    uid = session['user_id']

    # Count of teacher courses
    cur.execute("SELECT COUNT(*) FROM teacher_courses WHERE teacher_id=%s", (uid,))
    classes_cnt = cur.fetchone()[0]

    # Fetch notices for teachers (or all)
    cur.execute("""
        SELECT notice_id, title, content
        FROM notices
        WHERE target_role IN ('all', 'teacher')
        ORDER BY date_posted DESC
    """)
    notices = cur.fetchall()  # list of tuples

    conn.close()

    return render_template(
        'teacher_dash.html',
        classes_count=classes_cnt,
        notices=notices
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
    cur = conn.cursor(dictionary=True)

    # Fetch course details
    cur.execute("SELECT course_id, course_name FROM courses WHERE course_id=%s", (course_id,))
    course_row = cur.fetchone()
    if not course_row:
        conn.close()
        flash("Course not found.", "danger")
        return redirect(url_for('teacher_classes'))

    course = (course_row['course_id'], course_row['course_name'])

    if request.method == 'POST':
        try:
            student_id = request.form['student_id']
            if not student_id:
                flash("Please select a student.", "warning")
                return redirect(url_for('teacher_enter_result', course_id=course_id))

            marks = float(request.form['marks'])
            full_marks = float(request.form['full_marks'])
            exam_type = request.form['exam_type']

            if marks > full_marks or marks < 0 or full_marks <= 0:
                flash("Invalid marks entered.", "warning")
                return redirect(url_for('teacher_enter_result', course_id=course_id))

            # Check if student is enrolled (safety check)
            cur.execute("SELECT 1 FROM student_enrollments WHERE student_id=%s AND course_id=%s",
                        (student_id, course_id))
            if not cur.fetchone():
                flash("Selected student is not enrolled in this course.", "danger")
                return redirect(url_for('teacher_enter_result', course_id=course_id))

            grade, gpa = calculate_grade_gpa(marks, full_marks)

            # Check if record already exists
            cur.execute("""
                SELECT result_id FROM student_results 
                WHERE student_id=%s AND course_id=%s AND exam_type=%s
            """, (student_id, course_id, exam_type))
            exists = cur.fetchone()

            if exists:
                cur.execute("""
                    UPDATE student_results 
                    SET marks_obtained=%s, full_marks=%s, grade=%s, gpa=%s 
                    WHERE result_id=%s
                """, (marks, full_marks, grade, gpa, exists['result_id']))
                flash(f"Updated {exam_type} result", "success")
            else:
                cur.execute("""
                    INSERT INTO student_results 
                    (student_id, course_id, marks_obtained, full_marks, grade, gpa, exam_type) 
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (student_id, course_id, marks, full_marks, grade, gpa, exam_type))
                flash(f"Saved {exam_type} result", "success")

            conn.commit()
        except ValueError:
            flash("Marks must be valid numbers.", "warning")
        except Exception as e:
            flash("Error saving result.", "danger")

        return redirect(url_for('teacher_enter_result', course_id=course_id))

    # GET: Load enrolled students only
    cur.execute("""
        SELECT u.user_id, u.full_name, COALESCE(u.semester, 'N/A') AS semester
        FROM users u
        JOIN student_enrollments se ON u.user_id = se.student_id
        WHERE se.course_id = %s
        ORDER BY u.full_name
    """, (course_id,))
    students_raw = cur.fetchall()
    students = [(s['user_id'], s['full_name'], s['semester']) for s in students_raw]

    # Load existing results with result_id for delete
    cur.execute("""
        SELECT u.full_name, 
               r.marks_obtained, r.full_marks, r.grade, r.gpa, 
               r.exam_type, r.result_id
        FROM student_results r 
        JOIN users u ON r.student_id = u.user_id 
        WHERE r.course_id = %s 
        ORDER BY r.exam_type, u.full_name
    """, (course_id,))
    results_raw = cur.fetchall()
    results = [
        (r['full_name'], r['marks_obtained'], r['full_marks'], 
         r['grade'], r['gpa'], r['exam_type'], r['result_id'])
        for r in results_raw
    ]

    conn.close()

    return render_template(
        'teacher_enter_result.html',
        course=course,
        students=students,
        results=results,
        course_id=course_id
    )

@app.route('/teacher/result/delete/<int:result_id>', methods=['GET', 'POST'])
def teacher_delete_result(result_id):
    if not check_auth('teacher'):
        return redirect(url_for('login'))

    conn = get_db()
    cur = conn.cursor(dictionary=True)

    if request.method == 'POST':
        # Perform the deletion
        cur.execute("SELECT course_id FROM student_results WHERE result_id=%s", (result_id,))
        res = cur.fetchone()
        
        if res:
            cur.execute("DELETE FROM student_results WHERE result_id=%s", (result_id,))
            conn.commit()
            flash("Result deleted successfully.", "success")
            conn.close()
            return redirect(url_for('teacher_enter_result', course_id=res['course_id']))
        
        conn.close()
        flash("Result not found.", "danger")
        return redirect(url_for('teacher_dashboard'))

    # GET request → Show confirmation page
    cur.execute("""
        SELECT 
            r.course_id, 
            c.course_name, 
            u.full_name AS student_name,
            r.exam_type,
            r.marks_obtained,
            r.full_marks,
            r.grade,
            r.gpa
        FROM student_results r
        JOIN courses c ON r.course_id = c.course_id
        JOIN users u ON r.student_id = u.user_id
        WHERE r.result_id = %s
    """, (result_id,))
    
    result = cur.fetchone()
    conn.close()

    if not result:
        flash("Result not found.", "danger")
        return redirect(url_for('teacher_dashboard'))

    return render_template(
        'teacher_delete_result.html',
        course_id=result['course_id'],
        course_name=result['course_name'],
        student_name=result['student_name'],
        exam_type=result['exam_type'],
        marks_obtained=result['marks_obtained'],
        full_marks=result['full_marks'],
        grade=result['grade'],
        gpa=result['gpa']
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
        cid = request.form['course_id']
        cur.execute("SELECT * FROM student_enrollments WHERE student_id=%s AND course_id=%s", (sid, cid))
        if cur.fetchone(): flash("Already Enrolled")
        else:
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

@app.route('/student/results')
def student_results():
    if not check_auth('student'):
        return redirect(url_for('login'))

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT 
            c.course_code,
            c.course_name,
            r.marks_obtained,
            r.full_marks,
            r.grade,
            r.gpa,
            r.exam_type
        FROM student_results r
        JOIN courses c ON r.course_id = c.course_id
        WHERE r.student_id = %s
        ORDER BY r.exam_type, c.course_name
    """, (session['user_id'],))

    results = cur.fetchall()
    conn.close()

    return render_template('student_results.html', results=results)

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
        WHERE br.student_id = %s
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
