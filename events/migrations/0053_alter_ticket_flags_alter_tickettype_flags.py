# Generated by Django 4.2.9 on 2024-01-22 17:38

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("events", "0052_ticket_flags"),
    ]

    operations = [
        migrations.AlterField(
            model_name="ticket",
            name="flags",
            field=models.ManyToManyField(
                blank=True,
                help_text="Flags specific to this ticket added on top of the type flags.",
                to="events.ticketflag",
                verbose_name="flags",
            ),
        ),
        migrations.AlterField(
            model_name="tickettype",
            name="flags",
            field=models.ManyToManyField(
                blank=True,
                help_text="Flags to apply on all tickets of this type.",
                to="events.ticketflag",
                verbose_name="flags",
            ),
        ),
    ]
