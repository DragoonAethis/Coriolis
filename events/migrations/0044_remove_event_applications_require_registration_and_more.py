# Generated by Django 4.2.6 on 2023-10-06 02:22

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("events", "0043_ticket_status_deadline_and_more"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="event",
            name="applications_require_registration",
        ),
        migrations.AddField(
            model_name="applicationtype",
            name="requires_valid_ticket",
            field=models.BooleanField(
                default=False,
                help_text="If enabled, users must have a valid ticket for the event before sending applications.",
                verbose_name="requires registration",
            ),
        ),
    ]