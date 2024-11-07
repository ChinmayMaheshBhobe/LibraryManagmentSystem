from sqlalchemy import extract
from app import app, db
from flask_mail import Message
from Db_Models import User, Request, Rating, Book, Type
from datetime import datetime, timedelta
import logging
from app import mail
from celery_setup import celery
from io import BytesIO
import calendar

# Configure logging
logging.basicConfig(level=logging.INFO)


@celery.task
def send_monthly_report():
    with app.app_context():
        # Retrieve all users from the database
        users = User.query.all()
        for user in users:
            user_name = user.username
            # Generate report data for the current user
            approved_report_data = generate_monthly_report_data(
                user, request_status=1)
            rejected_report_data = generate_monthly_report_data(
                user, request_status=-1)
            # Send the report email to the current user
            send_monthly_report_email(user.email, user_name,
                                      approved_report_data, rejected_report_data)


def generate_monthly_report_data(user, request_status):
    report_data = []
    # Calculate start and end dates for the current month
    today = datetime.today()
    start_date = today.replace(day=1)
    end_date = start_date + timedelta(days=32)  # Go to the next month

    # Query requests made by the user for the current month with the given request_status
    requests = Request.query.filter_by(user_id=user.id, request_status=request_status) \
        .filter(extract('year', Request.request_date) == start_date.year) \
        .filter(extract('month', Request.request_date) == start_date.month).all()

    for request in requests:
        # Convert request_date to string
        request_date_str = request.request_date.strftime("%Y-%m-%d")
        remaining_days = calculate_remaining_days(
            request_date_str, request.request_days)

        # Fetch rating for the book given by the user
        rating = Rating.query.filter_by(
            user_id=user.id, book_id=request.book_id).first()
        rating_value = rating.rating if rating else 'Not rated by you'

        report_data.append({
            'Book Name': request.book.title,
            'Request Days': request.request_days,
            'Due Date': (request.request_date + timedelta(days=request.request_days)).strftime("%Y-%m-%d"),
            'Request Type': request.request_type,
            'Rating': rating_value,
            'Remaining Days': remaining_days
        })
    return report_data


def send_monthly_report_email(user_email, user_name, approved_report_data, rejected_report_data):
    subject = f"Good morning, {user_name}! Your Monthly Report"
    # Create HTML content for the email body
    body = """
    <html>
    <head>
    <style>
    table {
      font-family: Arial, sans-serif;
      border-collapse: collapse;
      width: 100%;
    }

    th {
      background-color: #f2f2f2;
      border: 1px solid #dddddd;
      text-align: left;
      padding: 8px;
    }

    td {
      border: 1px solid #dddddd;
      text-align: left;
      padding: 8px;
    }
    </style>
    </head>
    <body>
    <h2>Your Monthly Report</h2>
    <h3>Books Acquired </h3>
    <table>
      <tr>
        <th>Book Name</th>
        <th>Request Days</th>
        <th>Due Date</th>
        <th>Request Type</th>
        <th>Rating</th>
        <th>Remaining Days</th>
      </tr>
    """
    body += generate_table_rows(approved_report_data)

    body += """
    </table>
    <h3>Books Returned or Rejected</h3>
    <table>
      <tr>
        <th>Book Name</th>
        <th>Request Days</th>
        <th>Due Date</th>
        <th>Request Type</th>
        <th>Rating</th>
        <th>Remaining Days</th>
      </tr>
    """
    body += generate_table_rows(rejected_report_data)

    body += """
    </table>
    <h4>Thank You</h4>
    <br/>
    <h4>Best Wishes From E-Library</h4>
    </body>
    </html>
    """
    # Create and send the email with HTML content
    msg = Message(subject, recipients=[user_email])
    msg.html = body
    mail.send(msg)


def generate_table_rows(report_data):
    rows = ""
    for data in report_data:
        rows += f"""
        <tr>
          <td>{data['Book Name']}</td>
          <td>{data['Request Days']}</td>
          <td>{data['Due Date']}</td>
          <td>{data['Request Type']}</td>
          <td>{data['Rating']}</td>
          <td>{data['Remaining Days']}</td>
        </tr>
        """
    return rows


# ---------------------------DAILY REPORT --------------------------------------


