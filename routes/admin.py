import os
import shutil
from datetime import datetime

from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    jsonify,
    session,
    current_app,
    send_from_directory,
)

from database.db import get_db_connection

from database.settings import (
    get_indstilling,
    set_indstilling,
    get_billed_sekunder,
    get_ticker_sekunder,
    get_dr_interval_sekunder,
    get_dr_antal,
)

from services.media import (
    allowed_file,
    hent_alle_nyheder_til_admin,
)

from services.rss import (
    reset_news_cache,
)

from config import (
    VEJR_BY,
    BASE_DIR,
)

admin_bp = Blueprint(
    "admin",
    __name__,
)


@admin_bp.route("/admin", methods=["GET", "POST"])
def admin():

    if not session.get("logget_ind"):
        return redirect(url_for("auth.login"))

    byer_koordinater = {
        "Skovgaarde": {"lat": "56.50941163", "lon": "10.5417551"},
        "Aarhus": {"lat": "56.1567", "lon": "10.2108"},
        "Randers": {"lat": "56.4607", "lon": "10.0357"},
        "Grenaa": {"lat": "56.4158", "lon": "10.8783"},
        "Ebeltoft": {"lat": "56.1952", "lon": "10.6831"},
        "København": {"lat": "55.6761", "lon": "12.5683"},
        "Aalborg": {"lat": "57.0488", "lon": "9.9217"},
        "Odense": {"lat": "55.4038", "lon": "10.4024"},
    }

    conn = get_db_connection()

    try:

        if request.method == "POST":

            # -----------------------------------
            # NYHED
            # -----------------------------------

            if "nyhed_tekst" in request.form:

                tekst = request.form[
                    "nyhed_tekst"
                ].strip()

                if tekst:

                    conn.execute("""
                        INSERT INTO ticker (
                            tekst
                        )
                        VALUES (?)
                    """, (tekst,))

                    conn.commit()

            # -----------------------------------
            # UPLOAD
            # -----------------------------------

            elif "medie_fil" in request.files:

                fil = request.files["medie_fil"]

                udloeb = request.form.get(
                    "udloeb_dato",
                    ""
                ).strip()

                if (
                    fil
                    and fil.filename
                    and allowed_file(
                        fil.filename
                    )
                ):

                    filnavn = os.path.basename(
                        fil.filename
                    )

                    fil.save(
                        os.path.join(
                            current_app.config[
                                "UPLOAD_FOLDER"
                            ],
                            filnavn
                        )
                    )

                    conn.execute("""
                        INSERT INTO medier (
                            filnavn,
                            aktiv,
                            udloebs_dato
                        )
                        VALUES (
                            ?, 1, ?
                        )
                    """, (
                        filnavn,
                        udloeb
                    ))

                    conn.commit()

            # -----------------------------------
            # BILLEDHASTIGHED
            # -----------------------------------

            elif "billed_sekunder" in request.form:

                try:

                    value = int(
                        request.form[
                            "billed_sekunder"
                        ]
                    )

                    if 1 <= value <= 120:

                        set_indstilling(
                            conn,
                            "billed_sekunder",
                            value
                        )

                        conn.commit()

                except (
                    ValueError,
                    TypeError,
                ):
                    pass

            # -----------------------------------
            # TICKERHASTIGHED
            # -----------------------------------

            elif "ticker_sekunder" in request.form:

                try:

                    value = int(
                        request.form[
                            "ticker_sekunder"
                        ]
                    )

                    if 5 <= value <= 300:

                        set_indstilling(
                            conn,
                            "ticker_sekunder",
                            value
                        )

                        conn.commit()

                except (
                    ValueError,
                    TypeError,
                ):
                    pass

            # -----------------------------------
            # DR
            # -----------------------------------

            elif (
                "dr_interval_sekunder"
                in request.form
            ):

                try:

                    interval = int(
                        request.form[
                            "dr_interval_sekunder"
                        ]
                    )

                    antal = int(
                        request.form[
                            "dr_antal"
                        ]
                    )

                    if (
                        30
                        <= interval
                        <= 3600
                    ):
                        set_indstilling(
                            conn,
                            "dr_interval_sekunder",
                            interval
                        )

                    if (
                        1
                        <= antal
                        <= 20
                    ):
                        set_indstilling(
                            conn,
                            "dr_antal",
                            antal
                        )

                    conn.commit()

                    reset_news_cache()

                except (
                    ValueError,
                    TypeError,
                    KeyError,
                ):
                    pass

            # -----------------------------------
            # VEJRBY
            # -----------------------------------

            elif "valgt_by" in request.form:

                by_navn = request.form[
                    "valgt_by"
                ]

                if (
                    by_navn
                    in byer_koordinater
                ):

                    set_indstilling(
                        conn,
                        "vejr_by",
                        by_navn
                    )

                    set_indstilling(
                        conn,
                        "vejr_lat",
                        byer_koordinater[
                            by_navn
                        ]["lat"]
                    )

                    set_indstilling(
                        conn,
                        "vejr_lon",
                        byer_koordinater[
                            by_navn
                        ]["lon"]
                    )

                    conn.commit()

            return redirect(
                url_for("admin.admin")
            )

        alle_medier = conn.execute("""
            SELECT *
            FROM medier
            ORDER BY id ASC
        """).fetchall()

        alle_nyheder = (
            hent_alle_nyheder_til_admin(
                conn
            )
        )

        billed_sekunder = (
            get_billed_sekunder(conn)
        )

        ticker_sekunder = (
            get_ticker_sekunder(conn)
        )

        dr_interval_sekunder = (
            get_dr_interval_sekunder(conn)
        )

        dr_antal = (
            get_dr_antal(conn)
        )

        nuvaerende_by = (
            get_indstilling(
                conn,
                "vejr_by",
                VEJR_BY
            )
        )

    finally:
        conn.close()

    try:

        total, used, free = (
            shutil.disk_usage(
                BASE_DIR
            )
        )

        total_gb = (
            total / (1024 ** 3)
        )

        used_gb = (
            used / (1024 ** 3)
        )

        free_gb = (
            free / (1024 ** 3)
        )

        used_percent = (
            used / total * 100
        )

    except Exception:

        total_gb = 0
        used_gb = 0
        free_gb = 0
        used_percent = 0

    current_date = datetime.now().strftime(
        "%Y-%m-%d"
    )

    return render_template(
        "admin.html",
        medier=alle_medier,
        nyheder=alle_nyheder,
        nuvaerende_sekunder=billed_sekunder,
        nuvaerende_ticker_sekunder=ticker_sekunder,
        dr_interval_sekunder=dr_interval_sekunder,
        dr_antal=dr_antal,
        nuvaerende_by=nuvaerende_by,
        byer=list(
            byer_koordinater.keys()
        ),
        current_date=current_date,
        disk_total_gb=f"{total_gb:.1f}",
        disk_used_gb=f"{used_gb:.1f}",
        disk_free_gb=f"{free_gb:.1f}",
        disk_used_percent=round(
            used_percent,
            1
        ),
    )


