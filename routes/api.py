from flask import Blueprint, jsonify, request, session, current_app
from werkzeug.security import generate_password_hash
from flask_login import login_required, current_user
import mysql.connector
from util import create_notification

api_bp = Blueprint('api', __name__)

@api_bp.route('/api/user/<username>', methods=['GET', 'PUT'])
@login_required
def api_user(username):
    # Only allow HR, admin, or manager to edit
    if request.method == 'PUT' and (not hasattr(current_user, 'role') or current_user.role not in ['admin', 'hr', 'manager', 'root']):
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
        # Notify user
        if username != current_user.username:
            create_notification(username, "Your profile was updated by an admin.", url="/profile")
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
    # Notify user
    create_notification(username, "Your password was reset.", url="/profile")
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

    conn = mysql.connector.connect(
        host=current_app.config['DB_HOST'],
        user=current_app.config['DB_USER'],
        password=current_app.config['DB_PASSWORD'],
        database=current_app.config['DB_NAME']
    )
    cursor = conn.cursor()
    cursor.execute("SELECT employee_id FROM users WHERE username=%s", (current_user.username,))
    row = cursor.fetchone()
    employee_id = row[0] if row else None

    if not (leave_type and start_date and end_date):
        return jsonify({'success': False, 'error': 'Missing fields'}), 400

    cursor.execute("""
        INSERT INTO leave_request (employee_id, leave_type, start_date, end_date, reason, status, requested_at)
        VALUES (%s, %s, %s, %s, %s, %s, NOW())
    """, (employee_id, leave_type, start_date, end_date, reason, 'Pending'))
    conn.commit()
    cursor.close()
    conn.close()

    # Notify user
    create_notification(current_user.username, f"Your leave request for {leave_type} from {start_date} to {end_date} was submitted.", url="/leave")

    # Notify manager (example: get manager username from DB)
    manager_username = get_manager_username_for_user(current_user.username)
    if manager_username:
        create_notification(manager_username, f"{current_user.username} submitted a leave request.", url="/management_hub")

    return jsonify({'success': True})

@api_bp.route('/api/notifications', methods=['GET'])
@login_required
def get_notifications():
    conn = mysql.connector.connect(
        host=current_app.config['DB_HOST'],
        user=current_app.config['DB_USER'],
        password=current_app.config['DB_PASSWORD'],
        database=current_app.config['DB_NAME']
    )
    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        "SELECT * FROM notifications WHERE user_username=%s ORDER BY created_at DESC LIMIT 20",
        (current_user.username,)
    )
    notifications = cursor.fetchall()
    cursor.close()
    conn.close()
    return jsonify({'success': True, 'notifications': notifications})

@api_bp.route('/api/notifications/mark_read', methods=['POST'])
@login_required
def mark_notifications_read():
    ids = request.json.get('ids', [])
    if not ids:
        return jsonify({'success': False, 'error': 'No IDs provided'}), 400
    conn = mysql.connector.connect(
        host=current_app.config['DB_HOST'],
        user=current_app.config['DB_USER'],
        password=current_app.config['DB_PASSWORD'],
        database=current_app.config['DB_NAME']
    )
    cursor = conn.cursor()
    format_strings = ','.join(['%s'] * len(ids))
    cursor.execute(
        f"UPDATE notifications SET is_read=1 WHERE id IN ({format_strings}) AND user_username=%s",
        (*ids, current_user.username)
    )
    conn.commit()
    cursor.close()
    conn.close()
    return jsonify({'success': True})

@api_bp.route('/api/notifications/mark_all_read', methods=['POST'])
@login_required
def mark_all_notifications_read():
    conn = mysql.connector.connect(
        host=current_app.config['DB_HOST'],
        user=current_app.config['DB_USER'],
        password=current_app.config['DB_PASSWORD'],
        database=current_app.config['DB_NAME']
    )
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE notifications SET is_read=1 WHERE user_username=%s AND is_read=0",
        (current_user.username,)
    )
    conn.commit()
    cursor.close()
    conn.close()
    return jsonify({'success': True})

@api_bp.route('/api/notifications/<int:notif_id>/mark_read', methods=['POST'])
@login_required
def mark_single_notification_read(notif_id):
    conn = mysql.connector.connect(
        host=current_app.config['DB_HOST'],
        user=current_app.config['DB_USER'],
        password=current_app.config['DB_PASSWORD'],
        database=current_app.config['DB_NAME']
    )
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE notifications SET is_read=1 WHERE id=%s AND user_username=%s",
        (notif_id, current_user.username)
    )
    conn.commit()
    cursor.close()
    conn.close()
    return jsonify({'success': True})