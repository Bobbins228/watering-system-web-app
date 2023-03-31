import json
import logging
import sys
import time
from datetime import datetime
from typing import Iterator

from flask import Flask, Response, render_template, request, stream_with_context, redirect, url_for
#Kafka Consumer
from confluent_kafka import Consumer
import os
import firebase_admin
import pyrebase
from firebase_admin import credentials, auth, db
import pymongo


bootstrap_server = os.environ["BOOTSTRAP_SERVER"]
sasl_user_name = os.environ["CLIENT_ID"]
sasl_password = os.environ["CLIENT_SECRET"]
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
#logging.basicConfig(stream=sys.stdout, level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# Firebase configuration
config = {
  "apiKey": "AIzaSyBWpph3nl5DKhH6ZXFzjVl2rpH4PjnL14E",

    "databaseURL": "https://watering-web-app-default-rtdb.europe-west1.firebasedatabase.app",
  
    "authDomain": "watering-web-app.firebaseapp.com",
  
    "projectId": "watering-web-app",
  
    "storageBucket": "watering-web-app.appspot.com",
  
    "messagingSenderId": "492128153074",
  
    "appId": "1:492128153074:web:83568abde93e84866b8f6b"
}

application = Flask(__name__)

# Initialize Firebase app
firebase = pyrebase.initialize_app(config)
cred = credentials.Certificate('firebase-credentials.json')
firebaseAdmin = firebase_admin.initialize_app(cred, {
	'databaseURL':"https://watering-web-app-default-rtdb.europe-west1.firebasedatabase.app"
	})

# Get a reference to the Firebase Authentication service
regAuth = firebase.auth()

isAuthenticated = False
isAdmin = False

#Connect to Mongo Atlas and set the database to plant-profile and collection to profile
client = pymongo.MongoClient(os.environ["MONGO_STRING"])
mongoDb = client["plant-profile"]
collection = mongoDb["profile"]


# Find a specific profile in the collection and sets it to the profile variable
profile = collection.find_one({"_id": 1})

# Home page
@application.route("/home")
def home():
    # Get the Firebase ID token from the user's browser cookies.
    id_token = request.cookies.get('token')
    global isAuthenticated
    if isAuthenticated == True:
        if id_token:
            try:
                # Verify the ID token and get the user's information.
                try:
                    decoded_token = auth.verify_session_cookie(id_token)
                    user_info = {
                        'uid': decoded_token['uid'],
                        'email': decoded_token.get('email', None)
                    }
                    return render_template('index.html', user=user_info)
                except Exception as e:
                    print(e)
        
            
            except auth.InvalidIdTokenError:
                # The token is invalid or expired. Redirect the user to the login page.
                return redirect(url_for('login'))
    else:
        message = "Please log in to view this page."
        return render_template("login.html",message=message)
    
    # If there's no ID token, redirect the user to the login page.
    return redirect(url_for('login'))

# Sign up page
@application.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        # If the form was submitted, create a new user with the email and password
        email = request.form["email"]
        password = request.form["password"]
        userName = request.form["userName"]
        try:
            user = regAuth.create_user_with_email_and_password(email, password)
            collectionRef = db.reference("users/"+user["localId"])
            collectionRef.set({"email": email, "name": userName, "isAdmin": False})
            # If the user was created successfully, redirect to the login page
            return redirect(url_for('login'))
        except:
            # If there was an error creating the user, render the signup page with an error message
            message = "An error occurred. Please try again."
            return render_template("signup.html", message=message)
    else:
        # If the user has not submitted the form, render the signup page
        return render_template("signup.html")

# Login page
@application.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        # If the form was submitted, authenticate the user with the provided email and password
        email = request.form["email"]
        password = request.form["password"]
        try:
            user = regAuth.sign_in_with_email_and_password(email, password)
            # If the user was authenticated successfully, set a session cookie and redirect to the home page
            session_cookie = auth.create_session_cookie(user['idToken'], expires_in=36000)
            response = redirect(url_for('home'))
            response.set_cookie('token', session_cookie, httponly=True, secure=True)
            ref = db.reference("/users/"+user['localId']+"/")
            adminStatus = ref.child("isAdmin").get()
        
            global isAuthenticated
            isAuthenticated = True
            global isAdmin
            isAdmin = adminStatus
            return response
        except Exception as e:
            print(e)
            
            # If there was an error authenticating the user, render the login page with an error message
            message = "Invalid email or password. Please try again."
            return render_template("login.html", message=message)
    else:

        # If the user has not submitted the form, render the login page
        return render_template("login.html")

# plant profile route
@application.route('/plant-profile', methods=["GET", "POST"])
def profile():
    global isAuthenticated
    global isAdmin
    if isAuthenticated == True:
        if isAdmin == True:
            if request.method == "POST":
                    inputName = request.form["name"]
                    inputWateringType = request.form["watering-type"]
                    try:
                        myquery = { "_id": 1 }
                        newvalues = { "$set": { "name": inputName, "watering-type": inputWateringType } }
                        collection.update_one(myquery, newvalues)
                        return render_template("plant-profile.html")
                    except Exception as e:
                        print(e)
            wateringType = collection.find_one({"_id": 1})["watering-type"]
            name = collection.find_one({"_id": 1})["name"]
            dateWatered = collection.find_one({"_id": 1})["date-last-watered"]
            message = {
                "name": name,
                "wateringType": wateringType,
                "dateWatered": dateWatered
            }
            return render_template("plant-profile.html", message=message)
        
            
            
        else:
            message = "No admin access detected, try a different account."
            return render_template("login.html",message=message)

    else:
        message = "Please log in as an administrator to view this page."
        return render_template("login.html",message=message)
    
    


# Logout route
@application.route('/logout')
def logout():
    # Clear the session cookie and redirect to the login page
    response = redirect(url_for('login'))
    response.set_cookie('session', expires=0)
    global isAuthenticated
    global isAdmin
    isAuthenticated = False
    isAdmin = False
    return response

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


if __name__ == '__main__':
    application.run(debug=True)
