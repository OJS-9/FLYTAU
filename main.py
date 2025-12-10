from flask import Flask, render_template, request, redirect, session
from flask_session import Session
from datetime import timedelta
from utils import *

app = Flask(__name__)

app.config.update(
    SESSION_TYPE="filesystem",
    SESSION_FILE_DIR="sessions",
    SESSION_PERMANENT=True,
    PERMANENT_SESSION_LIFETIME=timedelta(minutes=30),
    SESSION_REFRESH_EACH_REQUEST=True,
    SESSION_COOKIE_SECURE=True,
)
Session(app)

