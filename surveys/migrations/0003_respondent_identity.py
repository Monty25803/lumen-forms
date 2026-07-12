from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('surveys', '0002_form_google_sheet_id_form_google_sheet_url_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='response',
            name='respondent_email',
            field=models.EmailField(default='unknown@example.com', max_length=254),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='response',
            name='respondent_name',
            field=models.CharField(default='Unknown', max_length=200),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='response',
            name='respondent_user',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='form_responses',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
