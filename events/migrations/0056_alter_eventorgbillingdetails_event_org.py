# Generated by Django 4.2.9 on 2024-01-25 21:12

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("events", "0055_alter_eventorgbillingdetails_event"),
    ]

    operations = [
        migrations.AlterField(
            model_name="eventorgbillingdetails",
            name="event_org",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="billing_details_set",
                to="events.eventorg",
                verbose_name="event org",
            ),
        ),
    ]