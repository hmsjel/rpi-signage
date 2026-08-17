from config import (
    DEFAULT_BILLED_SEKUNDER,
    DEFAULT_TICKER_SEKUNDER,
    DEFAULT_DR_INTERVAL_SEKUNDER,
    DEFAULT_DR_ANTAL,
)


def get_indstilling(conn, nogle, default):
    row = conn.execute("""
        SELECT vaerdi
        FROM indstillinger
        WHERE nogle = ?
    """, (nogle,)).fetchone()

    return row["vaerdi"] if row else default


def set_indstilling(conn, nogle, vaerdi):
    conn.execute("""
        INSERT INTO indstillinger (nogle, vaerdi)
        VALUES (?, ?)
        ON CONFLICT(nogle)
        DO UPDATE SET vaerdi = excluded.vaerdi
    """, (nogle, str(vaerdi)))


def get_int_setting(
    conn,
    key,
    default,
    minimum=None,
    maximum=None
):
    value = get_indstilling(
        conn,
        key,
        str(default)
    )

    try:
        value = int(value)

    except (ValueError, TypeError):
        return default

    if minimum is not None and value < minimum:
        return default

    if maximum is not None and value > maximum:
        return default

    return value


def get_billed_sekunder(conn):
    return get_int_setting(
        conn,
        "billed_sekunder",
        DEFAULT_BILLED_SEKUNDER,
        1,
        120
    )


def get_ticker_sekunder(conn):
    return get_int_setting(
        conn,
        "ticker_sekunder",
        DEFAULT_TICKER_SEKUNDER,
        5,
        300
    )


def get_dr_interval_sekunder(conn):
    return get_int_setting(
        conn,
        "dr_interval_sekunder",
        DEFAULT_DR_INTERVAL_SEKUNDER,
        30,
        3600
    )


def get_dr_antal(conn):
    return get_int_setting(
        conn,
        "dr_antal",
        DEFAULT_DR_ANTAL,
        1,
        20
    )