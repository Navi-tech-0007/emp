from flask import Blueprint, jsonify, request, session, current_app

from werkzeug.security import generate_password_hash
from flask_login import login_required, current_user
import mysql.connector

api_bp = Blueprint('api', __name__)

@api_bp.route('/api/user/<username>', methods=['GET', 'PUT'])
@login_required
def api_user(username):
    # Only allow HR, admin, or manager to edit
    if request.method == 'PUT' and session.get('role') not in ['admin', 'hr', 'manager', 'root']:
        return jsonify({'success': False, 'error': 'Permission denied'}), 403

    conn = mysql.connector.connect(
        host=current_app.config['DB_HOST'],
        user=current_app.config['DB_USER'],
        password=current_app.config['DB_PASSWORD'],
        database=current_app.config['DB_NAME']
    )
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM users WHERE username=%s", (username,))
    user = cursor.fetchone()
    if request.method == 'GET':
        if not user:
            return jsonify({'success': False, 'error': 'User not found.'}), 404
        return jsonify({'success': True, 'user': user})

    if request.method == 'PUT':
        data = request.get_json()
        fields = ['name', 'username', 'role', 'department', 'number', 'active', 'hrcode', 'hire_date']
        update_values = [data.get(f) for f in fields]
        update_values.append(username)
        cursor.execute("""
            UPDATE users
            SET name=%s, username=%s, role=%s, department=%s, number=%s, active=%s, hrcode=%s, hire_date=%s
            WHERE username=%s
        """, update_values)
        conn.commit()
        cursor.close()
        conn.close()
        return jsonify({'success': True})

    cursor.close()
    conn.close()
    return jsonify({'success': False, 'error': 'Invalid request method.'}), 405

@api_bp.route('/api/user/<username>/reset_password', methods=['POST'])
@login_required
def api_reset_password(username):
    data = request.get_json()
    new_password = data.get('new_password')
    if not new_password or len(new_password) < 6:
        return jsonify({'success': False, 'error': 'Password too short.'}), 400
    hashed = generate_password_hash(new_password)
    conn = mysql.connector.connect(
        host=current_app.config['DB_HOST'],
        user=current_app.config['DB_USER'],
        password=current_app.config['DB_PASSWORD'],
        database=current_app.config['DB_NAME']
    )
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET password=%s WHERE username=%s", (hashed, username))
    conn.commit()
    cursor.close()
    conn.close()
    return jsonify({'success': True})

@api_bp.route('/api/leave', methods=['POST'])
@login_required
def api_leave():
    data = request.get_json()
    employee_id = session.get('employee_id')
    leave_type = data.get('leave_type')
    start_date = data.get('start_date')
    end_date = data.get('end_date')
    reason = data.get('reason')

    if not (leave_type and start_date and end_date):
        return jsonify({'success': False, 'error': 'Missing fields'}), 400

    conn = mysql.connector.connect(
        host=current_app.config['DB_HOST'],
        user=current_app.config['DB_USER'],
        password=current_app.config['DB_PASSWORD'],
        database=current_app.config['DB_NAME']
    )
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO leave_request (employee_id, leave_type, start_date, end_date, reason, status, requested_at)
        VALUES (%s, %s, %s, %s, %s, %s, NOW())
    """, (employee_id, leave_type, start_date, end_date, reason, 'Pending'))
    conn.commit()
    cursor.close()
    conn.close()
    return jsonify({'success': True})