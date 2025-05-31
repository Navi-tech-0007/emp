from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app
from flask_login import login_required, current_user
import datetime
from util import create_notification
import mysql.connector

schedule_bp = Blueprint('schedule', __name__)

def get_schedules_for_users_and_dates(user_ids, week_dates):
    if not user_ids:
        return []
    conn = mysql.connector.connect(
        host=current_app.config['DB_HOST'],
        user=current_app.config['DB_USER'],
        password=current_app.config['DB_PASSWORD'],
        database=current_app.config['DB_NAME']
    )
    cursor = conn.cursor(dictionary=True)
    query = f"""
        SELECT * FROM schedule
        WHERE employee_id IN ({','.join(['%s'] * len(user_ids))})
        AND DATE(start_datetime) IN ({','.join(['%s'] * len(week_dates))})
    """
    cursor.execute(query, user_ids + week_dates)
    results = cursor.fetchall()
    cursor.close()
    conn.close()
    return results

@schedule_bp.route('/configure_schedule')
@login_required
def configure_schedule():
    conn = mysql.connector.connect(
        host=current_app.config['DB_HOST'],
        user=current_app.config['DB_USER'],
        password=current_app.config['DB_PASSWORD'],
        database=current_app.config['DB_NAME']
    )
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT name FROM departments ORDER BY name")
    departments = [row['name'] for row in cursor.fetchall()]
    selected_department = request.args.get('department', '')
    week_offset = int(request.args.get('week_offset', 0))
    users = []
    if selected_department:
        cursor.execute("SELECT * FROM users WHERE department=%s", (selected_department,))
        users = cursor.fetchall()
        for user in users:
            assert user.get('employee_id'), f"User missing employee_id: {user}"
    today = datetime.datetime.utcnow().date()
    start_of_week = today - datetime.timedelta(days=today.weekday()) + datetime.timedelta(weeks=week_offset)
    week_days = [(start_of_week + datetime.timedelta(days=i)).strftime('%a %d %b') for i in range(7)]
    week_dates = [(start_of_week + datetime.timedelta(days=i)).strftime('%Y-%m-%d') for i in range(7)]
    week_day_date = list(zip(week_days, week_dates))
    week_range = f"{week_days[0]} - {week_days[-1]}"
    user_ids = [str(user['employee_id']) for user in users]
    schedule_map = {}
    schedules = get_schedules_for_users_and_dates(user_ids, week_dates)
    for sched in schedules:
        date_str = str(sched['start_datetime'])[:10]
        emp_id = str(sched['employee_id'])
        key = f"{emp_id}|{date_str}"
        schedule_map[key] = sched.get('shift_type', '')
        schedule_map[f"{emp_id}|{date_str}|start_time"] = str(sched.get('start_datetime'))[11:16]
        schedule_map[f"{emp_id}|{date_str}|end_time"] = str(sched.get('end_datetime'))[11:16]
        schedule_map[f"{emp_id}|{date_str}|description"] = sched.get('description', '')
        schedule_map[f"{emp_id}|{date_str}|location"] = sched.get('location', '')
        schedule_map[f"{emp_id}|{date_str}|created_by"] = sched.get('created_by', '')
        schedule_map[f"{emp_id}|{date_str}|last_updated"] = sched.get('last_updated', '')
    # Fetch approved leave and add to schedule_map
    if user_ids:
        cursor.execute("""
            SELECT employee_id, start_date, end_date, leave_type
            FROM leave_request
            WHERE employee_id IN ({})
              AND status='Approved'
              AND (
                (start_date BETWEEN %s AND %s)
                OR (end_date BETWEEN %s AND %s)
                OR (start_date <= %s AND end_date >= %s)
              )
        """.format(','.join(['%s'] * len(user_ids))),
        user_ids + [week_dates[0], week_dates[-1], week_dates[0], week_dates[-1], week_dates[0], week_dates[-1]])
        leave_rows = cursor.fetchall()
        for leave in leave_rows:
            current = leave['start_date']
            while current <= leave['end_date']:
                key = f"{leave['employee_id']}|{current}"
                schedule_map[key] = 'Leave'
                schedule_map[f"{leave['employee_id']}|{current}|leave_type"] = leave['leave_type']
                current += datetime.timedelta(days=1)
    cursor.execute("SELECT employee_id FROM users")
    all_users = cursor.fetchall()
    cursor.close()
    conn.close()
    mobile_date = request.args.get('mobile_date')
    return render_template(
        'management_hub/configure_schedule.html',
        departments=departments,
        selected_department=selected_department,
        users=users,
        week_days=week_days,
        week_dates=week_dates,
        week_range=week_range,
        week_offset=week_offset,
        schedule_map=schedule_map,
        all_users=all_users,
        now=datetime.datetime.utcnow(),
        week_day_date=week_day_date,
        mobile_date=mobile_date,
    )

