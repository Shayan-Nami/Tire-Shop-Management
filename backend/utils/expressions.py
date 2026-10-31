from django.db.models import DecimalField, FloatField, Func
from django.db.models.functions import Cast


class DecimalDivision(Func):
    """Preserve fractional division when SQLite stores decimals as integers."""

    arity = 2
    arg_joiner = ' / '
    template = '(%(expressions)s)'
    output_field = DecimalField(max_digits=28, decimal_places=12)

    def as_sqlite(self, compiler, connection, **extra_context):
        # A NUMERIC cast still permits integer division; REAL is required on SQLite.
        numerator, denominator = self.get_source_expressions()
        clone = self.copy()
        clone.set_source_expressions([Cast(numerator, FloatField()), denominator])
        return clone.as_sql(compiler, connection, **extra_context)
