import uuid
from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone

User = get_user_model()


class Department(models.Model):
    """Support departments (e.g., Technical Support, Billing, Sales)."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, default='')
    email = models.EmailField(blank=True, default='support@velohoster.com')
    is_active = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order', 'name']
        verbose_name = 'Support Department'
        verbose_name_plural = 'Support Departments'

    def __str__(self):
        return self.name


class Ticket(models.Model):
    """Customer support ticket."""

    class Priority(models.TextChoices):
        LOW = 'low', 'Low'
        MEDIUM = 'medium', 'Medium'
        HIGH = 'high', 'High'
        URGENT = 'urgent', 'Urgent / Critical'

    class Status(models.TextChoices):
        OPEN = 'open', 'Open'
        ANSWERED = 'answered', 'Staff Replied'
        CUSTOMER_REPLY = 'customer_reply', 'Customer Reply'
        IN_PROGRESS = 'in_progress', 'In Progress'
        CLOSED = 'closed', 'Closed'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    ticket_number = models.CharField(
        max_length=25, unique=True, db_index=True,
        help_text='Unique formatted ticket code, e.g. #TICK-87124'
    )
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='support_tickets', db_index=True
    )
    department = models.ForeignKey(
        Department, on_delete=models.SET_NULL, null=True, blank=True, related_name='tickets'
    )
    subject = models.CharField(max_length=255)
    priority = models.CharField(
        max_length=15, choices=Priority.choices, default=Priority.MEDIUM, db_index=True
    )
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.OPEN, db_index=True
    )

    # Optional linkage to client services
    hosting_account = models.ForeignKey(
        'hosting.HostingAccount', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='support_tickets'
    )
    domain = models.ForeignKey(
        'domains.Domain', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='support_tickets'
    )

    last_reply_at = models.DateTimeField(default=timezone.now, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-last_reply_at']
        verbose_name = 'Support Ticket'
        verbose_name_plural = 'Support Tickets'

    def __str__(self):
        return f"{self.ticket_number} - {self.subject} ({self.get_status_display()})"

    @classmethod
    def generate_ticket_number(cls):
        import secrets
        num = secrets.randbelow(900000) + 100000
        return f"TICK-{num}"


class TicketMessage(models.Model):
    """Conversation messages in a support ticket."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    ticket = models.ForeignKey(
        Ticket, on_delete=models.CASCADE, related_name='messages'
    )
    user = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True
    )
    is_staff = models.BooleanField(default=False)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']
        verbose_name = 'Ticket Message'
        verbose_name_plural = 'Ticket Messages'

    def __str__(self):
        author = "Staff" if self.is_staff else (self.user.email if self.user else "User")
        return f"{author} on {self.ticket.ticket_number} at {self.created_at}"


class TicketAttachment(models.Model):
    """Files/screenshots attached to a ticket message."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    message = models.ForeignKey(
        TicketMessage, on_delete=models.CASCADE, related_name='attachments'
    )
    file = models.FileField(upload_to='ticket_attachments/%Y/%m/')
    filename = models.CharField(max_length=255)
    file_size = models.PositiveIntegerField(default=0, help_text='File size in bytes')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.filename
