"""Shared utility helper functions"""
import os
from io import BytesIO
from PIL import Image
import mysql.connector
from flask_login import UserMixin

EXIF_ORIENTATION = 274  # Magic numbers from http://www.exiv2.org/tags.html

def random_hex_bytes(n_bytes):
    """Create a hex encoded string of random bytes"""
    return os.urandom(n_bytes).hex()

def resize_image(file_p, size):
    """Resize an image to fit within the size, and save to the path directory"""
    dest_ratio = size[0] / float(size[1])
    try:
        image = Image.open(file_p)
    except IOError:
        print("Error: Unable to open image")
        return None

    try:
        exif = dict(image._getexif().items())
        if exif[EXIF_ORIENTATION] == 3:
            image = image.rotate(180, expand=True)
        elif exif[EXIF_ORIENTATION] == 6:
            image = image.rotate(270, expand=True)
        elif exif[EXIF_ORIENTATION] == 8:
            image = image.rotate(90, expand=True)
    except:
        print("No exif data")

    source_ratio = image.size[0] / float(image.size[1])

    # the image is smaller than the destination on both axis
    # don't scale it
    if image.size < size:
        new_width, new_height = image.size
    elif dest_ratio > source_ratio:
        new_width = int(image.size[0] * size[1]/float(image.size[1]))
        new_height = size[1]
    else:
        new_width = size[0]
        new_height = int(image.size[1] * size[0]/float(image.size[0]))
    image = image.resize((new_width, new_height), resample=Image.LANCZOS)

    final_image = Image.new("RGBA", size)
    topleft = (int((size[0]-new_width) / float(2)),
               int((size[1]-new_height) / float(2)))
    final_image.paste(image, topleft)
    bytes_stream = BytesIO()
    final_image.save(bytes_stream, 'PNG')
    return bytes_stream.getvalue()

def get_user_by_username(username):
    from flask import current_app
    conn = mysql.connector.connect(
        host=current_app.config['DB_HOST'],
        user=current_app.config['DB_USER'],
        password=current_app.config['DB_PASSWORD'],
        database=current_app.config['DB_NAME']
    )
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM users WHERE username=%s", (username,))
    user = cursor.fetchone()
    cursor.close()
    conn.close()
    return user

def get_manager_by_department(department):
    import mysql.connector
    from flask import current_app
    conn = mysql.connector.connect(
        host=current_app.config['DB_HOST'],
        user=current_app.config['DB_USER'],
        password=current_app.config['DB_PASSWORD'],
        database=current_app.config['DB_NAME']
    )
    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        "SELECT username FROM users WHERE department=%s AND role='manager'",
        (department,)
    )
    managers = [row['username'] for row in cursor.fetchall()]
    cursor.close()
    conn.close()
    return managers

def get_avatar_url(user):
    # Example: return a default avatar if no photo_url is set
    if not user:
        return '/static/default_avatar.png'
    photo_url = user.get('photo_url')
    if photo_url:
        return photo_url
    return '/static/default_avatar.png'

def get_next_employee_id():
    from flask import current_app
    import mysql.connector

    conn = mysql.connector.connect(
        host=current_app.config['DB_HOST'],
        user=current_app.config['DB_USER'],
        password=current_app.config['DB_PASSWORD'],
        database=current_app.config['DB_NAME']
    )
    cursor = conn.cursor()
    cursor.execute("""
        SELECT MAX(CAST(SUBSTRING(employee_id, 4) AS UNSIGNED))
        FROM users
        WHERE employee_id LIKE 'EMP%';
    """)
    max_id = cursor.fetchone()[0]
    cursor.close()
    conn.close()

    next_id_num = (max_id or 0) + 1
    return f"EMP{str(next_id_num).zfill(4)}"


def check_hr_code(hrcode):
    from flask import current_app
    conn = mysql.connector.connect(
        host=current_app.config['DB_HOST'],
        user=current_app.config['DB_USER'],
        password=current_app.config['DB_PASSWORD'],
        database=current_app.config['DB_NAME']
    )
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM hrcodes WHERE code=%s", (hrcode,))
    hr_code_item = cursor.fetchone()
    cursor.close()
    conn.close()
    return hr_code_item

DEPARTMENTS = ["HR", "Food", "Overnight"]  # Example
REQUESTABLE_LEAVE_TYPES = ["Vacation", "Sick", "Personal"]  # Example

class User(UserMixin):
    def __init__(self, user_dict):
        self.username = user_dict['username']
        self.name = user_dict.get('name')
        self.email = user_dict.get('email')
        self.role = user_dict.get('role')
        self.employee_id = user_dict.get('employee_id')
        # ... any other fields

    def get_id(self):
        return self.username  # or whatever uniquely identifies the user

def get_filtered_users(department=None, role=None, search=None):
    """Fetch users filtered by department, role, and search (name/email)."""
    from flask import current_app
    conn = mysql.connector.connect(
        host=current_app.config['DB_HOST'],
        user=current_app.config['DB_USER'],
        password=current_app.config['DB_PASSWORD'],
        database=current_app.config['DB_NAME']
    )
    cursor = conn.cursor(dictionary=True)
    query = "SELECT * FROM users WHERE 1=1"
    params = []
    if department:
        query += " AND department=%s"
        params.append(department)
    if role:
        query += " AND role=%s"
        params.append(role)
    if search:
        query += " AND (LOWER(name) LIKE %s OR LOWER(email) LIKE %s)"
        params.extend([f"%{search.lower()}%", f"%{search.lower()}%"])
    cursor.execute(query, tuple(params))
    users = cursor.fetchall()
    cursor.close()
    conn.close()
    return users

def create_notification(user_username, message, url=None):
    """Create a notification for a user."""
    from flask import current_app
    import mysql.connector

    conn = mysql.connector.connect(
        host=current_app.config['DB_HOST'],
        user=current_app.config['DB_USER'],
        password=current_app.config['DB_PASSWORD'],
        database=current_app.config['DB_NAME']
    )
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO notifications (user_username, message, url) VALUES (%s, %s, %s)",
        (user_username, message, url)
    )
    conn.commit()
    cursor.close()
    conn.close()
