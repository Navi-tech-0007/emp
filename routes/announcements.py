from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask_login import login_required, current_user
import mysql.connector

announcements_bp = Blueprint('announcement', __name__, url_prefix='/announcement')

# Announcement Center - list all announcements
@announcements_bp.route('/center', methods=['GET', 'POST'])
@login_required
def center():
    if request.method == 'POST':
        title = request.form.get('title')
        message = request.form.get('message')
        date = request.form.get('date')
        department = request.form.get('department')
        start_date = request.form.get('start_date')
        end_date = request.form.get('end_date')
        if not (title and message and date):
            flash('All fields are required.', 'danger')
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
                    ','.join(request.form.getlist('roles')),
                    department,
                    start_date,
                    end_date
                ))
                conn.commit()
                cursor.close()
                conn.close()
                flash('Announcement posted!', 'success')
                return redirect(url_for('announcement.center'))
            except Exception as e:
                flash("Error posting announcement: " + str(e), "danger")
    try:
        conn = mysql.connector.connect(
            host=current_app.config['DB_HOST'],
            user=current_app.config['DB_USER'],
            password=current_app.config['DB_PASSWORD'],
            database=current_app.config['DB_NAME']
        )
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT id, title, message, DATE_FORMAT(date, '%b %d, %Y') AS date, roles
            FROM announcements
            ORDER BY date DESC
        """)
        announcements = cursor.fetchall()
        cursor.close()
        conn.close()
    except Exception as e:
        announcements = []
        flash("Error fetching announcements: " + str(e), "danger")
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
        flash("Error fetching departments: " + str(e), "danger")

    roles = ['all', 'hr', 'admin', 'manager', 'employee']

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
        flash('Announcement deleted.', 'success')
    except Exception as e:
        flash("Error deleting announcement: " + str(e), "danger")
    return redirect(url_for('announcement.center'))