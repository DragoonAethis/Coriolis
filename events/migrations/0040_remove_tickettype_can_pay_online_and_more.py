# Generated by Django 4.2.5 on 2023-10-02 04:16

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("events", "0039_tickettype_online_payment_policy"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="tickettype",
            name="can_pay_online",
        ),
        migrations.RemoveField(
            model_name="tickettype",
            name="must_pay_online",
        ),
    ]
