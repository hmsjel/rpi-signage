import os
import shutil
import uuid

from datetime import datetime, date

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

from werkzeug.utils import secure_filename

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


# ============================================================
# AUTOMATISK UDLØB
# ============================================================

def opdater_udloebne_medier(conn):
    """
    Deaktiverer automatisk medier, hvor udløbsdatoen
    er overskredet.

    Et medie med udløbsdato i dag er stadig aktivt.
    """

    i_dag = date.today().isoformat()

    conn.execute(
        """
        UPDATE medier
        SET aktiv = 0
        WHERE udloebs_dato IS NOT NULL
        AND udloebs_dato != ''
        AND udloebs_dato < ?
        """,
        (i_dag,)
    )

    conn.commit()


# ============================================================
# ADMIN
# ============================================================

@admin_bp.route(
    "/admin",
    methods=["GET", "POST"]
)
def admin():

    if not session.get("logget_ind"):
        return redirect(
            url_for("auth.login")
        )

    # --------------------------------------------------------
    # VEJRBYER
    # --------------------------------------------------------

    byer_koordinater = {
        "Skovgaarde": {
            "lat": "56.50941163",
            "lon": "10.5417551"
        },
        "Aarhus": {
            "lat": "56.1567",
            "lon": "10.2108"
        },
        "Randers": {
            "lat": "56.4607",
            "lon": "10.0357"
        },
        "Grenaa": {
            "lat": "56.4158",
            "lon": "10.8783"
        },
        "Ebeltoft": {
            "lat": "56.1952",
            "lon": "10.6831"
        },
        "København": {
            "lat": "55.6761",
            "lon": "12.5683"
        },
        "Aalborg": {
            "lat": "57.0488",
            "lon": "9.9217"
        },
        "Odense": {
            "lat": "55.4038",
            "lon": "10.4024"
        },
    }

    conn = get_db_connection()

    try:

        # ----------------------------------------------------
        # AUTOMATISK DEAKTIVERING AF UDLØBNE MEDIER
        # ----------------------------------------------------

        opdater_udloebne_medier(conn)

        # ====================================================
        # POST
        # ====================================================

        if request.method == "POST":

            # ------------------------------------------------
            # NY LOKAL NYHED
            # ------------------------------------------------

            if "nyhed_tekst" in request.form:

                tekst = request.form.get(
                    "nyhed_tekst",
                    ""
                ).strip()

                if tekst:

                    conn.execute(
                        """
                        INSERT INTO ticker (
                            tekst
                        )
                        VALUES (?)
                        """,
                        (tekst,)
                    )

                    conn.commit()

            # ------------------------------------------------
            # UPLOAD MEDIE
            # ------------------------------------------------

            elif "medie_fil" in request.files:

                fil = request.files[
                    "medie_fil"
                ]

                start = request.form.get(
                    "start_dato",
                    ""
                ).strip()

                udloeb = request.form.get(
                    "udloeb_dato",
                    ""
                ).strip()

                # --------------------------------------------
                # Kontroller fil
                # --------------------------------------------

                if (
                    fil
                    and fil.filename
                    and allowed_file(
                        fil.filename
                    )
                ):

                    # ----------------------------------------
                    # SIKKERT FILNAVN
                    # ----------------------------------------

                    original_filnavn = (
                        secure_filename(
                            fil.filename
                        )
                    )

                    if not original_filnavn:
                        return redirect(
                            url_for(
                                "admin.admin"
                            )
                        )

                    # ----------------------------------------
                    # Lav unikt filnavn
                    #
                    # Eksempel:
                    # billede.jpg
                    #
                    # bliver til:
                    # billede_a8f31c.jpg
                    # ----------------------------------------

                    filnavn, filendelse = os.path.splitext(
                        original_filnavn
                    )

                    unikt_id = uuid.uuid4().hex[:8]

                    filnavn = (
                        f"{filnavn}_"
                        f"{unikt_id}"
                        f"{filendelse.lower()}"
                    )

                    upload_folder = (
                        current_app.config[
                            "UPLOAD_FOLDER"
                        ]
                    )

                    filsti = os.path.join(
                        upload_folder,
                        filnavn
                    )

                    # ----------------------------------------
                    # Gem fil
                    # ----------------------------------------

                    fil.save(filsti)

                    # ----------------------------------------
                    # Nyt medie er aktivt som udgangspunkt
                    #
                    # Hvis udløbsdato allerede er overskredet,
                    # sættes det til inaktivt.
                    #
                    # Startdato håndteres af skærmens
                    # SQL-filter.
                    # ----------------------------------------

                    aktiv = 1

                    if udloeb:

                        if (
                            udloeb
                            < date.today().isoformat()
                        ):
                            aktiv = 0

                    # ----------------------------------------
                    # Gem i database
                    # ----------------------------------------

                    conn.execute(
                        """
                        INSERT INTO medier (
                            filnavn,
                            aktiv,
                            start_dato,
                            udloebs_dato
                        )
                        VALUES (?, ?, ?, ?)
                        """,
                        (
                            filnavn,
                            aktiv,
                            start or None,
                            udloeb or None
                        )
                    )

                    conn.commit()

            # ------------------------------------------------
            # BILLEDHASTIGHED
            # ------------------------------------------------

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

            # ------------------------------------------------
            # TICKERHASTIGHED
            # ------------------------------------------------

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

            # ------------------------------------------------
            # DR NYHEDER
            # ------------------------------------------------

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

                    # ----------------------------------------
                    # Interval
                    # ----------------------------------------

                    if 30 <= interval <= 3600:

                        set_indstilling(
                            conn,
                            "dr_interval_sekunder",
                            interval
                        )

                    # ----------------------------------------
                    # Antal nyheder
                    # ----------------------------------------

                    if 1 <= antal <= 20:

                        set_indstilling(
                            conn,
                            "dr_antal",
                            antal
                        )

                    conn.commit()

                    # Tøm nyhedscachen så de nye
                    # indstillinger bruges med det samme.
                    reset_news_cache()

                except (
                    ValueError,
                    TypeError,
                    KeyError,
                ):
                    pass

            # ------------------------------------------------
            # VEJRBY
            # ------------------------------------------------

            elif "valgt_by" in request.form:

                by_navn = request.form[
                    "valgt_by"
                ]

                if by_navn in byer_koordinater:

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

            # ------------------------------------------------
            # TILBAGE TIL ADMIN
            # ------------------------------------------------

            return redirect(
                url_for("admin.admin")
            )

        # ====================================================
        # HENT DATA TIL ADMIN
        # ====================================================

        alle_medier = conn.execute(
            """
            SELECT *
            FROM medier
            ORDER BY id ASC
            """
        ).fetchall()

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

    # ========================================================
    # LAGERPLADS
    # ========================================================

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

    # ========================================================
    # DATO
    # ========================================================

    current_date = (
        datetime.now().strftime(
            "%Y-%m-%d"
        )
    )

    # ========================================================
    # RENDER ADMIN
    # ========================================================

    return render_template(
        "admin.html",

        medier=alle_medier,

        nyheder=alle_nyheder,

        nuvaerende_sekunder=(
            billed_sekunder
        ),

        nuvaerende_ticker_sekunder=(
            ticker_sekunder
        ),

        dr_interval_sekunder=(
            dr_interval_sekunder
        ),

        dr_antal=(
            dr_antal
        ),

        nuvaerende_by=(
            nuvaerende_by
        ),

        byer=list(
            byer_koordinater.keys()
        ),

        current_date=(
            current_date
        ),

        disk_total_gb=(
            f"{total_gb:.1f}"
        ),

        disk_used_gb=(
            f"{used_gb:.1f}"
        ),

        disk_free_gb=(
            f"{free_gb:.1f}"
        ),

        disk_used_percent=round(
            used_percent,
            1
        ),
    )


