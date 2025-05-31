from flask import Blueprint, render_template, redirect, url_for, flash, session, request, jsonify, current_app
from flask_login import login_required, current_user
import mysql.connector
import datetime
from datetime import datetime, timedelta

leave_bp = Blueprint('leave', __name__)

@leave_bp.route('/leave', methods=['GET'])
@login_required
def leave():
    user = session.get('user')
    conn = mysql.connector.connect(
        host=current_app.config['DB_HOST'],
        user=current_app.config['DB_USER'],
        password=current_app.config['DB_PASSWORD'],
        database=current_app.config['DB_NAME']
    )
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT employee_id FROM users WHERE username=%s", (user,))
    user_row = cursor.fetchone()
    employee_id = user_row['employee_id'] if user_row else None
    cursor.execute("SELECT leave_type, balance FROM leave_balances WHERE employee_id = %s", (employee_id,))
    balances = cursor.fetchall()
    cursor.execute(
        "SELECT * FROM leave_request WHERE employee_id = %s ORDER BY requested_at DESC",
        (employee_id,)
    )
    leaves = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template(
        'management_hub/leave.html',
        balances=balances,
        requestable_types=['Vacation', 'Sick', 'Personal'],
        leaves=leaves,
        user=current_user,
        avatar_url=getattr(current_user, "avatar_url", None),
    )

@leave_bp.route('/manage_leave')
@login_required
def manage_leave():
    if current_user.role.lower() not in ['manager', 'hr']:
        flash("Access denied: Only HR and Manager roles can access this page.", "danger")
        return redirect(url_for('main.home'))
    conn = mysql.connector.connect(
        host=current_app.config['DB_HOST'],
        user=current_app.config['DB_USER'],
        password=current_app.config['DB_PASSWORD'],
        database=current_app.config['DB_NAME']
    )
    cursor = conn.cursor(dictionary=True)

    # --- Add this block ---
    cursor.execute("SELECT name FROM departments ORDER BY name")
    departments = [row['name'] for row in cursor.fetchall()]
    # ----------------------

    # Get manager's department(s)
    manager_departments = []
    if current_user.role.lower() == 'manager':
        cursor.execute("SELECT department FROM users WHERE id = %s", (current_user.id,))
        row = cursor.fetchone()
        if row and row['department']:
            manager_departments = [row['department']]
    # HR or admin can see all
    elif current_user.role.lower() in ['hr', 'admin']:
        cursor.execute("SELECT name FROM departments")
        manager_departments = [row['name'] for row in cursor.fetchall()]

    # Filter pending requests by department
    if manager_departments:
        format_strings = ','.join(['%s'] * len(manager_departments))
        cursor.execute(f"""
            SELECT lr.*, u.name AS employee_name, u.employee_id, u.department
            FROM leave_request lr
            LEFT JOIN users u ON lr.employee_id = u.employee_id
            WHERE lr.status = 'Pending' AND u.department IN ({format_strings})
            ORDER BY lr.requested_at DESC
        """, tuple(manager_departments))
    else:
        # Fallback: show none
        pending_requests = []
    pending_requests = cursor.fetchall()

    selected_department = request.args.get('department', '')
    leave_requests = []
    if selected_department:
        filters = ["u.department = %s"]
        params = [selected_department]
        if request.args.get('status'):
            filters.append("lr.status = %s")
            params.append(request.args['status'])
        if request.args.get('employee'):
            filters.append("(u.name LIKE %s OR u.employee_id LIKE %s)")
            params.append(f"%{request.args['employee']}%")
            params.append(f"%{request.args['employee']}%")
        filter_sql = " AND ".join(filters)
        if filter_sql:
            filter_sql = "WHERE " + filter_sql
        cursor.execute(f"""
            SELECT lr.*, u.name AS employee_name, u.employee_id, u.department
            FROM leave_request lr
            LEFT JOIN users u ON lr.employee_id = u.employee_id
            {filter_sql}
            ORDER BY lr.requested_at DESC
        """, params)
        leave_requests = cursor.fetchall()
    # --- Add this to fetch all pending requests for the modal ---
    cursor.execute("""
        SELECT lr.*, u.name AS employee_name, u.employee_id, u.department
        FROM leave_request lr
        LEFT JOIN users u ON lr.employee_id = u.employee_id
        WHERE lr.status = 'Pending'
        ORDER BY lr.requested_at DESC
    """)
    pending_requests = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template(
        'management_hub/manage_leave.html',
        leave_requests=leave_requests,
        departments=departments,
        selected_department=selected_department,
        user=current_user,
        flask_request=request,
        pending_requests=pending_requests
    )

