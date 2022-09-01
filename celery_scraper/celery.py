from __future__ import absolute_import
from celery import Celery

# init celery
app = Celery('celery_scraper',
                broker='amqp://admin:mypass@rabbit_2:5672',
                backend='rpc://',
                include=['celery_scraper.tasks']
            )

#Scheduling scraping every 1000 seconds looking for post with key words
app.conf.beat_schedule = {
   'big tasks': {
       'task': 'celery_scraper.tasks.main_scheduled_task',
       'schedule': 1000.0,
       'args': [["f1","koronawirus","mecz","skoki","ciekawostki"]]
   },
}
