# Generated by Django 4.1.4 on 2022-12-09 23:26

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("events", "0023_ticketrenderer_event_ticket_renderer_help_text_and_more"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="tickettype",
            name="preview_box_coords",
        ),
        migrations.RemoveField(
            model_name="tickettype",
            name="preview_image",
        ),
        migrations.AddField(
            model_name="tickettype",
            name="short_name",
            field=models.CharField(
                blank=True,
                help_text="Usually used for ticket rendering.",
                max_length=128,
                verbose_name="short name",
            ),
        ),
    ]
