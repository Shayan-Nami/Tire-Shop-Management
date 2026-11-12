from unittest.mock import Mock

from mssql.base import DatabaseWrapper

from apps.accounts.models import User
from apps.customers.models import Customer
from apps.services_app.models import Service


def _offline_mssql_schema_editor(monkeypatch):
    monkeypatch.setattr('mssql.base.Database.connect', Mock(side_effect=AssertionError('Offline DDL test only')))
    wrapper = DatabaseWrapper(
        {
            'ENGINE': 'mssql',
            'NAME': 'tire_shop_offline_ddl',
            'USER': '',
            'PASSWORD': '',
            'HOST': '127.0.0.1',
            'PORT': '1433',
            'OPTIONS': {'driver': 'ODBC Driver 17 for SQL Server'},
        },
        alias='mssql-ddl-offline',
    )
    wrapper._sql_server_version = 2019
    return wrapper.SchemaEditorClass(wrapper, collect_sql=True)


def test_mssql_filtered_unique_indexes_compile_without_not(monkeypatch):
    schema_editor = _offline_mssql_schema_editor(monkeypatch)

    for model in (User, Customer):
        for constraint in model._meta.constraints:
            sql = str(constraint.create_sql(model, schema_editor))
            assert 'CREATE UNIQUE' in sql.upper()
            assert 'WHERE' in sql.upper()
            where_clause = sql.upper().split('WHERE', 1)[1]
            assert 'IS NOT NULL' in where_clause
            assert "> ''" in where_clause or "> N''" in where_clause
            assert 'NOT' not in where_clause.replace('IS NOT NULL', '')


def test_service_model_mssql_has_no_expression_index_warning(monkeypatch):
    schema_editor = _offline_mssql_schema_editor(monkeypatch)
    warnings = [w for w in Service.check() if w.id == 'models.W044']
    assert warnings == []
    for constraint in Service._meta.constraints:
        sql = str(constraint.create_sql(Service, schema_editor))
        assert sql
