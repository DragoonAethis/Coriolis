import csv
import logging

from django.http import HttpResponse
from django.contrib import admin
from django.contrib.admin.views.decorators import staff_member_required
from django.utils.translation import gettext_lazy as _

from events.models import *

# Ensure users go through the allauth workflow when logging into admin.
admin.site.login = staff_member_required(admin.site.login, login_url='/accounts/login')

# No special handling for these two.
admin.site.register(Payment)


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ('email', 'is_staff', 'is_superuser')
    list_filter = ('is_staff', )
    search_fields = ('email', )


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'ticket_code_length')
    list_filter = ('active', )
    search_fields = ('name', )


@admin.register(EventPage)
class EventPageAdmin(admin.ModelAdmin):
    list_display = ('name', 'event', 'slug', 'hidden')
    list_filter = ('event__name', 'hidden')
    search_fields = ('name', 'slug')


@admin.register(TicketRenderer)
class TicketRendererAdmin(admin.ModelAdmin):
    list_display = ('name', )
    search_fields = ('name', )


@admin.register(NotificationChannel)
class NotificationChannelAdmin(admin.ModelAdmin):
    list_display = ('name', 'event', 'enabled', 'source', 'target')
    list_filter = ('event__name', 'source', 'target')
    search_fields = ('name', )


@admin.register(TicketType)
class TicketTypeAdmin(admin.ModelAdmin):
    list_display = ('name', 'event', 'code_prefix', 'price', 'max_tickets', 'tickets_remaining')
    list_filter = ('event__name', 'self_registration')
    search_fields = ('name', )


@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'event', 'status', 'email', 'nickname')
    list_filter = ('event__name', 'type__name', 'status')
    search_fields = ('code', 'name', 'email', 'phone', 'nickname')


@admin.register(ApplicationType)
class ApplicationTypeAdmin(admin.ModelAdmin):
    list_display = ('name', 'event', 'slug', 'registration_from', 'registration_to')
    list_filter = ('event__name', )
    search_fields = ('name', )


@admin.register(Application)
class ApplicationAdmin(admin.ModelAdmin):
    list_display = ('name', 'type', 'status', 'event', 'phone', 'email')
    list_filter = ('event__name', 'type__name', 'status')
    search_fields = ('name', 'email', 'phone')
    actions = ('download_as_csv', )

    @admin.action(description=_("Download selected applications as CSV"))
    def download_as_csv(self, request, queryset):
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="export.csv"'

        writer = csv.writer(response)
        writer.writerow((
            'id', 'user', 'event', 'type', 'status',
            'name', 'phone', 'email',
            'application',
            'org_notes'
        ))

        app: Application
        for app in queryset:
            try:
                writer.writerow((
                    app.id,
                    app.user.email,
                    app.event.name,
                    app.type.name,
                    app.get_status_display(),
                    app.name,
                    app.phone,
                    app.email,
                    app.application,
                    app.org_notes
                ))
            except Exception as ex:
                writer.writerow(f"Exception: {ex}")
                logging.exception("Could not properly generate the application CSV export file")

        return response
