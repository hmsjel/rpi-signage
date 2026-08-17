from config import ALLOWED_EXTENSIONS


def allowed_file(filename):
    if not filename or "." not in filename:
        return False

    extension = filename.rsplit(".", 1)[1].lower()

    return extension in ALLOWED_EXTENSIONS


def hent_lokale_nyheder(conn):
    rows = conn.execute("""
        SELECT tekst
        FROM ticker
        ORDER BY id ASC
    """).fetchall()

    return [row["tekst"] for row in rows]


def hent_alle_nyheder_til_admin(conn):
    rows = conn.execute("""
        SELECT id, tekst
        FROM ticker
        ORDER BY id ASC
    """).fetchall()

    return rows