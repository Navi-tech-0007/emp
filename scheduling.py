import pymysql
import mysql.connector
from flask import current_app
import boto3

def get_db():
    return pymysql.connect(
        host=current_app.config['DB_HOST'],
        user=current_app.config['DB_USER'],
        password=current_app.config['DB_PASSWORD'],
        db=current_app.config['DB_NAME'],
        cursorclass=pymysql.cursors.DictCursor
    )

def validate_employee_in_dynamodb(employee_id):
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table('Users')
    response = table.scan(
        FilterExpression='employee_id = :eid',
        ExpressionAttributeValues={':eid': employee_id}
    )
    return bool(response.get('Items'))

def add_schedule(employee_id, start_datetime, end_datetime, shift_type, description, location, created_by):
    # Validate employee before adding schedule
    if not validate_employee_in_dynamodb(employee_id):
        raise ValueError(f"Invalid employee_id: {employee_id}")

    db = get_db()
    with db.cursor() as cursor:
        sql = """INSERT INTO schedule (employee_id, start_datetime, end_datetime, shift_type, description, location, created_by)
                 VALUES (%s, %s, %s, %s, %s, %s, %s)"""
        cursor.execute(sql, (employee_id, start_datetime, end_datetime, shift_type, description, location, created_by))
        db.commit()
    db.close()

def get_schedules(employee_id):
    db = get_db()
    with db.cursor() as cursor:
        sql = "SELECT * FROM schedule WHERE employee_id=%s"
        cursor.execute(sql, (employee_id,))
        result = cursor.fetchall()
    db.close()
    return result

def add_leave_request(employee_id, start_date, end_date, leave_type, reason):
    db = get_db()
    with db.cursor() as cursor:
        sql = """INSERT INTO leave_request (employee_id, start_date, end_date, leave_type, reason)
                 VALUES (%s, %s, %s, %s, %s)"""
        cursor.execute(sql, (employee_id, start_date, end_date, leave_type, reason))
        db.commit()
    db.close()

def get_leave_requests(employee_id):
    db = get_db()
    with db.cursor() as cursor:
        sql = "SELECT * FROM leave_request WHERE employee_id=%s"
        cursor.execute(sql, (employee_id,))
        result = cursor.fetchall()
    db.close()
    return result

def get_schedules_for_users_and_dates(user_ids, dates):
    if not user_ids or not dates:
        return []
    conn = mysql.connector.connect(
        host=current_app.config['DB_HOST'],
        user=current_app.config['DB_USER'],
        password=current_app.config['DB_PASSWORD'],
        database=current_app.config['DB_NAME']
    )
    cursor = conn.cursor(dictionary=True)
    format_strings_users = ','.join(['%s'] * len(user_ids))
    format_strings_dates = ','.join(['%s'] * len(dates))
    query = f"""
        SELECT employee_id, start_datetime, end_datetime, shift_type, description, location, created_by, last_updated
        FROM schedule
        WHERE employee_id IN ({format_strings_users})
          AND DATE(start_datetime) IN ({format_strings_dates})
    """
    cursor.execute(query, tuple(user_ids) + tuple(dates))
    results = cursor.fetchall()
    cursor.close()
    conn.close()
    return results
