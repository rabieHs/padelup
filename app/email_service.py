from django.conf import settings
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Email, To, Content


def send_booking_confirmation(user, booking):
    """Send booking confirmation email via SendGrid"""
    if not settings.SENDGRID_API_KEY:
        print('SendGrid API key not configured, skipping email')
        return False

    court_name = booking.court.name
    club_name = booking.court.club.name
    date = booking.date.strftime('%A, %B %d, %Y')
    start_time = booking.start_time.strftime('%H:%M')
    end_time = booking.end_time.strftime('%H:%M')

    subject = f'Booking Confirmed - {club_name}'
    html_content = f"""
    <div style="font-family: 'Inter', Arial, sans-serif; max-width: 600px; margin: 0 auto; background: #f8fafc; padding: 24px;">
        <div style="background: #094A73; color: white; padding: 24px; border-radius: 16px 16px 0 0; text-align: center;">
            <h1 style="margin: 0; font-size: 24px;">PadelUp</h1>
            <p style="margin: 8px 0 0; opacity: 0.9;">Booking Confirmation</p>
        </div>
        <div style="background: white; padding: 24px; border-radius: 0 0 16px 16px;">
            <p>Hi <strong>{user.first_name or user.username}</strong>,</p>
            <p>Your court booking has been confirmed!</p>
            <div style="background: #f0fdf4; border: 1px solid #10B981; border-radius: 12px; padding: 16px; margin: 16px 0;">
                <h3 style="margin: 0 0 12px; color: #094A73;">{club_name}</h3>
                <p style="margin: 4px 0;"><strong>Court:</strong> {court_name}</p>
                <p style="margin: 4px 0;"><strong>Date:</strong> {date}</p>
                <p style="margin: 4px 0;"><strong>Time:</strong> {start_time} - {end_time}</p>
                <p style="margin: 4px 0;"><strong>Duration:</strong> {booking.duration} min</p>
                <p style="margin: 4px 0;"><strong>Total:</strong> {booking.total_amount} {booking.currency}</p>
            </div>
            <p style="color: #6b7280; font-size: 14px;">See you on the court!</p>
        </div>
    </div>
    """

    return _send_email(user.email, subject, html_content)


def send_match_join_confirmation(user, match):
    """Send match join confirmation email via SendGrid"""
    if not settings.SENDGRID_API_KEY:
        print('SendGrid API key not configured, skipping email')
        return False

    date = match.date.strftime('%A, %B %d, %Y')
    time = match.time.strftime('%H:%M')
    match_type = match.match_type.capitalize()

    subject = f'Match Joined - {match.title}'
    html_content = f"""
    <div style="font-family: 'Inter', Arial, sans-serif; max-width: 600px; margin: 0 auto; background: #f8fafc; padding: 24px;">
        <div style="background: #094A73; color: white; padding: 24px; border-radius: 16px 16px 0 0; text-align: center;">
            <h1 style="margin: 0; font-size: 24px;">PadelUp</h1>
            <p style="margin: 8px 0 0; opacity: 0.9;">Match Confirmation</p>
        </div>
        <div style="background: white; padding: 24px; border-radius: 0 0 16px 16px;">
            <p>Hi <strong>{user.first_name or user.username}</strong>,</p>
            <p>You have successfully joined a match!</p>
            <div style="background: #eff6ff; border: 1px solid #3b82f6; border-radius: 12px; padding: 16px; margin: 16px 0;">
                <h3 style="margin: 0 0 12px; color: #094A73;">{match.title}</h3>
                <p style="margin: 4px 0;"><strong>Type:</strong> {match_type}</p>
                <p style="margin: 4px 0;"><strong>Date:</strong> {date}</p>
                <p style="margin: 4px 0;"><strong>Time:</strong> {time}</p>
                <p style="margin: 4px 0;"><strong>Organizer:</strong> {match.organizer.username}</p>
                <p style="margin: 4px 0;"><strong>Players:</strong> {match.get_accepted_participants_count()}/{match.max_players}</p>
            </div>
            <p style="color: #6b7280; font-size: 14px;">Good luck and have fun!</p>
        </div>
    </div>
    """

    return _send_email(user.email, subject, html_content)