@celery.task
def send_daily_report():
    with app.app_context():
        # Retrieve all users from the database
        users = User.query.all()
        for user in users:
            user_name = user.username
            # Generate report data for the current user
            report_data = generate_report_data(user)
            # Send the report email to the current user
            send_daily_report_email(user.email, user_name, report_data)


def calculate_remaining_days(request_date, total_days):
    # Convert request date string to datetime object
    request_datetime = datetime.fromisoformat(request_date)
    current_time = datetime.utcnow()
    remaining_time = request_datetime + \
        timedelta(days=total_days) - current_time
    remaining_days = remaining_time.days
    return max(remaining_days, 0)


def generate_report_data(user):
    report_data = []
    requests = Request.query.filter_by(user_id=user.id, request_status=1).all()
    for request in requests:
        # Convert request_date to string
        request_date_str = request.request_date.strftime("%Y-%m-%d")
        remaining_days = calculate_remaining_days(
            request_date_str, request.request_days)

        # Fetch rating for the book given by the user
        rating = Rating.query.filter_by(
            user_id=user.id, book_id=request.book_id).first()
        rating_value = rating.rating if rating else 'Not rated by you'

        report_data.append({
            'Book Name': request.book.title,
            'Request Days': request.request_days,
            'Due Date': (request.request_date + timedelta(days=request.request_days)).strftime("%Y-%m-%d"),
            'Request Type': request.request_type,
            'Rating': rating_value,
            'Remaining Days': remaining_days
        })
    print("Report Data:", report_data)
    return report_data


def send_daily_report_email(user_email, user_name, report_data):
    if not report_data:
        return  # No report data found for the user, don't send email

    subject = f"Good morning, {user_name}! Your Daily Report"
    # Create HTML content for the email body
    body = """
    <html>
    <head>
    <style>
    table {
      font-family: Arial, sans-serif;
      border-collapse: collapse;
      width: 100%;
    }

    th {
      background-color: #f2f2f2;
      border: 1px solid #dddddd;
      text-align: left;
      padding: 8px;
    }

    td {
      border: 1px solid #dddddd;
      text-align: left;
      padding: 8px;
    }
    </style>
    </head>
    <body>
    <h2>Your Daily Report</h2>
    <table>
      <tr>
        <th>Book Name</th>
        <th>Request Days</th>
        <th>Due Date</th>
        <th>Request Type</th>
        <th>Rating</th>
        <th>Remaining Days</th>
      </tr>
    """
    for data in report_data:
        body += f"""
        <tr>
          <td>{data['Book Name']}</td>
          <td>{data['Request Days']}</td>
          <td>{data['Due Date']}</td>
          <td>{data['Request Type']}</td>
          <td>{data['Rating']}</td>
          <td>{data['Remaining Days']}</td>
        </tr>
        """
    body += """
    </table>
    <h4>Thank You</h4>
    <br/>
    <h4>Best Wishes From E-Library</h4>
    </body>
    </html>
    """
    # Create and send the email with HTML content
    msg = Message(subject, recipients=[user_email])
    msg.html = body
    mail.send(msg)


# ---------------------------SEND DAILY REMINDER -------------------------------------------------


@celery.task
def send_daily_reminder():
    with app.app_context():
        today = datetime.utcnow().date()
        users = User.query.all()

        logging.info("Executing send_daily_reminder task...")
        for user in users:
            # Log values of last_visited and today for debugging
            logging.info(
                f"User: {user.email}, Last Visited: {user.last_visited}, Today: {today}")

            if user.last_visited is None or user.last_visited.date() < today:
                logging.info(f"Sending reminder email to {user.email}...")
                send_reminder_email(user)
            else:
                logging.info(
                    f"Not sending reminder email to {user.email}: Already visited today")


def send_reminder_email(user):
    subject = "Daily Login Reminder"
    body = "You haven't logged in today. Don't forget to visit our website!"
    recipient = user.email

    msg = Message(subject, recipients=[recipient])
    msg.body = body

    try:
        mail.send(msg)
        logging.info(f"Reminder email sent successfully to {user.email}.")
    except Exception as e:
        logging.error(
            f"Failed to send reminder email to {user.email}: {str(e)}"
        )
