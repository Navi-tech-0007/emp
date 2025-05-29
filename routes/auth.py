from flask import Blueprint, render_template, redirect, url_for, flash, session, request, current_app
from flask_login import login_user, logout_user
from werkzeug.security import check_password_hash, generate_password_hash
from forms import LoginForm
from util import get_user_by_username, User, get_user_by_username
import application

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        import mysql.connector
        conn = mysql.connector.connect(
            host=current_app.config['DB_HOST'],
            user=current_app.config['DB_USER'],
            password=current_app.config['DB_PASSWORD'],
            database=current_app.config['DB_NAME']
        )
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE username=%s", (form.username.data,))
        user = cursor.fetchone()
        cursor.close()
        conn.close()
        if user:
            if not user['password'].startswith('pbkdf2:sha256:'):
                session['reset_user'] = user['username']
                flash("Your password needs to be reset due to a system upgrade. Please set a new password.", "warning")
                return redirect(url_for('auth.force_password_reset'))
            if check_password_hash(user['password'], form.password.data):
                user_obj = User(user)
                login_user(user_obj)
                session.permanent = True
                session['user'] = user['username']
                session['role'] = user.get('role', 'user')
                session['employee_id'] = user['employee_id']
                if user['username'] == 'root@gt.com':
                    session['role'] = 'root'
                return redirect(url_for('main.dashboard'))
        flash("Invalid username or password.", "danger")
        return redirect(url_for('auth.login', email=form.username.data))

    # For GET requests or if form not submitted, just render the form
    email = request.args.get('email')
    return render_template('login_email.html', form=form, email=email)

@auth_bp.route('/force_password_reset', methods=['GET', 'POST'])
def force_password_reset():
    if 'reset_user' not in session:
        return redirect(url_for('auth.login'))
    if request.method == 'POST':
        new_password = request.form['new_password']
        import mysql.connector
        conn = mysql.connector.connect(
            host=current_app.config['DB_HOST'],
            user=current_app.config['DB_USER'],
            password=current_app.config['DB_PASSWORD'],
            database=current_app.config['DB_NAME']
        )
        cursor = conn.cursor(dictionary=True)
        hashed_password = generate_password_hash(new_password, method='pbkdf2:sha256')
        cursor.execute("UPDATE users SET password=%s WHERE username=%s", (hashed_password, session['reset_user']))
        conn.commit()
        cursor.execute("SELECT role FROM users WHERE username=%s", (session['reset_user'],))
        user = cursor.fetchone()
        cursor.close()
        conn.close()
        session['user'] = session['reset_user']
        session['role'] = user['role'] if user and 'role' in user else 'user'
        session.pop('reset_user', None)
        flash("Password reset successful. You are now logged in.", "success")
        return redirect(url_for('main.dashboard'))
    return render_template('force_password_reset.html')

@auth_bp.route('/logout')
def logout():
    session.pop('user', None)
    session.pop('role', None)
    return redirect(url_for('main.home'))