from flask import Flask, render_template, request, redirect, url_for
import os

app = Flask(__name__)

UPLOAD_FOLDER = "uploads"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

os.makedirs(UPLOAD_FOLDER, exist_ok=True)


@app.route("/")
def index():

    images = []

    for file in os.listdir(UPLOAD_FOLDER):
        if file.lower().endswith((".jpg", ".jpeg", ".png", ".gif")):
            images.append(file)

    print("Billeder:", images)

    return render_template("index.html", images=images)
@app.route("/admin", methods=["GET", "POST"])
def admin():

    if request.method == "POST":

        file = request.files["file"]

        if file.filename != "":
            file.save(
                os.path.join(
                    app.config["UPLOAD_FOLDER"],
                    file.filename
                )
            )

        return redirect(url_for("admin"))

    files = os.listdir(UPLOAD_FOLDER)

    return render_template(
        "admin.html",
        files=files
    )

from flask import send_from_directory

@app.route("/uploads/<filename>")
def uploaded_file(filename):
    return send_from_directory(
        app.config["UPLOAD_FOLDER"],
        filename
    )

if __name__ == "__main__":
    app.run(debug=True)

