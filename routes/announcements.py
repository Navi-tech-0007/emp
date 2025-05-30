from flask import Blueprint, render_template, request, redirect, url_for, current_app
from flask_login import login_required, current_user
import mysql.connector
import datetime

announcements_bp = Blueprint('announcement', __name__, url_prefix='/announcement')

# Announcement Center - list all announcements
@announcements_bp.route('/center', methods=['GET', 'POST'])
@login_required
def center():
    if request.method == 'POST':
        title = request.form.get('title')
        message = request.form.get('message')
        department = request.form.get('department')
        start_date = request.form.get('start_date')
        end_date = request.form.get('end_date')
        selected_roles = request.form.getlist('roles')
        date = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        if not (title and message):
            # Stay on post section if validation fails
            return redirect(url_for('announcement.center', open='post'))
        else:
            try:
                conn = mysql.connector.connect(
                    host=current_app.config['DB_HOST'],
                    user=current_app.config['DB_USER'],
                    password=current_app.config['DB_PASSWORD'],
                    database=current_app.config['DB_NAME']
                )
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO announcements (title, message, date, roles, department, start_date, end_date)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (
                    title,
                    message,
                    date,
                    ','.join(selected_roles),
                    department,
                    start_date,
                    end_date
                ))
                conn.commit()
                cursor.close()
                conn.close()
                # Stay on post section after posting
                return redirect(url_for('announcement.center', open='post'))
            except Exception as e:
                # Stay on post section if error
                return redirect(url_for('announcement.center', open='post'))
    try:
        # --- Filtering logic for GET ---
        filter_department = request.args.get('filter_department')
        filter_role = request.args.get('filter_role')

        query = """
            SELECT id, title, message, DATE_FORMAT(date, '%%b %%d, %%Y') AS date, roles, department, start_date, end_date
            FROM announcements
            WHERE 1=1
        """
        params = []

        if filter_department:
            query += " AND department = %s"
            params.append(filter_department)
        if filter_role:
            query += " AND (roles = %s OR roles LIKE %s OR roles LIKE %s OR roles LIKE %s)"
            params.extend([
                filter_role,
                f"{filter_role},%",
                f"%,{filter_role},%",
                f"%,{filter_role}"
            ])

        query += " ORDER BY date DESC"

        conn = mysql.connector.connect(
            host=current_app.config['DB_HOST'],
            user=current_app.config['DB_USER'],
            password=current_app.config['DB_PASSWORD'],
            database=current_app.config['DB_NAME']
        )
        cursor = conn.cursor(dictionary=True)
        cursor.execute(query, params)
        announcements = cursor.fetchall()
        cursor.close()
        conn.close()
    except Exception as e:
        announcements = []
        # flash("Error fetching announcements: " + str(e), "danger")
    # Fetch departments for dropdown
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
        # flash("Error fetching departments: " + str(e), "danger")

    # Fetch roles from the database
    try:
        conn = mysql.connector.connect(
            host=current_app.config['DB_HOST'],
            user=current_app.config['DB_USER'],
            password=current_app.config['DB_PASSWORD'],
            database=current_app.config['DB_NAME']
        )
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT role FROM users WHERE role != 'root'")
        roles = [row[0] for row in cursor.fetchall()]
        cursor.close()
        conn.close()
    except Exception as e:
        roles = []
        # flash("Error fetching roles: " + str(e), "danger")

    return render_template(
        'management_hub/center.html',
        announcements=announcements,
        departments=departments,
        roles=roles,
        user=current_user
    )

# Optional: Delete Announcement
@announcements_bp.route('/delete/<int:announcement_id>', methods=['POST'])
@login_required
def delete_announcement(announcement_id):
    filter_department = request.form.get('filter_department', '')
    filter_role = request.form.get('filter_role', '')
    try:
        conn = mysql.connector.connect(
            host=current_app.config['DB_HOST'],
            user=current_app.config['DB_USER'],
            password=current_app.config['DB_PASSWORD'],
            database=current_app.config['DB_NAME']
        )
        cursor = conn.cursor()
        cursor.execute("DELETE FROM announcements WHERE id=%s", (announcement_id,))
        conn.commit()
        cursor.close()
        conn.close()
        # flash('Announcement deleted.', 'success')
    except Exception as e:
        # flash("Error deleting announcement: " + str(e), "danger")
        pass
    # Stay on review section after delete
    return redirect(url_for('announcement.center', open='review', filter_department=filter_department, filter_role=filter_role))

@announcements_bp.route('/edit', methods=['POST'])
@login_required
def edit_announcement():
    ann_id = request.form.get('id')
    title = request.form.get('title')
    message = request.form.get('message')
    department = request.form.get('department')
    roles = request.form.get('roles')
    start_date = request.form.get('start_date')
    end_date = request.form.get('end_date')
    try:
        conn = mysql.connector.connect(
            host=current_app.config['DB_HOST'],
            user=current_app.config['DB_USER'],
            password=current_app.config['DB_PASSWORD'],
            database=current_app.config['DB_NAME']
        )
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE announcements
            SET title=%s, message=%s, department=%s, roles=%s, start_date=%s, end_date=%s
            WHERE id=%s
        """, (title, message, department, roles, start_date, end_date, ann_id))
        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        pass
    return redirect(url_for('announcement.center', open='review'))