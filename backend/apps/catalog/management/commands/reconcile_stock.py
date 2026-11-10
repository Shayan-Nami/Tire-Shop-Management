from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Sum, Value
from django.db.models.functions import Coalesce
from rest_framework.exceptions import ValidationError

from apps.catalog.models import Tire
from apps.catalog.services import repair_stock_projection_service


class Command(BaseCommand):
    help = 'Check stock against the ledger; explicitly repair projections only after verifying ledger truth.'

    def add_arguments(self, parser):
        parser.add_argument('--repair', action='store_true', help='Rebuild stock projections from the ledger.')
        parser.add_argument('--tire-id', type=int, action='append', dest='tire_ids', help='Limit to these tires; repeatable.')
        parser.add_argument('--reason', help='Required audit reason for repair.')
        parser.add_argument('--user', help='Username of the active manager authorizing repair.')

    @transaction.atomic
    def handle(self, *args, **options):
        repair_mode = options['repair']
        user = None
        if repair_mode:
            if not (options.get('reason') or '').strip() or not options.get('user'):
                raise CommandError('--repair requires --reason and --user.')
            user = get_user_model().objects.filter(username=options['user'], is_active=True).first()
            if not user or not (user.is_superuser or user.role == 'MANAGER'):
                raise CommandError('--user must identify an active manager.')
        elif options.get('reason') or options.get('user'):
            raise CommandError('--reason and --user require --repair.')

        tires = Tire.objects.order_by('tire_id')
        if options.get('tire_ids'):
            tires = tires.filter(pk__in=options['tire_ids'])
            missing = set(options['tire_ids']) - set(tires.values_list('pk', flat=True))
            if missing:
                raise CommandError(f'Unknown tire IDs: {sorted(missing)}')

        if repair_mode:
            tire_ids = list(tires.select_for_update().values_list('pk', flat=True))
            repaired = 0
            try:
                for tire_id in tire_ids:
                    audit = repair_stock_projection_service(tire_id, options['reason'], user)
                    if audit:
                        repaired += 1
                        self.stdout.write(
                            f'Audit #{audit.pk}: tire {tire_id}, {audit.stock_before} -> {audit.stock_after}'
                        )
            except ValidationError as exc:
                raise CommandError(f'Recovery aborted; all repairs rolled back: {exc}') from exc
            self.stdout.write(self.style.SUCCESS(f'Rebuilt {repaired} stock projections; ledger unchanged.'))
            return

        discrepancies = []
        for tire in tires.annotate(total_movements=Coalesce(Sum('stock_movements__quantity'), Value(0))):
            if tire.stock_quantity != tire.total_movements:
                discrepancies.append(tire)
                self.stdout.write(self.style.WARNING(
                    f'Tire {tire.pk}: stock={tire.stock_quantity}, ledger={tire.total_movements}, '
                    f'difference={tire.stock_quantity - tire.total_movements}'
                ))
        if discrepancies:
            self.stdout.write(
                'Investigate the ledger first. If it is authoritative, run reconcile_stock '
                '--repair --tire-id ID --reason "investigation reference" --user MANAGER. '
                'Physical stocktaking (adjust-stock) is separate and does not repair ledger discrepancies.'
            )
            raise CommandError(f'{len(discrepancies)} مغایرت موجودی یافت شد')
        self.stdout.write(self.style.SUCCESS(f'Stock matches the ledger for {tires.count()} tires.'))
