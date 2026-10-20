"""
OTP (One-Time Password) Service
===============================
Provides email OTP generation, verification, and rate-limiting.
Used for:
  - User Registration Verification
  - Password Reset
  - Cart Checkout Email Verification
"""
import logging
import os
import secrets
import subprocess
from datetime import timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from django.conf import settings
from django.core.mail import EmailMultiAlternatives, get_connection
from django.utils import timezone

from accounts.models import EmailOTP
from core.models import SiteSetting

logger = logging.getLogger(__name__)


class OTPService:
    """Enterprise OTP Service with SMTP and sendmail fallback."""

    OTP_EXPIRY_MINUTES = 10
    RESEND_COOLDOWN_SECONDS = 60
    MAX_ATTEMPTS = 5

    @classmethod
    def get_client_ip(cls, request):
        """Extract client IP from request headers."""
        if not request:
            return None
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR')

    @classmethod
    def generate_and_send_otp(cls, email: str, first_name: str = None, purpose: str = EmailOTP.Purpose.REGISTRATION, request = None) -> tuple[bool, str]:
        """
        Generates a 6-digit OTP and sends it via email.
        Enforces a 60-second cooldown between requests.
        """
        email = email.strip().lower()
        if not email or '@' not in email:
            return False, "Please enter a valid email address."

        # Check for recent active OTP (cooldown check)
        recent_otp = EmailOTP.objects.filter(
            email=email,
            purpose=purpose,
            is_used=False,
            created_at__gte=timezone.now() - timedelta(seconds=cls.RESEND_COOLDOWN_SECONDS)
        ).first()

        if recent_otp:
            time_left = cls.RESEND_COOLDOWN_SECONDS - int((timezone.now() - recent_otp.created_at).total_seconds())
            if time_left < 1:
                time_left = 1
            return False, f"Please wait {time_left} seconds before requesting a new verification code."

        # Invalidate any older unused OTPs for this email and purpose
        EmailOTP.objects.filter(email=email, purpose=purpose, is_used=False).update(is_used=True)

        # Generate a cryptographically secure 6-digit numeric OTP
        otp_code = f"{secrets.randbelow(900000) + 100000}"
        expires_at = timezone.now() + timedelta(minutes=cls.OTP_EXPIRY_MINUTES)

        ip = cls.get_client_ip(request)

        # Create record in database
        EmailOTP.objects.create(
            email=email,
            otp_code=otp_code,
            purpose=purpose,
            expires_at=expires_at,
            ip_address=ip,
        )

        # Send Email
        success, err = cls.send_otp_email(
            to_email=email,
            otp_code=otp_code,
            first_name=first_name,
            purpose=purpose
        )

        if not success:
            logger.error("Failed to deliver OTP to %s: %s", email, err)
            return False, "Could not send verification email. Please check your email address or try again."

        return True, "A 6-digit verification code has been sent to your email."

    @classmethod
    def verify_otp(cls, email: str, otp_code: str, purpose: str = EmailOTP.Purpose.REGISTRATION) -> tuple[bool, str]:
        """
        Validates the 6-digit OTP code for a given email and purpose.
        Enforces expiration and maximum failed attempts.
        """
        email = email.strip().lower()
        otp_code = str(otp_code or '').strip()

        if not otp_code or len(otp_code) != 6 or not otp_code.isdigit():
            return False, "Please enter a valid 6-digit verification code."

        otp = EmailOTP.objects.filter(
            email=email,
            purpose=purpose,
            is_used=False
        ).order_by('-created_at').first()

        if not otp:
            return False, "No active verification code found for this email. Please request a new code."

        # Check expiration
        if timezone.now() > otp.expires_at:
            otp.is_used = True
            otp.save(update_fields=['is_used'])
            return False, "Your verification code has expired (valid for 10 minutes). Please request a new code."

        # Check maximum attempts
        if otp.attempts >= cls.MAX_ATTEMPTS:
            otp.is_used = True
            otp.save(update_fields=['is_used'])
            return False, "Too many incorrect attempts. For security, this code is now expired. Please request a new one."

        # Validate code match
        if otp.otp_code != otp_code:
            otp.attempts += 1
            otp.save(update_fields=['attempts'])
            remaining = cls.MAX_ATTEMPTS - otp.attempts
            if remaining > 0:
                return False, f"Incorrect verification code. You have {remaining} attempt(s) remaining."
            else:
                otp.is_used = True
                otp.save(update_fields=['is_used'])
                return False, "Too many incorrect attempts. This code is now invalid. Please request a new one."

        # Success - mark used
        otp.is_used = True
        otp.save(update_fields=['is_used'])
        return True, "Email verified successfully."

    @classmethod
    def send_otp_email(cls, to_email: str, otp_code: str, first_name: str = None, purpose: str = EmailOTP.Purpose.REGISTRATION) -> tuple[bool, str]:
        """
        Constructs and delivers a responsive, branded HTML email containing the OTP code.
        """
        site = SiteSetting.get_settings()
        company_name = getattr(site, 'company_name', None) or 'VeloHoster'
        greeting = f"Hello {first_name}," if first_name else "Hello,"

        purpose_label = "Account Registration"
        if purpose == EmailOTP.Purpose.PASSWORD_RESET:
            purpose_label = "Password Reset"
        elif purpose == EmailOTP.Purpose.CHECKOUT:
            purpose_label = "Order Checkout Verification"

        subject = f"{otp_code} is your {company_name} verification code"

        # Plain-text alternative
        text_body = f"""{greeting}

Your 6-digit verification code for {company_name} {purpose_label} is:

    {otp_code}

This code will expire in {cls.OTP_EXPIRY_MINUTES} minutes.
Do NOT share this code with anyone. Our support team will never ask for your code.

If you did not request this verification code, please ignore this email.

Best regards,
The {company_name} Team
https://velohoster.com
"""

        # High-end, responsive HTML Email Template
        html_body = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{subject}</title>
