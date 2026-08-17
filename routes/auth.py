from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    session,
)

from config import (
    ADMIN_BRUGERNAVN,
    ADMIN_KODE,
)

auth_bp = Blueprint(
    "auth",
    __name__
)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        brugernavn = request.form.get(
            "brugernavn",
            ""
        ).strip()

        kode = request.form.get(
            "kode",
            ""
        ).strip()

        if (
            brugernavn == ADMIN_BRUGERNAVN
            and kode == ADMIN_KODE
        ):

            session["logget_ind"] = True

            return redirect(
                url_for("admin.admin")
            )

        return render_template(
            "login.html",
            fejl="Forkert brugernavn eller kode"
        )

    return render_template(
        "login.html"
    )


@auth_bp.route("/logout")
def logout():

    session.pop(
        "logget_ind",
        None
    )

    return redirect(
        url_for("auth.login")
    )