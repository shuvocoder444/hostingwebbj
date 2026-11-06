from django.contrib import admin
from .models import Department, Ticket, TicketMessage, TicketAttachment


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ('name', 'email', 'order', 'is_active')
    list_editable = ('order', 'is_active')


class TicketMessageInline(admin.StackedInline):
    model = TicketMessage
    extra = 0
    readonly_fields = ('created_at',)


@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = ('ticket_number', 'subject', 'user', 'department', 'priority', 'status', 'last_reply_at', 'created_at')
    list_filter = ('status', 'priority', 'department')
    search_fields = ('ticket_number', 'subject', 'user__email', 'user__first_name')
    readonly_fields = ('ticket_number', 'created_at', 'updated_at', 'last_reply_at')
    inlines = [TicketMessageInline]


@admin.register(TicketMessage)
class TicketMessageAdmin(admin.ModelAdmin):
    list_display = ('ticket', 'user', 'is_staff', 'created_at')
    list_filter = ('is_staff',)
    search_fields = ('ticket__ticket_number', 'user__email', 'message')


@admin.register(TicketAttachment)
class TicketAttachmentAdmin(admin.ModelAdmin):
    list_display = ('filename', 'message', 'file_size', 'created_at')
