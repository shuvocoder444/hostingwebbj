import os
import logging
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponseForbidden, Http404, FileResponse
from django.utils import timezone
from django.db.models import Q

from .models import Department, Ticket, TicketMessage, TicketAttachment
from hosting.models import HostingAccount
from domains.models import Domain

logger = logging.getLogger(__name__)


@login_required
def ticket_list_view(request):
    """Client Portal: List user support tickets with status tabs."""
    status_filter = request.GET.get('status', 'all')
    search_q = request.GET.get('q', '').strip()

    qs = Ticket.objects.filter(user=request.user).select_related('department')

    if status_filter == 'open':
        qs = qs.exclude(status=Ticket.Status.CLOSED)
    elif status_filter == 'closed':
        qs = qs.filter(status=Ticket.Status.CLOSED)
    elif status_filter in dict(Ticket.Status.choices):
        qs = qs.filter(status=status_filter)

    if search_q:
        qs = qs.filter(
            Q(ticket_number__icontains=search_q) |
            Q(subject__icontains=search_q)
        )

    all_tickets = list(qs)
    total_count = Ticket.objects.filter(user=request.user).count()
    open_count = Ticket.objects.filter(user=request.user).exclude(status=Ticket.Status.CLOSED).count()
    closed_count = total_count - open_count

    context = {
        'tickets': all_tickets,
        'status_filter': status_filter,
        'search_q': search_q,
        'total_count': total_count,
        'open_count': open_count,
        'closed_count': closed_count,
    }
    return render(request, 'tickets/ticket_list.html', context)


@login_required
def ticket_create_view(request):
    """Client Portal: Open a new support ticket."""
    departments = Department.objects.filter(is_active=True).order_by('order', 'name')
    user_hosting_accounts = HostingAccount.objects.filter(user=request.user).only('id', 'domain', 'username')
    user_domains = Domain.objects.filter(user=request.user).only('id', 'domain_name')

    if request.method == 'POST':
        dept_id = request.POST.get('department_id')
        subject = request.POST.get('subject', '').strip()
        priority = request.POST.get('priority', Ticket.Priority.MEDIUM)
        message_text = request.POST.get('message', '').strip()
        hosting_id = request.POST.get('hosting_id') or None
        domain_id = request.POST.get('domain_id') or None

        if not subject or not message_text:
            messages.error(request, "Please enter both a Subject and Message for your ticket.")
            return render(request, 'tickets/ticket_create.html', {
                'departments': departments,
                'user_hosting_accounts': user_hosting_accounts,
                'user_domains': user_domains,
                'form_data': request.POST,
            })

        department = None
        if dept_id:
            department = Department.objects.filter(id=dept_id, is_active=True).first()

        # Generate unique ticket number
        ticket_number = Ticket.generate_ticket_number()
        while Ticket.objects.filter(ticket_number=ticket_number).exists():
            ticket_number = Ticket.generate_ticket_number()

        ticket = Ticket.objects.create(
            ticket_number=ticket_number,
            user=request.user,
            department=department,
            subject=subject,
            priority=priority if priority in dict(Ticket.Priority.choices) else Ticket.Priority.MEDIUM,
            status=Ticket.Status.OPEN,
            hosting_account_id=hosting_id if hosting_id else None,
            domain_id=domain_id if domain_id else None,
            last_reply_at=timezone.now(),
        )

        # Create first message
        msg = TicketMessage.objects.create(
            ticket=ticket,
            user=request.user,
            is_staff=False,
            message=message_text,
        )

        # Handle file attachments
        files = request.FILES.getlist('attachments')
        for f in files:
            if f.size <= 10 * 1024 * 1024:  # max 10MB per file
                TicketAttachment.objects.create(
                    message=msg,
                    file=f,
                    filename=f.name,
                    file_size=f.size,
                )

        messages.success(request, f"Support ticket #{ticket.ticket_number} created successfully! Our team will respond shortly.")
        return redirect('ticket_detail', ticket_id=ticket.id)

    return render(request, 'tickets/ticket_create.html', {
        'departments': departments,
        'user_hosting_accounts': user_hosting_accounts,
        'user_domains': user_domains,
    })


@login_required
def ticket_detail_view(request, ticket_id):
    """Client Portal: View ticket details and post reply."""
    ticket = get_object_or_404(
        Ticket.objects.select_related('department', 'hosting_account', 'domain', 'user'),
        id=ticket_id
    )

    # Permission check: owner or admin
    if ticket.user != request.user and getattr(request.user, 'role', '') != 'admin' and not request.user.is_staff:
        return HttpResponseForbidden("You do not have permission to view this ticket.")

    if request.method == 'POST':
        action = request.POST.get('action', 'reply')

        if action == 'close':
            ticket.status = Ticket.Status.CLOSED
            ticket.save(update_fields=['status', 'updated_at'])
            messages.info(request, f"Ticket #{ticket.ticket_number} has been closed.")
            return redirect('ticket_detail', ticket_id=ticket.id)

        reply_text = request.POST.get('message', '').strip()
        if not reply_text:
            messages.error(request, "Reply message cannot be empty.")
            return redirect('ticket_detail', ticket_id=ticket.id)

        is_staff_reply = (getattr(request.user, 'role', '') == 'admin' or request.user.is_staff)

        # Post reply
        msg = TicketMessage.objects.create(
            ticket=ticket,
            user=request.user,
            is_staff=is_staff_reply,
            message=reply_text,
        )

        # Update ticket status
        ticket.status = Ticket.Status.ANSWERED if is_staff_reply else Ticket.Status.CUSTOMER_REPLY
        ticket.last_reply_at = timezone.now()
        ticket.save(update_fields=['status', 'last_reply_at', 'updated_at'])

        # Handle attachments
        files = request.FILES.getlist('attachments')
        for f in files:
            if f.size <= 10 * 1024 * 1024:
                TicketAttachment.objects.create(
                    message=msg,
                    file=f,
                    filename=f.name,
                    file_size=f.size,
                )

        messages.success(request, "Your reply has been posted successfully.")
        return redirect('ticket_detail', ticket_id=ticket.id)

    messages_qs = ticket.messages.select_related('user').prefetch_related('attachments').order_by('created_at')

    return render(request, 'tickets/ticket_detail.html', {
        'ticket': ticket,
        'ticket_messages': messages_qs,
    })


@login_required
def ticket_attachment_download_view(request, attachment_id):
    """Download ticket attachment securely."""
    attachment = get_object_or_404(
        TicketAttachment.objects.select_related('message__ticket'),
        id=attachment_id
    )
    ticket = attachment.message.ticket

    # Verify authorization
    if ticket.user != request.user and getattr(request.user, 'role', '') != 'admin' and not request.user.is_staff:
        return HttpResponseForbidden("Access denied.")

    if not attachment.file or not os.path.exists(attachment.file.path):
        raise Http404("Attachment not found.")

    return FileResponse(open(attachment.file.path, 'rb'), as_attachment=True, filename=attachment.filename)
