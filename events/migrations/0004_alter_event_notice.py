# Generated by Django 3.2.10 on 2022-01-07 01:34

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('events', '0003_auto_20220107_0039'),
    ]

    operations = [
        migrations.AlterField(
            model_name='event',
            name='notice',
            field=models.TextField(blank=True, help_text='Notice to be shown below the event description, if set.', verbose_name='notice'),
        ),
    ]