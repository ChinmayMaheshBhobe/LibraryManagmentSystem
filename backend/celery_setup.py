from celery import Celery
from celery.schedules import crontab


celery = Celery(__name__)

celery.conf.update(
    broker_url='redis://localhost:6379/1',  # Redis broker URL
    result_backend='redis://localhost:6379/2',  # Redis result backend
    timezone='Asia/Kolkata',
    broker_connection_retry_on_startup=True,
    beat_schedule={
        'send_daily_reminder': {
            'task': 'user_tasks.send_daily_reminder',
            'schedule': crontab(hour=20, minute=49)
        },
        'send_daily_report': {
            'task': 'user_tasks.send_daily_report',
            'schedule': crontab(hour=17, minute=14)
        },
        'send_monthly_report': {
            'task': 'user_tasks.send_monthly_report',
            'schedule': crontab(day_of_month=5, hour=22, minute=10)
        }
    }
)
