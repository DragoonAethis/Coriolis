from django.contrib import admin
from django.contrib.admin.views.decorators import staff_member_required
from .models import User, Event, EventPage, TicketType, ApplicationType, Ticket, Payment, Application

# Ensure users go through the allauth workflow when logging into admin.
admin.site.login = staff_member_required(admin.site.login, login_url='/accounts/login')

# No special handling for these two.
admin.site.register(User)
admin.site.register(Payment)


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
