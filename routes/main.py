from flask import Blueprint, render_template, redirect, url_for, flash, session, request, jsonify, Response, current_app
from flask_login import login_required, current_user
from util import get_user_by_username, get_manager_by_department, get_avatar_url, get_next_employee_id, REQUESTABLE_LEAVE_TYPES
import datetime
import mysql.connector

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
def home():
    return render_template('main.html')

@main_bp.route('/dashboard')
def dashboard():
    username = session.get('user')
    if not username:
        flash("You must be logged in to view the dashboard.", "danger")
        return redirect(url_for('auth.login'))
    user = get_user_by_username(username)
    department = user.get('department') if user else None
    manager = None
    if department:
        manager = get_manager_by_department(department)
    if not manager:
        manager = {
            'name': 'No Manager Assigned',
            'role': '',
            'email': '',
            'photo_url': url_for('static', filename='default_avatar.png')
        }
    # --- Fetch leave balances ---
    balances = []
    if user and user.get('employee_id'):
        conn = mysql.connector.connect(
            host=current_app.config['DB_HOST'],
            user=current_app.config['DB_USER'],
            password=current_app.config['DB_PASSWORD'],
            database=current_app.config['DB_NAME']
        )
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT leave_type, balance FROM leave_balances WHERE employee_id=%s", (user['employee_id'],))
        balances = cursor.fetchall()
        cursor.close()
        conn.close()
    recent_leaves = []
    if user and user.get('employee_id'):
        conn = mysql.connector.connect(
            host=current_app.config['DB_HOST'],
            user=current_app.config['DB_USER'],
            password=current_app.config['DB_PASSWORD'],
            database=current_app.config['DB_NAME']
        )
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT leave_type, start_date, end_date, status, requested_at
            FROM leave_request
            WHERE employee_id=%s
            ORDER BY requested_at DESC
            LIMIT 5
        """, (user['employee_id'],))
        recent_leaves = cursor.fetchall()
        cursor.close()
        conn.close()
    return render_template(
        'dashboard.html',
        user=current_user,
        avatar_url=get_avatar_url(user),
        manager=manager,
        balances=balances,
        requestable_types=REQUESTABLE_LEAVE_TYPES,
        recent_leaves=recent_leaves
    )

@main_bp.route('/about')
def about():
    return "About page coming soon!"

@main_bp.route('/contact')
def contact():
    return "Contact page coming soon!"

@main_bp.route("/directory")
@login_required
def directory():
    conn = mysql.connector.connect(
        host=current_app.config['DB_HOST'],
        user=current_app.config['DB_USER'],
        password=current_app.config['DB_PASSWORD'],
        database=current_app.config['DB_NAME']
    )
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM users")
    users = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('view-edit.html', users=users, user=current_user)

@main_bp.route('/profile/<username>')
def profile(username):
    user = get_user_by_username(username)
    if not user:
        return "User not found", 404
    return render_template('profile.html',emp=user, avatar_url=get_avatar_url(user), user=current_user)

@main_bp.route('/edit_profile', methods=['POST', 'GET'])
def edit_profile():
    username = session.get('user')
    if not username:
        return redirect(url_for('auth.login'))
    user = get_user_by_username(username)
    if request.method == 'POST':
        # --- Update user details ---
        updated_data = {
            'full_name': request.form.get('full_name'),
            'email': request.form.get('email'),
            'department': request.form.get('department'),
            'role': request.form.get('role'),
            'username': username
        }
        conn = mysql.connector.connect(
            host=current_app.config['DB_HOST'],
            user=current_app.config['DB_USER'],
            password=current_app.config['DB_PASSWORD'],
            database=current_app.config['DB_NAME']
        )
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE users
            SET full_name=%s, email=%s, department=%s, role=%s
            WHERE username=%s
        """, (updated_data['full_name'], updated_data['email'], updated_data['department'], updated_data['role'], updated_data['username']))
        conn.commit()
        cursor.close()
        conn.close()
        flash("Profile updated successfully!", "success")
        return redirect(url_for('main.profile', username=username))
    # Fetch departments from DB for the dropdown
    conn = mysql.connector.connect(
        host=current_app.config['DB_HOST'],
        user=current_app.config['DB_USER'],
        password=current_app.config['DB_PASSWORD'],
        database=current_app.config['DB_NAME']
    )
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM departments ORDER BY name")
    departments = [row[0] for row in cursor.fetchall()]
    cursor.close()
    conn.close()
    return render_template('edit_profile.html', user=user, departments=departments)