# ============================================================
# SKIFT AKTIV / INAKTIV
# ============================================================

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

        medie = conn.execute(
            """
            SELECT
                id,
                udloebs_dato
            FROM medier
            WHERE id = ?
            """,
            (id,)
        ).fetchone()

        if not medie:

            return jsonify(
                success=False,
                error="Medie ikke fundet"
            ), 404

        # ----------------------------------------------------
        # Et udløbet medie må ikke aktiveres igen
        # ----------------------------------------------------

        if ny_status == 1:

            udloebs_dato = medie["udloebs_dato"]

            if udloebs_dato:

                if udloebs_dato < date.today().isoformat():

                    return jsonify(
                        success=False,
                        error="Mediet er udløbet"
                    ), 400

        conn.execute(
            """
            UPDATE medier
            SET aktiv = ?
            WHERE id = ?
            """,
            (
                ny_status,
                id
            )
        )

        conn.commit()

    finally:

        conn.close()

    return jsonify(
        success=True
    )

# ============================================================
# ÆNDRE STARTDATO OG UDLØBSDATO
# ============================================================

@admin_bp.route(
    "/aendre-datoer/<int:id>",
    methods=["POST"]
)
def aendre_datoer(id):

    if not session.get("logget_ind"):

        return redirect(
            url_for("auth.login")
        )

    start_dato = request.form.get(
        "start_dato",
        ""
    ).strip()

    udloebs_dato = request.form.get(
        "udloebs_dato",
        ""
    ).strip()

    # --------------------------------------------------------
    # Valider datoformat
    # --------------------------------------------------------

    def gyldig_dato(dato):

        if not dato:
            return True

        try:

            datetime.strptime(
                dato,
                "%Y-%m-%d"
            )

            return True

        except ValueError:

            return False

    if not gyldig_dato(start_dato):
        return redirect(
            url_for("admin.admin")
        )

    if not gyldig_dato(udloebs_dato):
        return redirect(
            url_for("admin.admin")
        )

    # --------------------------------------------------------
    # Kontroller at startdato ikke ligger efter udløbsdato
    # --------------------------------------------------------

    if (
        start_dato
        and udloebs_dato
        and start_dato > udloebs_dato
    ):

        return redirect(
            url_for("admin.admin")
        )

    conn = get_db_connection()

    try:

        # ----------------------------------------------------
        # Hvis udløbsdato er overskredet,
        # skal mediet være inaktivt.
        # ----------------------------------------------------

        if udloebs_dato:

            i_dag = (
                date.today().isoformat()
            )

            if udloebs_dato < i_dag:

                conn.execute(
                    """
                    UPDATE medier
                    SET
                        start_dato = ?,
                        udloebs_dato = ?,
                        aktiv = 0
                    WHERE id = ?
                    """,
                    (
                        start_dato or None,
                        udloebs_dato,
                        id
                    )
                )

            else:

                # ------------------------------------------------
                # Udløbsdato er stadig gyldig.
                #
                # Vi ændrer IKKE aktiv-status her.
                # Det betyder, at hvis brugeren manuelt har
                # deaktiveret mediet, forbliver det deaktiveret.
                # ------------------------------------------------

                conn.execute(
                    """
                    UPDATE medier
                    SET
                        start_dato = ?,
                        udloebs_dato = ?
                    WHERE id = ?
                    """,
                    (
                        start_dato or None,
                        udloebs_dato,
                        id
                    )
                )

        else:

            # ----------------------------------------------------
            # Ingen udløbsdato
            # ----------------------------------------------------

            conn.execute(
                """
                UPDATE medier
                SET
                    start_dato = ?,
                    udloebs_dato = NULL
                WHERE id = ?
                """,
                (
                    start_dato or None,
                    id
                )
            )

        conn.commit()

    finally:

        conn.close()

    return redirect(
        url_for("admin.admin")
    )


