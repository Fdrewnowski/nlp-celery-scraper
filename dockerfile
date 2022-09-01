FROM python:3.8
ENV HOME /app
ADD ./requirements.txt /app/requirements.txt
ADD ./celery_scraper/ /app/
WORKDIR /app/
EXPOSE 9091
RUN pip install -r requirements.txt
ENTRYPOINT celery -A test_celery worker -B --autoscale 3 --loglevel=info