@leave_bp.route('/approve_leave/<int:request_id>')
def approve_leave(request_id):
    conn = mysql.connector.connect(
        host=current_app.config['DB_HOST'],
        user=current_app.config['DB_USER'],
        password=current_app.config['DB_PASSWORD'],
        database=current_app.config['DB_NAME']
    )
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE leave_request SET status='Approved', reviewed_by=%s, reviewed_at=NOW() WHERE id=%s",
        (session.get('user'), request_id)
    )
    conn.commit()
    cursor.close()
    conn.close()
    approve_leave_request(request_id)
    flash('Leave request approved.', 'success')
    return redirect(url_for('leave.manage_leave'))

@leave_bp.route('/reject_leave/<int:request_id>')
def reject_leave(request_id):
    restore_leave_balance(request_id)
    conn = mysql.connector.connect(
        host=current_app.config['DB_HOST'],
        user=current_app.config['DB_USER'],
        password=current_app.config['DB_PASSWORD'],
        database=current_app.config['DB_NAME']
    )
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE leave_request SET status='Rejected', reviewed_by=%s, reviewed_at=NOW() WHERE id=%s",
        (session.get('user'), request_id)
    )
    conn.commit()
    cursor.close()
    conn.close()
    flash('Leave request rejected.', 'info')
    return redirect(url_for('leave.manage_leave'))

def approve_leave_request(request_id):
    conn = mysql.connector.connect(
        host=current_app.config['DB_HOST'],
        user=current_app.config['DB_USER'],
        password=current_app.config['DB_PASSWORD'],
        database=current_app.config['DB_NAME']
    )
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM leave_request WHERE id=%s", (request_id,))
    leave = cursor.fetchone()
    if not leave:
        cursor.close()
        conn.close()
        return False  # Indicate failure
    leave_type = leave['leave_type']
    employee_id = leave['employee_id']
    start = leave['start_date']
    end = leave['end_date']
    hours_requested = ((end - start).days + 1) * 8
    cursor.execute("""
        UPDATE leave_balances
        SET balance = balance - %s
        WHERE employee_id = %s AND leave_type = %s
    """, (hours_requested, employee_id, leave_type))
    conn.commit()
    cursor.close()
    conn.close()
    return True  # Indicate success

def restore_leave_balance(request_id):
    conn = mysql.connector.connect(
        host=current_app.config['DB_HOST'],
        user=current_app.config['DB_USER'],
        password=current_app.config['DB_PASSWORD'],
        database=current_app.config['DB_NAME']
    )
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM leave_request WHERE id=%s", (request_id,))
    leave = cursor.fetchone()
    if not leave:
        cursor.close()
        conn.close()
        return False
    leave_type = leave['leave_type']
    employee_id = leave['employee_id']
    start = leave['start_date']
    end = leave['end_date']
    hours_requested = ((end - start).days + 1) * 8
    cursor.execute("""
        UPDATE leave_balances
        SET balance = balance + %s
        WHERE employee_id = %s AND leave_type = %s
    """, (hours_requested, employee_id, leave_type))
    conn.commit()
    cursor.close()
    conn.close()
    return True

@leave_bp.route('/update_leave_status/<int:request_id>', methods=['POST'])
@login_required
def update_leave_status(request_id):
    new_status = request.form.get('status')
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    if new_status not in ['Pending', 'Approved', 'Rejected', 'Cancelled']:
        if is_ajax:
            return jsonify(success=False, message='Invalid status.'), 400
        flash('Invalid status.', 'danger')
        return redirect(url_for('leave.manage_leave'))

    # Update status in DB
    conn = mysql.connector.connect(
        host=current_app.config['DB_HOST'],
        user=current_app.config['DB_USER'],
        password=current_app.config['DB_PASSWORD'],
        database=current_app.config['DB_NAME']
    )
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE leave_request SET status=%s, reviewed_by=%s, reviewed_at=NOW() WHERE id=%s",
        (new_status, session.get('user'), request_id)
    )
    conn.commit()
    cursor.close()
    conn.close()

    # Update leave balances if needed
    if new_status == 'Approved':
        if not approve_leave_request(request_id):
            if is_ajax:
                return jsonify(success=False, message='Leave request not found.'), 404
            flash('Leave request not found.', 'danger')
            return redirect(url_for('leave.manage_leave'))
    elif new_status in ['Rejected', 'Cancelled']:
        if not restore_leave_balance(request_id):
            if is_ajax:
                return jsonify(success=False, message='Leave request not found.'), 404
            flash('Leave request not found.', 'danger')
            return redirect(url_for('leave.manage_leave'))

    if is_ajax:
        return jsonify(success=True, new_status=new_status)
    else:
        flash(f'Leave request status changed to {new_status}.', 'success')
        department = request.form.get('department', '')
        status = request.form.get('status_filter', '')
        employee = request.form.get('employee', '')
        return redirect(url_for('leave.manage_leave',
                                department=department,
                                status=status,
                                employee=employee))

