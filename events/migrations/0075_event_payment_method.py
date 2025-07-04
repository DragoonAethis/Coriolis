# Generated by Django 4.2.21 on 2025-05-31 23:40

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("events", "0074_ticket_payment_method"),
    ]

    operations = [
        migrations.AddField(
            model_name="event",
            name="payment_method",
            field=models.CharField(
                blank=True,
                help_text="Payment method to use for this event. If empty, the global default is used instead.",
                verbose_name="payment method",
            ),
        ),
    ]
