from unittest.mock import Mock

from django.db import migrations
from django.db.migrations.loader import MigrationLoader
from django.db.migrations.state import ProjectState
from mssql.base import DatabaseWrapper

from apps.accounts.models import User
from apps.customers.models import Customer
from apps.invoices.models import SalesInvoice
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


def _assert_filtered_unique_index_sql_is_mssql_safe(sql: str) -> None:
    upper = sql.upper()
    assert 'CREATE UNIQUE' in upper
    assert 'WHERE' in upper
    where_clause = upper.split('WHERE', 1)[1]
    assert 'IS NOT NULL' in where_clause
    assert "> ''" in where_clause or "> N''" in where_clause
    assert 'NOT (' not in where_clause
    assert 'NOT' not in where_clause.replace('IS NOT NULL', '')


def test_mssql_filtered_unique_indexes_compile_without_not(monkeypatch):
    schema_editor = _offline_mssql_schema_editor(monkeypatch)

    for model in (User, Customer):
        for constraint in model._meta.constraints:
            sql = str(constraint.create_sql(model, schema_editor))
            _assert_filtered_unique_index_sql_is_mssql_safe(sql)


def test_mssql_historical_filtered_unique_migrations_compile_without_not(monkeypatch):
    schema_editor = _offline_mssql_schema_editor(monkeypatch)
    loader = MigrationLoader(None, ignore_no_migrations=True)
    targets = [
        ('accounts', '0004_alter_user_phone_number_and_more'),
        ('accounts', '0005_remove_user_unique_user_phone_number_not_null_and_more'),
        ('customers', '0004_alter_customer_national_code_and_more'),
        ('customers', '0005_remove_customer_unique_customer_phone_number_not_null_and_more'),
    ]

    for app_label, migration_name in targets:
        plan = loader.graph.forwards_plan((app_label, migration_name))
        state = ProjectState()
        for node in plan:
            migration = loader.get_migration(*node)
            next_state = migration.mutate_state(state, preserve=True)
            if node == (app_label, migration_name):
                apps_registry = next_state.apps
                add_constraints = [
                    op for op in migration.operations if isinstance(op, migrations.AddConstraint)
                ]
                assert add_constraints
                for op in add_constraints:
                    model = apps_registry.get_model(app_label, op.model_name)
                    sql = str(op.constraint.create_sql(model, schema_editor))
                    _assert_filtered_unique_index_sql_is_mssql_safe(sql)
            state = next_state


def test_service_model_mssql_has_no_expression_index_warning(monkeypatch):
    schema_editor = _offline_mssql_schema_editor(monkeypatch)
    warnings = [w for w in Service.check() if w.id == 'models.W044']
    assert warnings == []
    for constraint in Service._meta.constraints:
        sql = str(constraint.create_sql(Service, schema_editor))
        assert sql


def test_sales_invoice_constraints_compile_on_mssql_without_not(monkeypatch):
    schema_editor = _offline_mssql_schema_editor(monkeypatch)
    constraint_names = [constraint.name for constraint in SalesInvoice._meta.constraints]
    assert 'sales_invoice_draft_must_be_unpaid' in constraint_names

    for constraint in SalesInvoice._meta.constraints:
        sql = str(constraint.create_sql(SalesInvoice, schema_editor))
        assert sql
        if constraint.name == 'sales_invoice_draft_must_be_unpaid':
            assert 'CHECK' in sql.upper()
            assert 'NOT' not in sql.upper()