@leave_bp.route('/cancel_leave/<int:leave_id>', methods=['POST'])
@login_required
def cancel_leave(leave_id):
    restore_leave_balance(leave_id)
    conn = mysql.connector.connect(
        host=current_app.config['DB_HOST'],
        user=current_app.config['DB_USER'],
        password=current_app.config['DB_PASSWORD'],
        database=current_app.config['DB_NAME']
    )
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE leave_request SET status='Cancelled', cancelled_by=%s WHERE id=%s AND (status='Pending' OR status='Approved')",
        (current_user.username, leave_id)
    )
    conn.commit()
    cursor.close()
    conn.close()
    flash('Leave request cancelled.', 'info')
    return redirect(url_for('leave.leave'))

@leave_bp.route('/leave', methods=['POST'])
@login_required
def submit_leave():
    user = session.get('user')
    employee_id = session.get('employee_id')
    leave_type = request.form.get('leave_type')
    start_date = request.form.get('start_date')
    end_date = request.form.get('end_date')
    reason = request.form.get('reason')

    # Validation: All fields required
    if not (leave_type and start_date and end_date):
        flash("All fields are required.", "danger")
        return redirect(url_for('leave.leave'))

    # Parse dates
    try:
        start_dt = datetime.strptime(start_date, "%Y-%m-%d").date()
        end_dt = datetime.strptime(end_date, "%Y-%m-%d").date()
        today = datetime.utcnow().date()
    except Exception:
        flash("Invalid date format.", "danger")
        return redirect(url_for('leave.leave'))

    # Rule 1: No leave for past days
    if start_dt < today:
        flash("You cannot request leave for past dates.", "danger")
        return redirect(url_for('leave.leave'))

    # Rule 2: Must request at least 5 days before start date
    if (start_dt - today).days < 5:
        flash("Leave requests must be submitted at least 5 days before the leave start date.", "danger")
        return redirect(url_for('leave.leave'))

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
    flash("Leave request submitted!", "success")
    return redirect(url_for('leave.leave'))

def get_pending_leave_requests():
    conn = mysql.connector.connect(
        host=current_app.config['DB_HOST'],
        user=current_app.config['DB_USER'],
        password=current_app.config['DB_PASSWORD'],
        database=current_app.config['DB_NAME']
    )
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT lr.*, u.name AS employee_name, u.department
        FROM leave_request lr
        LEFT JOIN users u ON lr.employee_id = u.employee_id
        WHERE lr.status = 'Pending'
        ORDER BY lr.requested_at DESC
    """)
    requests = cursor.fetchall()
    cursor.close()
    conn.close()
    return requests

@leave_bp.route('/management_hub')
@login_required
def management_hub():
    conn = mysql.connector.connect(
        host=current_app.config['DB_HOST'],
        user=current_app.config['DB_USER'],
        password=current_app.config['DB_PASSWORD'],
        database=current_app.config['DB_NAME']
    )
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM leave_request WHERE status = 'Pending'")
    pending_leave_count = cursor.fetchone()[0]
    cursor.close()
    conn.close()
    return render_template(
        'management_hub/management_hub.html',
        user=current_user,
        pending_leave_count=pending_leave_count
    )

@leave_bp.route('/leave/pending')
def pending_leave_requests():
    # Fetch only pending leave requests from your database
    pending_requests = get_pending_leave_requests()  # Replace with your actual data fetching logic
    return render_template('leave/pending_requests.html', requests=pending_requests)
