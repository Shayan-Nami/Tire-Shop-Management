from __future__ import annotations

from typing import TYPE_CHECKING, Any

from django.core.exceptions import FieldError
from django.db.models import DecimalField, FloatField, Func, IntegerField, Value
from django.db.models.functions import Cast, NullIf

if TYPE_CHECKING:
    from django.db.backends.base.base import BaseDatabaseWrapper
    from django.db.models.sql.compiler import SQLCompiler, _AsSqlType


class DecimalDivision(Func):
    arity = 2
    arg_joiner = ' / '
    template = '(%(expressions)s)'
    output_field = DecimalField(max_digits=28, decimal_places=12)

    def __init__(self, numerator: Any, denominator: Any, **extra: Any) -> None:
        safe_denominator = (
            denominator
            if isinstance(denominator, NullIf)
            else NullIf(denominator, Value(0))
        )
        super().__init__(numerator, safe_denominator, **extra)

    def as_sqlite(
        self,
        compiler: SQLCompiler,
        connection: BaseDatabaseWrapper,
        **extra_context: Any,
    ) -> _AsSqlType:
        numerator, denominator = self.get_source_expressions()
        clone = self.copy()
        clone.set_source_expressions([
            Cast(numerator, FloatField()),
            Cast(denominator, FloatField()),
        ])
        return clone.as_sql(compiler, connection, **extra_context)

    def as_sql(
        self,
        compiler: SQLCompiler,
        connection: BaseDatabaseWrapper,
        function: str | None = None,
        template: str | None = None,
        arg_joiner: str | None = None,
        **extra_context: Any,
    ) -> _AsSqlType:
        if connection.vendor != 'sqlite':
            numerator, denominator = self.get_source_expressions()
            try:
                num_field = numerator.output_field
            except (AttributeError, FieldError):
                num_field = None
            if isinstance(num_field, IntegerField):
                clone = self.copy()
                clone.set_source_expressions([
                    Cast(numerator, DecimalField(max_digits=28, decimal_places=12)),
                    denominator,
                ])
                return super(DecimalDivision, clone).as_sql(
                    compiler,
                    connection,
                    function=function,
                    template=template,
                    arg_joiner=arg_joiner,
                    **extra_context,
                )
        return super().as_sql(
            compiler,
            connection,
            function=function,
            template=template,
            arg_joiner=arg_joiner,
            **extra_context,
        )
