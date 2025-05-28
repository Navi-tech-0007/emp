import boto3
import hashlib
import os
import binascii

def hash_password(password, salt=None):
    if salt is None:
        salt = os.urandom(16)
    elif isinstance(salt, str):
        salt = binascii.unhexlify(salt)
    pwd_hash = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 100000)
    return binascii.hexlify(pwd_hash).decode('utf-8'), binascii.hexlify(salt).decode('utf-8')

def add_user(
    email,
    password,
    salt,
    name=None,
    hrcode=None,
    role="user",
    object_key=None,
    department=None,
    employee_id=None,
    hire_date=None,
    number=None,
    active=True
):
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table('Users')
    item = {
        'username': email,
        'password': password,
        'salt': salt,
        'name': name if name is not None else None,
        'hrcode': hrcode if hrcode is not None else None,
        'role': role if role is not None else None,
        'active': active,
        'object_key': object_key if object_key is not None else None,
        'department': department if department is not None else None,
        'employee_id': employee_id if employee_id is not None else None,
        'hire_date': hire_date if hire_date is not None else None,
        'number': number if number is not None else None
    }
    if object_key:
        item['object_key'] = object_key
    table.put_item(Item=item)

def get_user(username):
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table('Users')
    resp = table.get_item(Key={'username': username})
    return resp.get('Item')