@schedule_bp.route('/update_schedule', methods=['POST'])
@login_required
def update_schedule():
    employee_id = request.form['employee_id']
    date = request.form['date']
    start_time = request.form['start_time']
    end_time = request.form['end_time']
    shift_type = request.form['shift_type']
    description = request.form.get('description', '')
    location = request.form.get('location', '')
    created_by = current_user.username
    start_datetime = f"{date} {start_time}:00"
    end_datetime = f"{date} {end_time}:00"
    conn = mysql.connector.connect(
        host=current_app.config['DB_HOST'],
        user=current_app.config['DB_USER'],
        password=current_app.config['DB_PASSWORD'],
        database=current_app.config['DB_NAME']
    )
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM users WHERE employee_id=%s", (employee_id,))
    if not cursor.fetchone():
        cursor.close()
        conn.close()
        flash("Invalid employee ID — user not found.", "danger")
        return redirect(url_for('schedule.configure_schedule',
            department=request.form.get('department', request.args.get('department', '')),
            week_offset=request.form.get('week_offset', request.args.get('week_offset', 0))
        ))
    cursor.execute("""
        INSERT INTO schedule (employee_id, start_datetime, end_datetime, shift_type, description, location, created_by, last_updated)
        VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
        ON DUPLICATE KEY UPDATE
            start_datetime=VALUES(start_datetime),
            end_datetime=VALUES(end_datetime),
            shift_type=VALUES(shift_type),
            description=VALUES(description),
            location=VALUES(location),
            created_by=VALUES(created_by)
    """, (employee_id, start_datetime, end_datetime, shift_type, description, location, created_by))
    conn.commit()
    # Get username for the employee_id
    conn2 = mysql.connector.connect(
        host=current_app.config['DB_HOST'],
        user=current_app.config['DB_USER'],
        password=current_app.config['DB_PASSWORD'],
        database=current_app.config['DB_NAME']
    )
    cursor2 = conn2.cursor(dictionary=True)
    cursor2.execute("SELECT username FROM users WHERE employee_id=%s", (employee_id,))
    user_row = cursor2.fetchone()
    cursor2.close()
    conn2.close()
    if user_row:
        create_notification(user_row['username'], "Your schedule was updated.", url="/my_schedule")
    cursor.close()
    conn.close()
    flash("Schedule updated.", "success")
    return redirect(url_for('schedule.configure_schedule',
        department=request.form.get('department', request.args.get('department', '')),
        week_offset=request.form.get('week_offset', request.args.get('week_offset', 0))
    ))

@schedule_bp.route('/edit_schedule', methods=['POST'])
@login_required
def edit_schedule():
    employee_id = request.form['employee_id']
    date = request.form['date']
    shift_type = request.form['shift_type']
    start_time = request.form['start_time']
    end_time = request.form['end_time']
    description = request.form['description']
    location = request.form['location']
    department = request.form['department']
    week_offset = request.form['week_offset']
    created_by = current_user.username
    conn = mysql.connector.connect(
        host=current_app.config['DB_HOST'],
        user=current_app.config['DB_USER'],
        password=current_app.config['DB_PASSWORD'],
        database=current_app.config['DB_NAME']
    )
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id FROM schedule WHERE employee_id=%s AND DATE(start_datetime)=%s",
        (employee_id, date)
    )
    existing = cursor.fetchone()
    if existing:
        cursor.execute("""
            UPDATE schedule
            SET shift_type=%s, start_datetime=%s, end_datetime=%s, description=%s, location=%s, created_by=%s, last_updated=NOW()
            WHERE id=%s
        """, (shift_type, f"{date} {start_time}", f"{date} {end_time}", description, location, created_by, existing[0]))
    else:
        cursor.execute("""
            INSERT INTO schedule (employee_id, start_datetime, end_datetime, shift_type, description, location, created_by, status, created_at, last_updated)
            VALUES (%s, %s, %s, %s, %s, %s, %s, 'active', NOW(), NOW())
        """, (employee_id, f"{date} {start_time}", f"{date} {end_time}", shift_type, description, location, created_by))
    conn.commit()
    # Notify user about shift edit
    conn2 = mysql.connector.connect(
        host=current_app.config['DB_HOST'],
        user=current_app.config['DB_USER'],
        password=current_app.config['DB_PASSWORD'],
        database=current_app.config['DB_NAME']
    )
    cursor2 = conn2.cursor(dictionary=True)
    cursor2.execute("SELECT username FROM users WHERE employee_id=%s", (employee_id,))
    user_row = cursor2.fetchone()
    cursor2.close()
    conn2.close()
    if user_row:
        create_notification(user_row['username'], "Your shift was edited.", url="/my_schedule")
    flash("Schedule updated.", "success")
    return redirect(url_for('schedule.configure_schedule', department=department, week_offset=week_offset))

