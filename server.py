import json
import logging
import sys
import time
from datetime import datetime
from typing import Iterator

from flask import Flask, Response, render_template, request, stream_with_context
#Kafka Consumer
from confluent_kafka import Consumer
from dotenv import load_dotenv
import os
load_dotenv(".env")

bootstrap_server = os.getenv("BOOTSTRAP_SERVER")
sasl_user_name = os.getenv("CLIENT_ID")
sasl_password = os.getenv("CLIENT_SECRET")
tempConsumer = Consumer({
    'bootstrap.servers': bootstrap_server,
    'security.protocol': 'SASL_SSL',
    'sasl.mechanisms': 'PLAIN',
    'sasl.username': sasl_user_name,
    'sasl.password': sasl_password,
    'group.id': 'temperature',
    'auto.offset.reset': 'earliest',
})
humidityConsumer = Consumer({
    'bootstrap.servers': bootstrap_server,
    'security.protocol': 'SASL_SSL',
    'sasl.mechanisms': 'PLAIN',
    'sasl.username': sasl_user_name,
    'sasl.password': sasl_password,
    'group.id': 'humidity',
    'auto.offset.reset': 'earliest',
})

tempConsumer.subscribe(['temperature'])
humidityConsumer.subscribe(['humidity'])
logging.basicConfig(stream=sys.stdout, level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

application = Flask(__name__)



@application.route("/")
def index() -> str:
    return render_template("index.html")

def plot_temperature_data() -> Iterator[str]:
    sliced = slice(13,-1)

    if request.headers.getlist("X-Forwarded-For"):
        client_ip = request.headers.getlist("X-Forwarded-For")[0]
    else:
        client_ip = request.remote_addr or ""

    try:
        logger.info("Client %s connected", client_ip)
        while True:
            msg = tempConsumer.poll(1.0)
            if msg is None:
                continue
            if msg.error():
                print("Consumer error: {}".format(msg.error()))
                continue
            
            temp = msg.value().decode('utf-8')  
            temp = temp[sliced]

            json_data = json.dumps(
                {
                    "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "value": float(temp),
                }
            )
            yield f"data:{json_data}\n\n"
            time.sleep(1)
    except GeneratorExit:
        logger.info("Client %s disconnected", client_ip)

def plot_humidity_data() -> Iterator[str]:
    sliced = slice(9,-1)
    if request.headers.getlist("X-Forwarded-For"):
        client_ip = request.headers.getlist("X-Forwarded-For")[0]
    else:
        client_ip = request.remote_addr or ""

    try:
        logger.info("Client %s connected", client_ip)
        while True:
            msg = humidityConsumer.poll(1.0)
            if msg is None:
                continue
            if msg.error():
                print("Consumer error: {}".format(msg.error()))
                continue
            
            humidity = msg.value().decode('utf-8')  
            humidity = humidity[sliced]

            json_data = json.dumps(
                {
                    "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "value": float(humidity),
                }
            )
            yield f"data:{json_data}\n\n"
            time.sleep(1)
    except GeneratorExit:
        logger.info("Client %s disconnected", client_ip)

@application.route("/chart-data")
def chart_data() -> Response:
    response = Response(stream_with_context(plot_temperature_data()), mimetype="text/event-stream")
    response.headers["Cache-Control"] = "no-cache"
    response.headers["X-Accel-Buffering"] = "no"
    return response

@application.route("/chart-humidity-data")
def chart_humidity_data() -> Response:
    response = Response(stream_with_context(plot_humidity_data()), mimetype="text/event-stream")
    response.headers["Cache-Control"] = "no-cache"
    response.headers["X-Accel-Buffering"] = "no"
    return response


if __name__ == "__main__":
    application.run(host="0.0.0.0", threaded=True)
