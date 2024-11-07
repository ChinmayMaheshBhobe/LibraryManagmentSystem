from app import celery


@celery.task
def send_admin_notification():
    # Implement logic to send admin notification
    pass


@celery.task
def generate_admin_report():
    # Implement logic to generate admin report
    pass