@schedule_bp.route('/delete_schedule', methods=['POST'])
@login_required
def delete_schedule():
    employee_id = request.form['employee_id']
    date = request.form['date']
    conn = mysql.connector.connect(
        host=current_app.config['DB_HOST'],
        user=current_app.config['DB_USER'],
        password=current_app.config['DB_PASSWORD'],
        database=current_app.config['DB_NAME']
    )
    cursor = conn.cursor()
    cursor.execute(
        "DELETE FROM schedule WHERE employee_id=%s AND DATE(start_datetime)=%s",
        (employee_id, date)
    )
    conn.commit()
    # Notify user about shift deletion
    conn2 = mysql.connector.connect(
        host=current_app.config['DB_HOST'],
        user=current_app.config['DB_USER'],
        password=current_app.config['DB_PASSWORD'],
        database=current_app.config['DB_NAME']
    )
    cursor2 = conn2.cursor(dictionary=True)
    cursor2.execute("SELECT username FROM users WHERE employee_id=%s", (employee_id,))
    user_row = cursor2.fetchone()
    cursor2.close()
    conn2.close()
    if user_row:
        create_notification(user_row['username'], "Your shift was deleted.", url="/my_schedule")
    flash("Schedule deleted.", "success")
    return redirect(url_for('schedule.configure_schedule',
        department=request.form.get('department', ''),
        week_offset=request.form.get('week_offset', 0)
    ))

@schedule_bp.route('/schedule')
def schedule():
    return redirect(url_for('schedule.configure_schedule'))

@schedule_bp.route('/my_schedule')
@login_required
def my_schedule():
    username = current_user.username
    week_start_str = request.args.get('week_start')
    nav = request.args.get('nav')

    # Always use date objects for week_start
    if week_start_str:
        week_start = datetime.datetime.strptime(week_start_str, "%Y-%m-%d").date()
    else:
        today = datetime.date.today()
        week_start = today - datetime.timedelta(days=today.weekday())

    # Handle navigation
    if nav == "prev":
        week_start = week_start - datetime.timedelta(days=7)
    elif nav == "next":
        week_start = week_start + datetime.timedelta(days=7)

    week_days = []
    for i in range(7):
        d = week_start + datetime.timedelta(days=i)
        week_days.append((d.strftime('%A'), d.strftime('%Y-%m-%d')))

    conn = mysql.connector.connect(
        host=current_app.config['DB_HOST'],
        user=current_app.config['DB_USER'],
        password=current_app.config['DB_PASSWORD'],
        database=current_app.config['DB_NAME']
    )
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT employee_id FROM users WHERE username=%s", (username,))
    user_row = cursor.fetchone()
    if not user_row:
        flash("User not found.", "danger")
        return redirect(url_for('auth.logout'))
    employee_id = user_row['employee_id']
    cursor.execute("""
        SELECT *, DATE(start_datetime) as date_only, TIME(start_datetime) as start_time, TIME(end_datetime) as end_time
        FROM schedule
        WHERE employee_id=%s
          AND DATE(start_datetime) BETWEEN %s AND %s
    """, (employee_id, week_days[0][1], week_days[-1][1]))
    rows = cursor.fetchall()
    cursor.execute("""
        SELECT start_date, end_date, leave_type
        FROM leave_request
        WHERE employee_id=%s
          AND status='Approved'
          AND (
            (start_date BETWEEN %s AND %s)
            OR (end_date BETWEEN %s AND %s)
            OR (start_date <= %s AND end_date >= %s)
          )
    """, (employee_id, week_days[0][1], week_days[-1][1], week_days[0][1], week_days[-1][1], week_days[0][1], week_days[-1][1]))
    leave_rows = cursor.fetchall()
    
    leave_dates = {}
    for leave in leave_rows:
        start = leave['start_date']
        end = leave['end_date']
        current = start
        while current <= end:
            leave_dates[str(current)] = leave['leave_type']
            current += datetime.timedelta(days=1)
    week_schedule = {}
    for day in week_days:
        date_str = str(day[1])
        if date_str in leave_dates:
            week_schedule[date_str] = {'leave_type': leave_dates[date_str]}
        else:
            row = next((r for r in rows if str(r['date_only']) == date_str), None)
            if row:
                week_schedule[date_str] = row
            else:
                week_schedule[date_str] = None
    total_hours = 0.0
    for row in rows:
        start = row['start_time']
        end = row['end_time']
        if isinstance(start, datetime.timedelta):
            start = (datetime.datetime.min + start).time()
        elif isinstance(start, str):
            start = datetime.datetime.strptime(start, "%H:%M:%S").time()
        if isinstance(end, datetime.timedelta):
            end = (datetime.datetime.min + end).time()
        elif isinstance(end, str):
            end = datetime.datetime.strptime(end, "%H:%M:%S").time()
        start_dt = datetime.datetime.combine(datetime.date.today(), start)
        end_dt = datetime.datetime.combine(datetime.date.today(), end)
        diff = (end_dt - start_dt).total_seconds() / 3600.0
        if diff > 0:
            total_hours += diff
    user_id = getattr(current_user, "id", None)
    # Example: count all shifts for this user
    cursor.execute(
        "SELECT COUNT(*) FROM schedule WHERE employee_id=%s AND DATE(start_datetime) BETWEEN %s AND %s",
        (employee_id, week_days[0][1], week_days[-1][1])
    )
    total_shifts = cursor.fetchone()['COUNT(*)']
    cursor.close()
    conn.close()
    
    return render_template(
        'management_hub/schedule.html',
        week_schedule=week_schedule,
        week_days=week_days,
        total_hours=total_hours,
        total_shifts=total_shifts,
        now=datetime.date.today(),  # Pass today's date
    )