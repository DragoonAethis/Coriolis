# Generated by Django 3.2.12 on 2022-02-20 00:31

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('events', '0007_applicationtype_org_email'),
    ]

    operations = [
        migrations.CreateModel(
            name='NotificationChannel',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(help_text='A custom label for this channel - not used anywhere.', max_length=256, verbose_name='name')),
                ('enabled', models.BooleanField(default=True, help_text='Enable or disable this channel.', verbose_name='enabled')),
                ('source', models.CharField(choices=[('ticket-used', 'Ticket Used')], help_text='Which events to send to this channel?', max_length=32, verbose_name='source')),
                ('target', models.CharField(choices=[('discord-webhook', 'Discord Webhook')], help_text='Where to send events from this channel?', max_length=16, verbose_name='target')),
                ('configuration', models.JSONField(help_text='Shown in the ticket choice screen. Supports Markdown. See docs: https://github.com/DragoonAethis/Coriolis/wiki/Notification-Channels', verbose_name='configuration')),
                ('event', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='events.event', verbose_name='event')),
            ],
            options={
                'verbose_name': 'notification channel',
                'verbose_name_plural': 'notification channels',
            },
        ),
    ]
