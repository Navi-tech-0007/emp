from datetime import datetime
import mysql.connector

@app.route('/dashboard')
@login_required
def dashboard():
    user_role = session.get('role', 'user')

    # Fetch all distinct role from users table
    conn = mysql.connector.connect(
        host=current_app.config['DB_HOST'],
        user=current_app.config['DB_USER'],
        password=current_app.config['DB_PASSWORD'],
        database=current_app.config['DB_NAME']
    )
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT role FROM users WHERE role IS NOT NULL AND role != ''")
    role = [row[0] for row in cursor.fetchall()]
    cursor.close()
    conn.close()

    # Normalize user_role and role to lowercase for matching
    user_role_lower = user_role.lower()
    role_lower = [r.lower() for r in role]

    announcements = [
        {
            "title": "Welcome to the Portal!",
            "message": "Check out the new features and resources available to all users.",
            "date": datetime(2025, 5, 28),
            "roles": role  # All roles from DB
        },
        {
            "title": "HR Policy Update",
            "message": "Please review the updated leave policy in the HR section.",
            "date": datetime(2025, 5, 27),
            "roles": ["HR", "Admin"]
        },
        {
            "title": "Manager Meeting",
            "message": "Monthly managers' sync is scheduled for Friday at 10am.",
            "date": datetime(2025, 5, 29),
            "roles": ["Manager", "Admin"]
        }
    ]

    filtered_announcements = [
        ann for ann in announcements
        if not ann.get("roles") or user_role_lower in [r.lower() for r in ann["roles"]]
    ]

    todo_tasks = {
        "User": [
            "Update your profile information.",
            "Submit your leave request for next month.",
            "Review your recent payslips."
        ],
        "Admin": [
            "Approve pending user registrations.",
            "Review system logs.",
            "Send monthly newsletter."
        ],
        "HR": [
            "Review new leave requests.",
            "Update employee records.",
            "Schedule onboarding for new hires."
        ],
        "Manager": [
            "Approve team leave requests.",
            "Review team performance reports.",
            "Schedule 1:1 meetings with team members."
        ]
    }
    # Use title-case for matching todo_tasks
    tasks = todo_tasks.get(user_role.title(), [])

    return render_template(
        "dashboard.html",
        announcements=filtered_announcements,
        tasks=tasks,
        user_role=user_role,
        role=role
    )