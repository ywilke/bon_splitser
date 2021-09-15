from flask import Flask
from flask_bootstrap import Bootstrap

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 2 * 1000 * 1000  # Max file size is 2MB
Bootstrap(app)
from app import routes