@admin_bp.route(
    "/skift-status/<int:id>",
    methods=["POST"]
)
def skift_status(id):

    if not session.get("logget_ind"):
        return jsonify(
            success=False,
            error="Ikke logget ind"
        ), 401

    data = request.get_json(
        silent=True
    )

    if not data:
        return jsonify(
            success=False,
            error="Ingen data modtaget"
        ), 400

    ny_status = (
        1
        if data.get("aktiv")
        else 0
    )

    conn = get_db_connection()

    try:

        cursor = conn.execute("""
            UPDATE medier
            SET aktiv = ?
            WHERE id = ?
        """, (
            ny_status,
            id
        ))

        conn.commit()

        if cursor.rowcount == 0:

            return jsonify(
                success=False,
                error="Medie ikke fundet"
            ), 404

    finally:
        conn.close()

    return jsonify(success=True)


@admin_bp.route(
    "/aendre-udloeb/<int:id>",
    methods=["POST"]
)
def aendre_udloeb(id):

    if not session.get("logget_ind"):
        return redirect(
            url_for("auth.login")
        )

    udloeb = request.form.get(
        "udloeb_dato",
        ""
    ).strip()

    udloeb = (
        udloeb
        if udloeb
        else None
    )

    conn = get_db_connection()

    try:

        cursor = conn.execute("""
            UPDATE medier
            SET udloebs_dato = ?
            WHERE id = ?
        """, (
            udloeb,
            id
        ))

        conn.commit()

        if cursor.rowcount == 0:
            return (
                "Medie ikke fundet",
                404
            )

    finally:
        conn.close()

    return redirect(
        url_for("admin.admin")
    )

@admin_bp.route("/slet/<int:id>")
def slet(id):

    if not session.get("logget_ind"):
        return redirect(
            url_for("auth.login")
        )

    conn = get_db_connection()

    try:

        medie = conn.execute("""
            SELECT filnavn
            FROM medier
            WHERE id = ?
        """, (id,)).fetchone()

        if medie:

            filsti = os.path.join(
                current_app.config[
                    "UPLOAD_FOLDER"
                ],
                medie["filnavn"]
            )

            try:
                os.remove(filsti)

            except FileNotFoundError:
                pass

            conn.execute("""
                DELETE FROM medier
                WHERE id = ?
            """, (id,))

            conn.commit()

    finally:
        conn.close()

    return redirect(
        url_for("admin.admin")
    )


@admin_bp.route("/slet-nyhed/<int:id>")
def slet_nyhed(id):

    if not session.get("logget_ind"):
        return redirect(
            url_for("auth.login")
        )

    conn = get_db_connection()

    try:

        conn.execute("""
            DELETE FROM ticker
            WHERE id = ?
        """, (id,))

        conn.commit()

    finally:
        conn.close()

    return redirect(
        url_for("admin.admin")
    )


@admin_bp.route("/uploads/<path:filename>")
def uploaded_file(filename):

    return send_from_directory(
        current_app.config[
            "UPLOAD_FOLDER"
        ],
        filename
    )

