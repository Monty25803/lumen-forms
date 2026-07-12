from django.core.management.base import BaseCommand

from surveys.models import Form
from surveys.notify import retry_unsynced_responses


class Command(BaseCommand):
    help = 'Retry Google Sheet sync for unsynced responses.'

    def add_arguments(self, parser):
        parser.add_argument('--form-id', type=int, help='Limit to one form primary key.')

    def handle(self, *args, **options):
        forms = Form.objects.exclude(google_sheet_id='')
        if options.get('form_id'):
            forms = forms.filter(pk=options['form_id'])
        total_synced = 0
        total_failed = 0
        for form in forms:
            synced, failed = retry_unsynced_responses(form)
            total_synced += synced
            total_failed += failed
            if synced or failed:
                self.stdout.write(f'{form.title}: synced={synced} failed={failed}')
        self.stdout.write(self.style.SUCCESS(
            f'Done. synced={total_synced} failed={total_failed}'
        ))
