"""Exercise production preflight SQL against the existing ephemeral PG fixtures."""
from uuid import uuid4
from white_list_archive.normalisation.cosenza_preflight import verify_relational_input


def check_cosenza_preflight_relational(conn, *, capture_id, parse_run_id,
                                      mismatched_capture_id):
    with conn.cursor() as cur:
        cur.execute('''SELECT co.sha256 FROM source.source_capture sc
            JOIN source.content_object co USING(content_object_id)
            WHERE sc.capture_id=%s''', (capture_id,))
        sha256 = cur.fetchone()[0]
    kwargs = dict(capture_id=str(capture_id), parse_run_id=str(parse_run_id), sha256=sha256)
    # Existing valid scalar run may have zero edition links: these are reported,
    # never invented or interpreted as automatic approval by the preflight.
    verify_relational_input(conn, **kwargs)

    def rejected(**override):
        try:
            verify_relational_input(conn, **dict(kwargs, **override))
        except ValueError:
            return
        raise AssertionError('Cosenza preflight accepted mismatched or unsuccessful input')

    rejected(capture_id=str(mismatched_capture_id))
    rejected(parse_run_id=str(uuid4()))
    rejected(sha256='0' * 64)
    with conn.cursor() as cur:
        cur.execute('SAVEPOINT preflight_unsuccessful_run')
        cur.execute("UPDATE source.parse_run SET status_code='failed' WHERE parse_run_id=%s",
                    (parse_run_id,))
    try:
        rejected()
    finally:
        with conn.cursor() as cur:
            cur.execute('ROLLBACK TO SAVEPOINT preflight_unsuccessful_run')
            cur.execute('RELEASE SAVEPOINT preflight_unsuccessful_run')
    verify_relational_input(conn, **kwargs)
