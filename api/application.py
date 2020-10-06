from flask import Flask, request, jsonify
from flask_api import status

from api_calls.menu_calls import menu_calls
from api_calls.order_calls import order_calls

application = Flask(__name__)

@application.route("/")
def home():
    return "<h1>RBC Restaurant REST API</h1><h2>By Daman Sharma</h2>"

# Blueprints for APIs defined in respective .py files under api_calls folder
application.register_blueprint(menu_calls)

application.register_blueprint(order_calls)

if __name__ == "__main__":
    application.run(port=5000, debug=True)