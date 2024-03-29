# Generated by Django 4.2.9 on 2024-01-25 21:10

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        (
            "events",
            "0054_eventorg_ticket_original_type_eventorgbillingdetails_and_more",
        ),
    ]

    operations = [
        migrations.AlterField(
            model_name="eventorgbillingdetails",
            name="event",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="billing_details_set",
                to="events.event",
                verbose_name="event",
            ),
        ),
    ]
