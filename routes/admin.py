from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session, current_app, Response
from werkzeug.security import generate_password_hash
from flask_login import login_required, current_user
import mysql.connector

admin_bp = Blueprint('admin', __name__)

@admin_bp.route('/admin/users')
def view_users():
    conn = mysql.connector.connect(
        host=current_app.config['DB_HOST'],
        user=current_app.config['DB_USER'],
        password=current_app.config['DB_PASSWORD'],
        database=current_app.config['DB_NAME']
    )
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT DISTINCT department FROM users WHERE department IS NOT NULL AND department != ''")
    departments = [row['department'] for row in cursor.fetchall()]
    cursor.execute("SELECT DISTINCT role FROM users WHERE role IS NOT NULL AND role != ''")
    roles = [row['role'] for row in cursor.fetchall()]
    cursor.execute("SELECT * FROM users")
    users = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template(
        'users.html',
        users=users,
        departments=departments,
        roles=roles,
        user=current_user
    )

@admin_bp.route('/admin/reset_password', methods=['POST'])
def reset_password():
    email = request.form['email']
    new_password = request.form['new_password']
    conn = mysql.connector.connect(
        host=current_app.config['DB_HOST'],
        user=current_app.config['DB_USER'],
        password=current_app.config['DB_PASSWORD'],
        database=current_app.config['DB_NAME']
    )
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT salt FROM users WHERE username=%s", (email,))
    user = cursor.fetchone()
    if not user:
        flash('User not found.')
        return redirect(url_for('admin.view_users'))
    hashed_password = generate_password_hash(new_password, method='pbkdf2:sha256')
    cursor.execute("UPDATE users SET password=%s WHERE username=%s", (hashed_password, email))
    conn.commit()
    cursor.close()
    conn.close()
    flash('Password reset.')
    return redirect(url_for('admin.view_users'))

@admin_bp.route('/admin/deactivate_user', methods=['POST'])
def deactivate_user():
    email = request.form['email']
    conn = mysql.connector.connect(
        host=current_app.config['DB_HOST'],
        user=current_app.config['DB_USER'],
        password=current_app.config['DB_PASSWORD'],
        database=current_app.config['DB_NAME']
    )
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET active=FALSE WHERE username=%s", (email,))
    conn.commit()
    cursor.close()
    conn.close()
    flash('User deactivated.')
    return redirect(url_for('admin.view_users'))

@admin_bp.route('/admin/activate_user', methods=['POST'])
def activate_user():
    email = request.form['email']
    conn = mysql.connector.connect(
        host=current_app.config['DB_HOST'],
        user=current_app.config['DB_USER'],
        password=current_app.config['DB_PASSWORD'],
        database=current_app.config['DB_NAME']
    )
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET active=TRUE WHERE username=%s", (email,))
    conn.commit()
    cursor.close()
    conn.close()
    flash('User activated.')
    return redirect(url_for('admin.view_users'))

@admin_bp.route('/bulk_user_action', methods=['POST'])
def bulk_user_action():
    data = request.get_json()
    action = data.get('action')
    users = data.get('users', [])
    conn = mysql.connector.connect(
        host=current_app.config['DB_HOST'],
        user=current_app.config['DB_USER'],
        password=current_app.config['DB_PASSWORD'],
        database=current_app.config['DB_NAME']
    )
    cursor = conn.cursor()
    for username in users:
        cursor.execute("UPDATE users SET active=%s WHERE username=%s", (True if action == 'activate' else False, username))
    conn.commit()
    cursor.close()
    conn.close()
    return jsonify({'status': 'success'})

@admin_bp.route('/export_directory')
def export_directory():
    import csv
    from io import StringIO
    conn = mysql.connector.connect(
        host=current_app.config['DB_HOST'],
        user=current_app.config['DB_USER'],
        password=current_app.config['DB_PASSWORD'],
        database=current_app.config['DB_NAME']
    )
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT name, username, role, department, active FROM users")
    employees = cursor.fetchall()
    cursor.close()
    conn.close()

    headers = ['name', 'username', 'role', 'department', 'active']
    si = StringIO()
    cw = csv.writer(si)
    cw.writerow(headers)
    for emp in employees:
        row = [emp.get(h, '') for h in headers]
        cw.writerow(row)
    output = si.getvalue()
    return Response(
        output,
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment;filename=directory.csv"}
    )