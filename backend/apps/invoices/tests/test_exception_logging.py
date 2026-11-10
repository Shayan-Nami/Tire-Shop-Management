import logging

from django.db import IntegrityError

from utils.exceptions import custom_exception_handler


def test_integrity_error_is_logged_with_traceback_and_still_returns_400(caplog):
    with caplog.at_level(logging.WARNING, logger='apps'):
        try:
            raise IntegrityError('duplicate key value violates unique constraint "uq_demo"')
        except IntegrityError as exc:
            response = custom_exception_handler(exc, {})

    assert response.status_code == 400
    assert 'یکپارچگی' in str(response.data['errors'])
    records = [r for r in caplog.records if r.name == 'apps' and r.levelno == logging.WARNING]
    assert len(records) == 1
    assert 'uq_demo' in records[0].getMessage()
    assert records[0].exc_info and records[0].exc_info[1] is not None
