# Generated by Django 4.1.3 on 2022-11-27 21:46

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("events", "0021_application_answers_application_notes_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="application",
            name="application",
            field=models.TextField(
                blank=True,
                help_text="Legacy application answers field.",
                verbose_name="application",
            ),
        ),
    ]