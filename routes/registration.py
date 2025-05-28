from flask import Blueprint, render_template, request, jsonify, session, redirect, url_for, flash, current_app
from werkzeug.security import generate_password_hash
from util import check_hr_code, get_next_employee_id
import datetime
import secrets
from flask_login import login_required, current_user
import mysql.connector

registration_bp = Blueprint('registration', __name__)

@registration_bp.route('/register', methods=['GET'])
def register_form():
    return render_template('register.html')

@registration_bp.route('/register', methods=['POST'])
def register():
    data = request.json
    name = data.get('name')
    email = data.get('email')
    password = data.get('password')
    hrcode = data.get('hrcode')

    hr_code_item = check_hr_code(hrcode)
    if not hr_code_item:
        return jsonify({'success': False, 'error': 'Invalid HR code.'})

    if hr_code_item.get('email', '').lower() != email.lower():
        return jsonify({'success': False, 'error': 'This HR code is not valid for this email address.'})

    role = hr_code_item.get('role', 'user')
    department = hr_code_item.get('department', '')



    employee_id = get_next_employee_id()
    hire_date = datetime.datetime.utcnow().strftime('%Y-%m-%d')

    conn = mysql.connector.connect(
        host=current_app.config['DB_HOST'],
        user=current_app.config['DB_USER'],
        password=current_app.config['DB_PASSWORD'],
        database=current_app.config['DB_NAME']
    )
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT 1 FROM users WHERE username=%s", (email,))
    if cursor.fetchone():
        cursor.close()
        conn.close()
        return jsonify({'success': False, 'error': 'Email already registered.'})

    hashed_password = generate_password_hash(password)
    cursor.execute("""
        INSERT INTO users (username, password, name, role, department, employee_id, hire_date)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
    """, (email, hashed_password, name, role, department, employee_id, hire_date))
    conn.commit()
    cursor.close()
    conn.close()

    session['user'] = email
    session['role'] = role

    return jsonify({'success': True})

@registration_bp.route('/check_email', methods=['POST'])
def check_email():
    data = request.get_json()
    email = data.get('email', '').strip()
    if not email:
        return jsonify({'exists': False, 'message': 'Email cannot be empty.'}), 400
    conn = mysql.connector.connect(
        host=current_app.config['DB_HOST'],
        user=current_app.config['DB_USER'],
        password=current_app.config['DB_PASSWORD'],
        database=current_app.config['DB_NAME']
    )
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT 1 FROM users WHERE username=%s", (email,))
    exists = cursor.fetchone() is not None
    cursor.close()
    conn.close()
    return jsonify({'exists': exists})

@registration_bp.route('/hr/generate_hr_code', methods=['GET', 'POST'])
def generate_hr_code():
    if request.method == 'GET':
        ensure_default_departments()
        conn = mysql.connector.connect(
            host=current_app.config['DB_HOST'],
            user=current_app.config['DB_USER'],
            password=current_app.config['DB_PASSWORD'],
            database=current_app.config['DB_NAME']
        )
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT name FROM departments ORDER BY name")
        departments = [row['name'] for row in cursor.fetchall()]
        cursor.close()
        conn.close()
        return render_template('add-employee.html', departments=departments, user=current_user)
    data = request.get_json()
    email = data.get('email')
    role = data.get('role', 'user')
    department = data.get('department')
    if not email:
        return jsonify({'success': False, 'error': 'Email is required'})
    if not department or not department.strip():
        return jsonify({'success': False, 'error': 'Department is required.'})
    code = secrets.token_hex(4)
    conn = mysql.connector.connect(
        host=current_app.config['DB_HOST'],
        user=current_app.config['DB_USER'],
        password=current_app.config['DB_PASSWORD'],
        database=current_app.config['DB_NAME']
    )
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO hrcodes (code, email, role, department) VALUES (%s, %s, %s, %s)",
        (code, email, role, department)
    )
    
    # Before inserting HR code
    cursor.execute("SELECT id FROM departments WHERE name=%s", (department,))
    dept_row = cursor.fetchone()
    if not dept_row:
        cursor.execute("INSERT INTO departments (name) VALUES (%s)", (department,))
        conn.commit()

    conn.commit()
    cursor.close()
    conn.close()
    return jsonify({'success': True, 'code': code})

@registration_bp.route('/hr/hr_codes')
def view_hr_codes():
    conn = mysql.connector.connect(
        host=current_app.config['DB_HOST'],
        user=current_app.config['DB_USER'],
        password=current_app.config['DB_PASSWORD'],
        database=current_app.config['DB_NAME']
    )
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM hrcodes ORDER BY department ASC, email ASC")
    codes = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('hr_codes.html', codes=codes, user=current_user)

@registration_bp.route('/hr/revoke_hr_code', methods=['POST'])
def revoke_hr_code():
    code = request.form['code']
    conn = mysql.connector.connect(
        host=current_app.config['DB_HOST'],
        user=current_app.config['DB_USER'],
        password=current_app.config['DB_PASSWORD'],
        database=current_app.config['DB_NAME']
    )
    cursor = conn.cursor()
    cursor.execute("DELETE FROM hrcodes WHERE code=%s", (code,))
    conn.commit()
    cursor.close()
    conn.close()
    flash('HR code revoked.')
    return redirect(url_for('registration.view_hr_codes'))

@registration_bp.route('/hr/regenerate_hr_code', methods=['POST'])
def regenerate_hr_code():
    code_value = request.form.get('code')
    email = request.form.get('email')
    role = request.form.get('role')
    department = request.form.get('department')

    conn = mysql.connector.connect(
        host=current_app.config['DB_HOST'],
        user=current_app.config['DB_USER'],
        password=current_app.config['DB_PASSWORD'],
        database=current_app.config['DB_NAME']
    )
    cursor = conn.cursor()
    cursor.execute("DELETE FROM hrcodes WHERE code=%s", (code_value,))

    if department:
        conn = mysql.connector.connect(
            host=current_app.config['DB_HOST'],
            user=current_app.config['DB_USER'],
            password=current_app.config['DB_PASSWORD'],
            database=current_app.config['DB_NAME']
        )
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM departments WHERE name=%s", (department,))
        if not cursor.fetchone():
            cursor.close()
            conn.close()
            return jsonify({'success': False, 'error': 'Invalid department selected.'})
        cursor.close()
        conn.close()
        new_code = secrets.token_hex(4)
        cursor.execute(
            "INSERT INTO hrcodes (code, email, role, department) VALUES (%s, %s, %s, %s)",
            (new_code, email, role, department)
        )
        conn.commit()
    cursor.close()
    conn.close()
    return redirect(url_for('registration.view_hr_codes'))

def ensure_default_departments():
    default_departments = ["HR", "Administration", "Food", "Overnight"]
    conn = mysql.connector.connect(
        host=current_app.config['DB_HOST'],
        user=current_app.config['DB_USER'],
        password=current_app.config['DB_PASSWORD'],
        database=current_app.config['DB_NAME']
    )
    cursor = conn.cursor()
    for dept in default_departments:
        cursor.execute("SELECT id FROM departments WHERE name=%s", (dept,))
        if not cursor.fetchone():
            cursor.execute("INSERT INTO departments (name) VALUES (%s)", (dept,))
    conn.commit()
    cursor.close()
    conn.close()