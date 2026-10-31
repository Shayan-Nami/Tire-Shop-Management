import runpy
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from django.core.exceptions import ImproperlyConfigured
from mssql.base import DatabaseWrapper


@pytest.fixture
def database_settings(monkeypatch):
    def load(**overrides):
        with monkeypatch.context() as env:
            defaults = {
                'DJANGO_DEBUG': 'False',
                'DJANGO_SECRET_KEY': 'database-settings-test-only-not-a-production-secret-8274',
                'DB_ENGINE': 'mssql',
                'USE_SQL_SERVER': 'False',
                'DB_NAME': 'audit_db',
                'DB_HOST': '127.0.0.1',
                'DB_PORT': '1433',
                'DB_USER': '',
                'DB_PASSWORD': 'synthetic-test-password',
                'DB_DRIVER': 'ODBC Driver 17 for SQL Server',
                'DB_TRUSTED_CONNECTION': None,
                'DB_ENCRYPT': None,
                'DB_TRUST_SERVER_CERTIFICATE': None,
            }
            for name, value in {**defaults, **overrides}.items():
                if value is None:
                    env.delenv(name, raising=False)
                else:
                    env.setenv(name, value)
            with patch('dotenv.load_dotenv', return_value=False):
                config = runpy.run_path(str(Path(__file__).with_name('settings.py')))
            return config['DATABASES']['default']
    return load


@pytest.fixture
def connection_parameters(monkeypatch):
    connect = Mock(side_effect=AssertionError('Settings tests must not open native connections'))
    monkeypatch.setattr('mssql.base.Database.connect', connect)

    def build(database):
        wrapper = DatabaseWrapper(database, alias='settings-test')
        params = wrapper.get_connection_params()
        text = wrapper._build_connection_string(params, params['OPTIONS']['driver'])
        connect.assert_not_called()
        return dict(part.split('=', 1) for part in text.split(';') if part)
    return build


@pytest.mark.parametrize(('user', 'trusted', 'expected_trusted', 'expected_user'), [
    ('', None, 'yes', ''),
    ('sql_user', None, 'no', 'sql_user'),
    ('', 'False', 'no', ''),
    ('sql_user', 'False', 'no', 'sql_user'),
    ('', 'True', 'yes', ''),
    ('sql_user', 'True', 'yes', ''),
])
def test_sql_server_authentication_and_secure_defaults(
    database_settings, connection_parameters, user, trusted, expected_trusted, expected_user,
):
    database = database_settings(DB_USER=user, DB_TRUSTED_CONNECTION=trusted)
    assert database['Trusted_Connection'] == expected_trusted
    assert database['USER'] == expected_user
    assert database['PASSWORD'] == ('synthetic-test-password' if expected_user else '')
    extras = database['OPTIONS']['extra_params']
    assert 'Trusted_Connection' not in extras
    assert extras == 'Encrypt=yes;TrustServerCertificate=no;'

    params = connection_parameters(database)
    assert params['Encrypt'] == 'yes'
    assert params['TrustServerCertificate'] == 'no'
    if expected_user:
        assert params['UID'] == expected_user
        assert params['PWD'] == 'synthetic-test-password'
        assert 'Trusted_Connection' not in params
    else:
        assert 'UID' not in params
        assert 'PWD' not in params
        assert params['Trusted_Connection'] == expected_trusted


@pytest.mark.parametrize(('encrypt', 'trust_certificate', 'expected_encrypt', 'expected_trust'), [
    ('no', 'yes', 'no', 'yes'),
    ('0', '1', 'no', 'yes'),
    ('False', 'True', 'no', 'yes'),
    (' YES ', ' no ', 'yes', 'no'),
])
def test_sql_server_tls_overrides(
    database_settings, connection_parameters, encrypt, trust_certificate, expected_encrypt, expected_trust,
):
    database = database_settings(
        DB_USER='sql_user', DB_ENCRYPT=encrypt,
        DB_TRUST_SERVER_CERTIFICATE=trust_certificate,
    )
    params = connection_parameters(database)
    assert params['Encrypt'] == expected_encrypt
    assert params['TrustServerCertificate'] == expected_trust
    assert 'Trusted_Connection' not in params


@pytest.mark.parametrize('name', [
    'DB_TRUSTED_CONNECTION', 'DB_ENCRYPT', 'DB_TRUST_SERVER_CERTIFICATE',
])
def test_sql_server_rejects_invalid_security_boolean(database_settings, name):
    with pytest.raises(ImproperlyConfigured, match=name):
        database_settings(**{name: 'invalid'})


@pytest.mark.parametrize(('engine', 'expected_backend'), [
    ('sqlite', 'django.db.backends.sqlite3'),
    ('postgres', 'django.db.backends.postgresql'),
])
def test_sql_server_controls_do_not_change_other_backends(database_settings, engine, expected_backend):
    database = database_settings(
        DB_ENGINE=engine, DB_TRUSTED_CONNECTION='invalid',
        DB_ENCRYPT='invalid', DB_TRUST_SERVER_CERTIFICATE='invalid',
    )
    assert database['ENGINE'] == expected_backend
    assert 'Trusted_Connection' not in database
