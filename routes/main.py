from flask import Blueprint, render_template, redirect, url_for, flash, session, current_app, request, jsonify
from flask_login import login_required, current_user
from util import get_user_by_username, get_manager_by_department, get_avatar_url, REQUESTABLE_LEAVE_TYPES, get_filtered_users, create_notification
from whoosh.index import open_dir
from whoosh.qparser import MultifieldParser
from datetime import datetime
import mysql.connector

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
def home():
    return render_template('main.html')

@main_bp.route('/dashboard')
@login_required
def dashboard():
    username = current_user.username
    user_role = current_user.role
    user = get_user_by_username(username)
    if not user:
        flash("Access denied: Your session could not be verified. Please log in again or contact IT support for assistance.", "danger")
        return redirect(url_for('auth.login'))
    
    # Get manager details.
    department = user.get('department') if user else None
    manager = get_manager_by_department(department) if department else None
    if not manager:
        manager = {
            'name': 'No Manager Assigned',
            'role': '',
            'email': '',
            'photo_url': url_for('static', filename='default_avatar.png')
        }
    
    # --- Fetch Announcements from the Database ---
    try:
        conn = mysql.connector.connect(
            host=current_app.config['DB_HOST'],
            user=current_app.config['DB_USER'],
            password=current_app.config['DB_PASSWORD'],
            database=current_app.config['DB_NAME']
        )
        cursor = conn.cursor(dictionary=True)
        # Retrieve all announcements with formatted date.
        cursor.execute("""
            SELECT id, title, message, DATE_FORMAT(date, '%b %d, %Y') AS date, roles, department, start_date, end_date
            FROM announcements
            ORDER BY date DESC
        """)
        announcements = cursor.fetchall()
        cursor.close()
        conn.close()
    except Exception as e:
        announcements = []  # Fallback to empty list if error occurs.
        print("Error fetching announcements: ", e)
    
    now = datetime.now()
    user_department = user.get('department', '').lower() if user else ''

    filtered_announcements = []
    for ann in announcements:
        # Role filter (as before)
        roles_str = ann.get("roles", "").strip().lower()
        if not roles_str or roles_str == "all":
            role_ok = True
        else:
            allowed_roles = [r.strip() for r in roles_str.split(',') if r.strip()]
            user_role = current_user.role  # or however you get the user's role
            role_ok = user_role in allowed_roles

        # Department filter
        dept = (ann.get("department") or "all").lower()
        dept_ok = (dept == "all") or (dept == user_department)

        # Date window filter
        start = ann.get("start_date")
        end = ann.get("end_date")
        date_ok = True
        if start and now < start:
            date_ok = False
        if end and now > end:
            date_ok = False

        if role_ok and dept_ok and date_ok:
            filtered_announcements.append(ann)
    announcements = filtered_announcements
    
    # --- Fetch leave balances ---
    balances = []
    if user and user.get('employee_id'):
        try:
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
        except Exception as e:
            print("Error fetching leave balances: ", e)
    
    # --- Fetch recent leave requests ---
    recent_leaves = []
    if user and user.get('employee_id'):
        try:
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
        except Exception as e:
            print("Error fetching recent leave requests: ", e)
    
    return render_template(
        'dashboard.html',
        avatar_url=get_avatar_url(user),
        manager=manager,
        balances=balances,
        requestable_types=REQUESTABLE_LEAVE_TYPES,
        recent_leaves=recent_leaves,
        announcements=announcements
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
    employees = get_filtered_users()
    # Fetch unique departments for filter dropdown.
    departments = [row['department'] for row in employees if row.get('department')]
    departments = sorted(list(set(departments)))
    return render_template('view-edit.html', employees=employees, departments=departments, )

@main_bp.route('/profile/<username>')
def profile(username):
    user = get_user_by_username(username)
    if not user:
        return "User not found", 404
    return render_template('profile.html', emp=user, avatar_url=get_avatar_url(user), )

@main_bp.route('/edit_profile', methods=['POST', 'GET'])
def edit_profile():
    user = current_user.username
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
        try:
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
            # Notify user
            create_notification(username, "Your profile was updated.", url="/profile/{}".format(username))
        except Exception as e:
            flash("Error updating profile: " + str(e), "danger")
        return redirect(url_for('main.profile', username=username))
    
    # Fetch departments from DB for the dropdown.
    try:
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
    except Exception as e:
        departments = []
        print("Error fetching departments: ", e)

    return render_template('edit_profile.html', departments=departments)

@main_bp.route('/api/search')
def api_search():
    q = request.args.get('q', '')
    ix = open_dir("whoosh_index")
    results = []
    if q:
        with ix.searcher() as searcher:
            parser = MultifieldParser(["label", "desc"], schema=ix.schema)
            # Add wildcards before and after for substring matching
            query_str = f"*{q}*"
            query = parser.parse(query_str)
            hits = searcher.search(query, limit=5)
            hits.fragmenter.charlimit = None
            for hit in hits:
                label = hit.highlights("label", top=1, text=hit["label"]) or hit["label"]
                desc = hit.highlights("desc", top=1, text=hit["desc"]) or hit["desc"]
                results.append({
                    "label": label,
                    "url": hit["url"],
                    "desc": desc
                })
    return jsonify(results)

# Add this helper function (or put in util.py)
def get_unread_notifications(username, limit=5):
    conn = mysql.connector.connect(
        host=current_app.config['DB_HOST'],
        user=current_app.config['DB_USER'],
        password=current_app.config['DB_PASSWORD'],
        database=current_app.config['DB_NAME']
    )
    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        "SELECT * FROM notifications WHERE user_username=%s AND is_read=0 ORDER BY created_at DESC LIMIT %s",
        (username, limit)
    )
    notifications = cursor.fetchall()
    cursor.execute(
        "SELECT COUNT(*) as unread_count FROM notifications WHERE user_username=%s AND is_read=0",
        (username,)
    )
    unread_count = cursor.fetchone()['unread_count']
    cursor.close()
    conn.close()
    return notifications, unread_count

@main_bp.route('/orgchart')
@login_required
def org_chart():
    # Fetch the full user record
    user = get_user_by_username(current_user.username)
    if not user or not user.get('department'):
        return "User or department not found", 404

    department = user['department']

    conn = mysql.connector.connect(
        host=current_app.config['DB_HOST'],
        user=current_app.config['DB_USER'],
        password=current_app.config['DB_PASSWORD'],
        database=current_app.config['DB_NAME']
    )
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT username, name, role, department, avatar_url FROM users WHERE department=%s ORDER BY name", (department,))
    dept_users = cursor.fetchall()
    cursor.close()
    conn.close()

    # Find manager
    manager = next((u for u in dept_users if u['role'].lower() == 'manager'), None)

    # Find all managers in department
    dept_managers = [u for u in dept_users if u['role'].lower() == 'manager']

    # Find colleagues (excluding self and manager)
    colleagues = [u for u in dept_users if u['username'] != current_user.username and u['role'].lower() != 'manager']

    # Find left and right colleague (for demo: just pick first two)
    left_colleague = colleagues[0] if len(colleagues) > 0 else None
    right_colleague = colleagues[1] if len(colleagues) > 1 else None

    return render_template(
        'orgchart.html',
        manager=manager,
        left_colleague=left_colleague,
        right_colleague=right_colleague,
        dept_managers=dept_managers
    )

