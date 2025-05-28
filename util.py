"""Shared utility helper functions"""
import os
from io import BytesIO
from PIL import Image
import mysql.connector

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
    from flask import current_app
    conn = mysql.connector.connect(
        host=current_app.config['DB_HOST'],
        user=current_app.config['DB_USER'],
        password=current_app.config['DB_PASSWORD'],
        database=current_app.config['DB_NAME']
    )
    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        "SELECT * FROM users WHERE department=%s AND role IN ('manager') LIMIT 1",
        (department,)
    )
    manager = cursor.fetchone()
    cursor.close()
    conn.close()
    return manager

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
    conn = mysql.connector.connect(
        host=current_app.config['DB_HOST'],
        user=current_app.config['DB_USER'],
        password=current_app.config['DB_PASSWORD'],
        database=current_app.config['DB_NAME']
    )
    cursor = conn.cursor()
    cursor.execute("SELECT MAX(employee_id) FROM users")
    max_id = cursor.fetchone()[0]
    cursor.close()
    conn.close()
    if max_id is None:
        return 1001
    try:
        return int(max_id) + 1
    except Exception:
        return 1001

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

class User:
    def __init__(self, user_dict):
        self.id = user_dict.get('username')
        self.username = user_dict.get('username')
        self.role = user_dict.get('role')
        self.employee_id = user_dict.get('employee_id')
        self.is_active = user_dict.get('active', True)
        self.name = user_dict.get('name')
    def get_id(self):
        return self.id
    def is_authenticated(self):
        return True
    def is_active(self):
        return self.is_active
    def is_anonymous(self):
        return False
