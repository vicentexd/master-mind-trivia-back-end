from flask import Flask
from flask_socketio import SocketIO
from dotenv import load_dotenv


load_dotenv()

app = Flask(__name__)
socketio = SocketIO(app,  cors_allowed_origins='*')

from . import routes

app.register_blueprint(routes.bp)
