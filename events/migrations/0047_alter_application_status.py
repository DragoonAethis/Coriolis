# Generated by Django 4.2.6 on 2023-10-25 23:43

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("events", "0046_remove_application_application_and_more"),
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
                    ("APRV", "Approved"),
                    ("REJD", "Rejected"),
                ],
                default="WAIT",
                max_length=4,
                verbose_name="status",
            ),
        ),
    ]
