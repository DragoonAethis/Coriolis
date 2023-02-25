# Generated by Django 4.1.6 on 2023-02-08 19:50

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("events", "0028_user_exempt_from_2fa"),
    ]

    operations = [
        migrations.AddField(
            model_name="tickettype",
            name="can_personalize",
            field=models.BooleanField(
                default=True,
                help_text="Determines if a ticket can be personalized at all.",
                verbose_name="can personalize",
            ),
        ),
    ]