from __future__ import absolute_import
from test_celery.celery import app
from celery.schedules import crontab
import re
from celery import chain, group
import requests
from bs4 import BeautifulSoup
from filelock import FileLock
import influxdb_client
from influxdb_client.client.write_api import SYNCHRONOUS
from langdetect import detect
from pymongo import MongoClient
from gensim.models import KeyedVectors
import numpy as np

@app.on_after_configure.connect
def setup_periodic_tasks(sender, **kwargs):
    sender.add_periodic_task(100.0, main_scheduled_task('sport'), expires=10, name="main_task")

@app.task
def main_scheduled_task(tag_names):

    for tag_name in tag_names:
        get_post_from_wykop = chain(select_newest_tags.s(tag_name) | \
                                    insert_into_db.s() | \
                                    language_detection.s()| \
                                    vectorize_posts.s()| \
                                    send_data.s())
        get_post_from_wykop()
        get_post_from_wykop

@app.task
def select_newest_tags(tag):
    rand_url = "https://www.wykop.pl/tag/wpisy/"+tag+"/najlepsze/"
    page = requests.get(rand_url)
    soup = BeautifulSoup(page.content, 'html.parser')
    content = soup.find_all('li', {"class": "entry iC"})
    results = []
    for con in content:
        post = con.find_all('p', {"class": ""})[0].text
        date = con.find_all('time')[0]['title']
        user_name = con.find_all('a', {"class": "profile"})[0]['href']
        score = con.find_all('p', {"class": "vC"})[0]['data-vc']
        responses = len(con.find_all('div', {"class": "wblock lcontrast dC"}))
        results.append([user_name[28:-1],date, str(re.sub(r'\n', ' ',post)), score, responses]) 
    return results

@app.task
def insert_into_db(results):

    client, bucket, org = get_influx_client()

    post_to_process = []

    write_api = client.write_api(write_options=SYNCHRONOUS)
    for res in results:
        if check_existance(client, bucket, org, res):
            score = influxdb_client.Point(res[0]).tag("date", res[1]).field("score", int(res[3]))
            respones = influxdb_client.Point(res[0]).tag("date", res[1]).field("respones", int(res[4]))

            write_api.write(bucket=bucket, record=score)
            write_api.write(bucket=bucket, record=respones)

            post_to_process.append({'text':res[2], 'score':res[3], 'responses':res[4]})

    return post_to_process

@app.task
def language_detection(posts):
    only_polish = []
    for post in posts:
        lang = detect(post['text'])
        print(lang)
        send_stats_to_db(lang)

        if lang == 'pl':
            only_polish.append(post)

    return only_polish

def get_influx_client():
    bucket = "student"
    org = "student"
    token = "8p8lq2q5NKp1DOwehQ1bNHSfFdJHdyDHYhhvdjW8Zy5LExO-SUAyhNlgNzB3tjW8tQ6GubtLjrrkmagLXKBWyw=="
    # Store the URL of your InfluxDB instance
    url="http://influxdb:8086"

    client = influxdb_client.InfluxDBClient(
        url=url,
        token=token,
        org=org
    )
    return client, bucket, org



def check_existance(client,bucket,org, res):
    query_api = client.query_api()
    query = 'from(bucket:"'+bucket+'")\
    |> range(start: -1d)\
    |> filter(fn:(r) => r._measurement == "'+res[0]+'")\
    |> filter(fn: (r) => r.date == "'+res[1]+'")'
    result = query_api.query(org=org, query=query)
    results = []
    #print(result)
    if len(result) > 0:
        return False
    else:
        return True



@app.task
def vectorize_posts(posts):
    outputs_dev = []
    with FileLock("/app/test_celery/model/word2vec/word2vec_100_3_polish.bin.lock"):
        word2vec = KeyedVectors.load("/app/test_celery/model/word2vec/word2vec_100_3_polish.bin")

        for elem in posts:
            text_vector = embbed_text(elem['text'], word2vec)
            elem['vectorized']= text_vector.tolist()
            #print(text_vector.tolist())
            temp = {'vec': text_vector.tolist(), 'score': elem['score'],'responses':elem['responses']}
            outputs_dev.append(temp)

    return outputs_dev

def embbed_text(text, model):
    splitted = text.split()
    text_vector = np.zeros(model.vector_size)
    iterator = 0
    for s in splitted:
        if s in model.key_to_index:
            text_vector += model[s]
            iterator += 1
        else:
            text_vector += model['nic']
            iterator += 1
    text_vector /= len(splitted)
    return text_vector

@app.task
def send_data(vectorized_posts):
    client = MongoClient("mongo", 27017)
    db = client.posts_with_vec
    collection = db['vectorized_posts']
    for document in vectorized_posts:
        #post = {'vec':document[0], 'score':document[1] , 'responses':document[2]}
        collection.insert_one(document)
    

def send_stats_to_db(lang):
    client, bucket, org = get_influx_client()
    write_api = client.write_api(write_options=SYNCHRONOUS)
    lang_stat = influxdb_client.Point("languages").field(lang, 1)
    write_api.write(bucket=bucket, record=lang_stat)



@app.task
def save_poema(word):
    with FileLock("myfile.txt.lock"):
        print("Lock acquired.")
        with open("myfile.txt", "a+") as myfile:
            myfile.write("{}&&{}&&{}&&{}&&{}\n".format(word[0],word[1],word[2],word[3],word[4]))


@app.task
def big_task(tag):
    rand_url = "https://www.wykop.pl/tag/wpisy/"+tag[0]+"/najlepsze/"
    page = requests.get(rand_url)
    soup = BeautifulSoup(page.content, 'html.parser')
    content = soup.find_all('li', {"class": "entry iC"})
    results = []
    for con in content:
        post = con.find_all('p', {"class": ""})[0].text
        date = con.find_all('time')[0]['title']
        user_name = con.find_all('a', {"class": "profile"})[0]['href']
        score = con.find_all('p', {"class": "vC"})[0]['data-vc']
        responses = len(con.find_all('div', {"class": "wblock lcontrast dC"}))
        results.append([user_name[28:-1],date, str(re.sub(r'\n', ' ',post)), score, responses])

    for word in results:
        with FileLock("rec_file.txt.lock"):
            print("Lock acquired.")
            with open("rec_file.txt", "a+") as myfile:
                myfile.write("{}&&{}&&{}&&{}&&{}\n".format(word[0],word[1],word[2],word[3],word[4]))

    bucket = "student"
    org = "student"
    token = "8p8lq2q5NKp1DOwehQ1bNHSfFdJHdyDHYhhvdjW8Zy5LExO-SUAyhNlgNzB3tjW8tQ6GubtLjrrkmagLXKBWyw=="
    # Store the URL of your InfluxDB instance
    url="http://influxdb:8086"

    client = influxdb_client.InfluxDBClient(
        url=url,
        token=token,
        org=org
    )

    write_api = client.write_api(write_options=SYNCHRONOUS)
    for res in results:
        score = influxdb_client.Point(res[0]).tag("date", res[1]).field("score", int(res[3]))
        respones = influxdb_client.Point(res[0]).tag("date", res[1]).field("respones", int(res[4]))

        write_api.write(bucket=bucket, record=score)
        write_api.write(bucket=bucket, record=respones)
    print("done")

# test tasks

@app.task
def add(x, y):
    z = x + y
    print(z)