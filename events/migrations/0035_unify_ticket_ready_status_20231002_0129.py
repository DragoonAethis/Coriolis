# Generated by Django 4.2.5 on 2023-10-02 01:29

from django.db import migrations


def ticket_unify_ready(apps, schema_editor):
    for row in apps.get_model("events", "Ticket").objects.all():
        if row.status == "OKPD":
            row.paid = True
            row.status = "OKNP"
            row.save(update_fields=["paid", "status"])


class Migration(migrations.Migration):
    dependencies = [
        ("events", "0034_alter_ticket_price_currency_alter_tickettype_color_and_more"),
    ]

    operations = [migrations.RunPython(ticket_unify_ready, reverse_code=migrations.RunPython.noop)]
