from flask import Flask

from config import (
    SECRET_KEY,
    UPLOAD_FOLDER,
)

from database.init_db import init_db

from routes.auth import auth_bp
from routes.screen import screen_bp
from routes.api import api_bp
from routes.admin import admin_bp


app = Flask(__name__)

app.secret_key = SECRET_KEY
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

init_db()

app.register_blueprint(auth_bp)
app.register_blueprint(screen_bp)
app.register_blueprint(api_bp)
app.register_blueprint(admin_bp)

print(app.url_map)

if __name__ == "__main__":
    app.run(
        debug=True,
        host="0.0.0.0",
        port=5000
    )
