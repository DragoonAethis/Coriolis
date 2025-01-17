# Generated by Django 4.2.15 on 2024-09-15 22:05

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("events", "0061_alter_ticket_contributed_value_currency_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="application",
            name="status",
            field=models.CharField(
                choices=[
                    ("CNCL", "Cancelled"),
                    ("WAIT", "Waiting for Organizers"),
                    ("RSVE", "On Reserve List"),
                    ("APRV", "Accepted"),
                    ("REJD", "Rejected"),
                ],
                default="WAIT",
                max_length=4,
                verbose_name="status",
            ),
        ),
    ]
