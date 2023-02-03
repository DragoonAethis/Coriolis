import io
import decimal
import datetime
from pprint import pformat

from django.http import FileResponse
from django.contrib import admin
from django.forms import ModelForm
from django.contrib.admin.views.decorators import staff_member_required
from django.utils.translation import gettext_lazy as _

import xlsxwriter

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
    save_as = True


class TicketAdminForm(ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if self.instance.event_id:
            self.fields['type'].queryset = TicketType.objects.filter(event_id=self.instance.event_id)


@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    form = TicketAdminForm
    readonly_fields = ('created', 'updated')
    list_display = ('__str__', 'event', 'status', 'email', 'nickname', 'created')
    list_filter = ('event__name', 'type__name', 'status')
    search_fields = ('code', 'name', 'email', 'phone', 'nickname')

    def get_fields(self, request, obj=None):
        fields = list(super().get_fields(request, obj))

        if obj is not None:
            # Put the read-only event after the user again:
            fields.insert(fields.index('user') + 1, fields.pop(fields.index('event')))

        return fields

    def get_readonly_fields(self, request, obj=None):
        fields = ['created', 'updated']

        if obj is not None:
            # Prevent ticket reassignment across events:
            fields.append('event')

        return fields


@admin.register(ApplicationType)
class ApplicationTypeAdmin(admin.ModelAdmin):
    list_display = ('name', 'event', 'slug', 'registration_from', 'registration_to')
    list_filter = ('event__name', )
    search_fields = ('name', )


@admin.register(Application)
class ApplicationAdmin(admin.ModelAdmin):
    list_display = ('name', 'type', 'status', 'event', 'phone', 'email', 'created')
    list_filter = ('event__name', 'type__name', 'status')
    search_fields = ('name', 'email', 'phone')
    actions = ('download_as_xlsx', )

    XLSX_SAFE_TYPES = (
        bool, str, int, float,
        decimal.Decimal,
        datetime.date,
        datetime.time,
        datetime.datetime,
        datetime.timedelta,
    )

    @admin.action(description=_("Download selected applications as XLSX"))
    def download_as_xlsx(self, request, queryset):
        buffer = io.BytesIO()
        workbook = xlsxwriter.Workbook(buffer, {
            'in_memory': True,
            'strings_to_urls': False,
        })
        ws = workbook.add_worksheet()

        attr_cols = [
            (_("ID"), lambda a: str(a.id)),
            (_("User"), lambda a: a.user.email),
            (_("Event"), lambda a: a.event.name),
            (_("Type"), lambda a: a.type.name),
            (_("Status"), lambda a: a.get_status_display()),
            (_("Name"), lambda a: a.name),
            (_("Phone"), lambda a: str(a.phone)),
            (_("Email"), lambda a: a.email),
            (_("Notes"), lambda a: a.notes),
            (_("Org Notes"), lambda a: a.org_notes),
        ]

        cur_row = 1  # 0 is for headers
        col_shift = len(attr_cols)
        found_cols = []

        app: Application
        for app in queryset:
            # Common data:
            for col, (label, expr) in enumerate(attr_cols):
                ws.write(cur_row, col, self.xlsx_safe_value(expr(app)))

            # Application data:
            for key, value in app.answers.items():
                try:
                    col = col_shift + found_cols.index(key)
                except ValueError:
                    found_cols.append(key)
                    col = col_shift + len(found_cols) - 1

                try:
                    error = ws.write(cur_row, col, self.xlsx_safe_value(value))
                    if error:
                        ws.write(cur_row, col, f"ERROR: {error}")
                except:  # noqa
                    ws.write(cur_row, col, "UNKNOWN ERROR!")

            cur_row += 1

        # Headers:
        for col, (label, expr) in enumerate(attr_cols):
            ws.write(0, col, str(label))

        for col, label in enumerate(found_cols):
            ws.write(0, col + col_shift, label)

        workbook.close()
        buffer.seek(0)

        return FileResponse(buffer, as_attachment=True, filename="export.xlsx", headers={
            "Content-Type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        })

    @staticmethod
    def xlsx_safe_value(value):
        if type(value) in ApplicationAdmin.XLSX_SAFE_TYPES:
            return value

        return pformat(value)