# ============================================================
# SLET MEDIE
# ============================================================

@admin_bp.route(
    "/slet/<int:id>"
)
def slet(id):

    if not session.get("logget_ind"):

        return redirect(
            url_for("auth.login")
        )

    conn = get_db_connection()

    try:

        medie = conn.execute(
            """
            SELECT filnavn
            FROM medier
            WHERE id = ?
            """,
            (id,)
        ).fetchone()

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

            conn.execute(
                """
                DELETE FROM medier
                WHERE id = ?
                """,
                (id,)
            )

            conn.commit()

    finally:

        conn.close()

    return redirect(
        url_for("admin.admin")
    )


# ============================================================
# SLET LOKAL NYHED
# ============================================================

@admin_bp.route(
    "/slet-nyhed/<int:id>"
)
def slet_nyhed(id):

    if not session.get("logget_ind"):

        return redirect(
            url_for("auth.login")
        )

    conn = get_db_connection()

    try:

        conn.execute(
            """
            DELETE FROM ticker
            WHERE id = ?
            """,
            (id,)
        )

        conn.commit()

    finally:

        conn.close()

    return redirect(
        url_for("admin.admin")
    )


# ============================================================
# VIS UPLOADET FIL
# ============================================================

@admin_bp.route(
    "/uploads/<path:filename>"
)
def uploaded_file(filename):

    return send_from_directory(
        current_app.config[
            "UPLOAD_FOLDER"
        ],
        filename
    )