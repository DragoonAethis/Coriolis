# Generated by Django 4.2.5 on 2023-10-02 03:56

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("events", "0037_ticket_contributed_value_and_more"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="ticket",
            name="vaccination_proof",
        ),
    ]