def send_welcome_email(user):
    """Send welcome email after registration via SendGrid"""
    if not settings.SENDGRID_API_KEY:
        print('SendGrid API key not configured, skipping welcome email')
        return False

    subject = 'Bienvenue sur PadelUp !'
    html_content = f"""
    <div style="font-family: 'Inter', Arial, sans-serif; max-width: 600px; margin: 0 auto; background: #f8fafc; padding: 24px;">
        <div style="background: #094A73; color: white; padding: 24px; border-radius: 16px 16px 0 0; text-align: center;">
            <h1 style="margin: 0; font-size: 24px;">PadelUp</h1>
            <p style="margin: 8px 0 0; opacity: 0.9;">Bienvenue dans la communauté !</p>
        </div>
        <div style="background: white; padding: 24px; border-radius: 0 0 16px 16px;">
            <p>Bonjour <strong>{user.first_name or user.username}</strong>,</p>
            <p>Votre compte PadelUp a été créé avec succès ! 🎾</p>
            <div style="background: #f0fdf4; border: 1px solid #10B981; border-radius: 12px; padding: 16px; margin: 16px 0;">
                <h3 style="margin: 0 0 12px; color: #094A73;">Pour commencer</h3>
                <p style="margin: 4px 0;">✅ Complétez votre profil avec votre niveau</p>
                <p style="margin: 4px 0;">✅ Découvrez les clubs près de chez vous</p>
                <p style="margin: 4px 0;">✅ Rejoignez ou créez un match</p>
                <p style="margin: 4px 0;">✅ Ajoutez des amis et jouez ensemble</p>
            </div>
            <p style="color: #6b7280; font-size: 14px;">À bientôt sur les terrains !</p>
            <p style="color: #6b7280; font-size: 14px;">L'équipe PadelUp</p>
        </div>
    </div>
    """

    return _send_email(user.email, subject, html_content)


def send_password_reset_email(user, code):
    """Send password reset code via email"""
    if not settings.SENDGRID_API_KEY:
        print('SendGrid API key not configured, skipping password reset email')
        return False

    subject = 'PadelUp - Code de réinitialisation'
    html_content = f"""
    <div style="font-family: 'Inter', Arial, sans-serif; max-width: 600px; margin: 0 auto; background: #f8fafc; padding: 24px;">
        <div style="background: #094A73; color: white; padding: 24px; border-radius: 16px 16px 0 0; text-align: center;">
            <h1 style="margin: 0; font-size: 24px;">PadelUp</h1>
            <p style="margin: 8px 0 0; opacity: 0.9;">Réinitialisation du mot de passe</p>
        </div>
        <div style="background: white; padding: 24px; border-radius: 0 0 16px 16px;">
            <p>Bonjour <strong>{user.first_name or user.username}</strong>,</p>
            <p>Vous avez demandé la réinitialisation de votre mot de passe. Voici votre code de vérification :</p>
            <div style="background: #eff6ff; border: 1px solid #3b82f6; border-radius: 12px; padding: 24px; margin: 16px 0; text-align: center;">
                <p style="font-size: 32px; font-weight: bold; letter-spacing: 8px; color: #094A73; margin: 0;">{code}</p>
            </div>
            <p style="color: #6b7280; font-size: 14px;">Ce code est valable pendant <strong>15 minutes</strong>.</p>
            <p style="color: #6b7280; font-size: 14px;">Si vous n'avez pas demandé cette réinitialisation, ignorez cet email.</p>
        </div>
    </div>
    """

    return _send_email(user.email, subject, html_content)


def _send_email(to_email, subject, html_content):
    """Send an email using SendGrid API"""
    try:
        message = Mail(
            from_email=Email(settings.DEFAULT_FROM_EMAIL),
            to_emails=To(to_email),
            subject=subject,
            html_content=Content('text/html', html_content),
        )
        sg = SendGridAPIClient(settings.SENDGRID_API_KEY)
        response = sg.send(message)
        print(f'Email sent to {to_email}, status: {response.status_code}')
        return response.status_code in [200, 201, 202]
    except Exception as e:
        print(f'Failed to send email to {to_email}: {e}')
        return False