<style>
  body {{ margin: 0; padding: 0; background-color: #f1f5f9; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; }}
  table {{ border-collapse: collapse; }}
</style>
</head>
<body style="margin: 0; padding: 30px 15px; background-color: #f1f5f9; color: #1e293b;">
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" align="center">
    <tr>
      <td align="center">
        <!-- Main Card Container -->
        <table role="presentation" width="100%" style="max-width: 560px; background-color: #ffffff; border-radius: 20px; overflow: hidden; box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.05), 0 8px 10px -6px rgba(0, 0, 0, 0.03); border: 1px solid #e2e8f0;">
          
          <!-- Header Banner -->
          <tr>
            <td style="background: linear-gradient(135deg, #0f172a 0%, #1e3a8a 100%); padding: 35px 30px; text-align: center;">
              <table role="presentation" width="100%">
                <tr>
                  <td align="center">
                    <span style="font-size: 26px; font-weight: 900; letter-spacing: -0.5px; color: #ffffff; text-transform: uppercase;">
                      VELO<span style="color: #38bdf8;">HOSTER</span>
                    </span>
                    <div style="margin-top: 6px; font-size: 11px; font-weight: 700; color: #93c5fd; letter-spacing: 1.5px; text-transform: uppercase;">
                      High-Performance Cloud Web Hosting
                    </div>
                  </td>
                </tr>
              </table>
            </td>
          </tr>

          <!-- Body Content -->
          <tr>
            <td style="padding: 40px 35px 30px 35px;">
              <div style="font-size: 18px; font-weight: 700; color: #0f172a; margin-bottom: 12px;">
                {greeting}
              </div>
              <p style="font-size: 14px; line-height: 1.6; color: #475569; margin: 0 0 24px 0;">
                Thank you for choosing <strong>{company_name}</strong>. To complete your {purpose_label.lower()} and verify your email address, please use the following 6-digit one-time verification code:
              </p>

              <!-- OTP Highlight Box -->
              <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="margin: 25px 0 30px 0;">
                <tr>
                  <td align="center" style="background: #eff6ff; border: 2px dashed #3b82f6; border-radius: 16px; padding: 24px 20px;">
                    <span style="display: block; font-size: 11px; font-weight: 800; color: #1d4ed8; text-transform: uppercase; letter-spacing: 2px; margin-bottom: 8px;">
                      Verification Code
                    </span>
                    <span style="font-family: 'SF Pro Display', Consolas, Menlo, Monaco, monospace; font-size: 38px; font-weight: 900; letter-spacing: 10px; color: #1e40af; display: inline-block;">
                      {otp_code}
                    </span>
                    <span style="display: block; font-size: 12px; font-weight: 600; color: #64748b; margin-top: 10px;">
                      ⏱️ Valid for <strong>{cls.OTP_EXPIRY_MINUTES} minutes</strong>
                    </span>
                  </td>
                </tr>
              </table>

              <!-- Security Notice -->
              <div style="background-color: #fef2f2; border-left: 4px solid #ef4444; border-radius: 8px; padding: 12px 16px; margin-bottom: 24px;">
                <p style="margin: 0; font-size: 12px; line-height: 1.5; color: #991b1b;">
                  <strong>Security Reminder:</strong> Never share this code with anyone. VeloHoster staff will never ask for your verification code or account password.
                </p>
              </div>

              <p style="font-size: 12px; line-height: 1.5; color: #94a3b8; margin: 0;">
                If you did not request this verification code, please ignore this email or contact our 24/7 security team.
              </p>
            </td>
          </tr>

          <!-- Footer -->
          <tr>
            <td style="background-color: #f8fafc; border-top: 1px solid #e2e8f0; padding: 24px 35px; text-align: center;">
              <p style="margin: 0 0 8px 0; font-size: 12px; color: #64748b;">
                Need help? <a href="https://velohoster.com/contact-us/" style="color: #2563eb; text-decoration: none; font-weight: 600;">Contact 24/7 Support</a> • <a href="https://velohoster.com" style="color: #2563eb; text-decoration: none; font-weight: 600;">velohoster.com</a>
              </p>
              <p style="margin: 0; font-size: 11px; color: #94a3b8;">
                © 2026 {company_name}. All rights reserved.
              </p>
            </td>
          </tr>

        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""

        # Determine Sender Email
        from_email = getattr(site, 'smtp_from_email', None) or getattr(settings, 'DEFAULT_FROM_EMAIL', None) or f'{company_name} <noreply@velohoster.com>'

        # Determine Connection (Custom SMTP or Django default)
        conn = None
        if getattr(site, 'smtp_host', None):
            try:
                conn = get_connection(
                    backend='django.core.mail.backends.smtp.EmailBackend',
                    host=site.smtp_host,
                    port=site.smtp_port or 587,
                    username=site.smtp_user or None,
                    password=site.smtp_password or None,
                    use_tls=site.smtp_use_tls,
                    use_ssl=site.smtp_use_ssl,
                    timeout=15,
                )
            except Exception as e:
                logger.warning("Failed to initialize custom SMTP connection: %s", e)
                conn = None

        # Attempt 1: Standard Django EmailMultiAlternatives
        try:
            msg = EmailMultiAlternatives(
                subject=subject,
                body=text_body,
                from_email=from_email,
                to=[to_email],
                connection=conn,
            )
            msg.attach_alternative(html_body, "text/html")
            msg.send(fail_silently=False)
            logger.info("OTP email successfully delivered to %s via Django SMTP", to_email)
            return True, "Email sent successfully."
        except Exception as exc:
            logger.warning("Django SMTP failed for %s (%s). Attempting sendmail fallback...", to_email, exc)

        # Attempt 2: Local /usr/sbin/sendmail binary fallback (Production Linux)
        if os.path.exists('/usr/sbin/sendmail'):
            try:
                raw_msg = MIMEMultipart('alternative')
                raw_msg['Subject'] = subject
                raw_msg['From'] = from_email
                raw_msg['To'] = to_email
                raw_msg.attach(MIMEText(text_body, 'plain', 'utf-8'))
                raw_msg.attach(MIMEText(html_body, 'html', 'utf-8'))

                proc = subprocess.Popen(
                    ['/usr/sbin/sendmail', '-t', '-oi', '-f', 'noreply@velohoster.com'],
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE
                )
                stdout, stderr = proc.communicate(raw_msg.as_bytes())
                if proc.returncode == 0:
                    logger.info("OTP email successfully delivered to %s via /usr/sbin/sendmail", to_email)
                    return True, "Email sent successfully via sendmail."
                else:
                    logger.error("Sendmail returned error code %d: %s", proc.returncode, stderr)
            except Exception as sm_exc:
                logger.error("Sendmail fallback failed: %s", sm_exc)

        # In local development, don't block the user if mail server is offline
        if getattr(settings, 'DEBUG', False):
            logger.warning("DEVELOPMENT MODE: Simulated OTP delivery for %s: Code = %s", to_email, otp_code)
            return True, f"Dev simulated OTP: {otp_code}"

        return False, "Unable to deliver verification email at this moment."
