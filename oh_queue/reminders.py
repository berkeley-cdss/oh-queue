from base64 import b64encode
from inspect import cleandoc

from ics import Calendar, Event
from zoneinfo import ZoneInfo

from common.course_config import get_domain
from common.rpc.mail import send_email
from common.course_config import format_coursecode, get_course
from oh_queue.models import AppointmentSignup


def send_appointment_reminders(signup: AppointmentSignup):
    send_appointment_reminder(signup, True)
    send_appointment_reminder(signup, False)


def send_student_appointment_absent_email(signup: AppointmentSignup):
    appointment = signup.appointment
    start_time = appointment.start_time
    helper = appointment.helper

    user = signup.user
    course = signup.course

    message = f"""Hey {user.short_name},

    You signed up for a {format_coursecode(course)} office hours appointment at {start_time.time()} PT on {start_time.date()} with {helper.name}. 
    It appears that you did not show up for the appointment. If you did actually attend, you can disregard this email (or reply to this email to let us know our system is in error).
    Please make sure you show up for future appointments. Our course staff has limited time and many students want our help. When you don't show up, that takes time away from another student that could benefit from help.
    If we notice that you book another appointment and do not show up, we may prevent you from booking appointments.
    
    Best,
    The 61A Software Team
    """.strip()

    message = cleandoc(message)

    send_email(
        sender="OH Queue <cs61a@berkeley.edu>",
        target=user.email,
        subject=f"{format_coursecode(course)} OH Appointment Absence",
        body=message,
    )


def send_appointment_reminder(signup: AppointmentSignup, is_staff: bool):
    appointment = signup.appointment
    user = signup.user
    helper = appointment.helper

    recipient = helper if is_staff else user

    if not recipient:
        return

    c = Calendar()
    e = Event()
    e.name = f"{format_coursecode(get_course())} Appointment"
    e.begin = appointment.start_time.replace(tzinfo=ZoneInfo("America/Los_Angeles"))
    e.end = e.begin + appointment.duration
    e.location = appointment.location.name
    e.uid = get_uid(signup, is_staff)
    c.events.add(e)

    if is_staff:
        additional_msg = f"""
        Student name: {user.short_name}
        Appointment assignment: {signup.assignment.name}
        Appointment question: {signup.question or 'N/A'}
        Description: {signup.description or 'N/A'}"""
    else:
        additional_msg = (
            f"It will be led by {appointment.helper.name}.\n"
            if appointment.helper
            else ""
        )

    message = f"""
        Hi {recipient.short_name},

        An appointment has been scheduled for you using the {format_coursecode(get_course())} OH Queue. 
        It is at {appointment.start_time.strftime('%A %B %-d, %I:%M%p')} Pacific Time, at location {appointment.location.name}.
        {additional_msg}

        To edit or cancel this appointment, go to https://{get_domain()}.

        Best,
        The 61A Software Team
        """.strip()

    send_email(
        sender="OH Queue <cs61a@berkeley.edu>",
        target=recipient.email,
        subject=f"{format_coursecode(get_course())} Appointment Scheduled",
        body=cleandoc(message),
        attachments={"invite.ics": b64encode(str(c).encode("utf-8")).decode("ascii")},
    )


def send_cancellation_reminders(signup: AppointmentSignup):
    send_cancellation_reminder(signup, True)
    send_cancellation_reminder(signup, False)


def send_cancellation_reminder(signup: AppointmentSignup, is_staff: bool):
    appointment = signup.appointment
    user = signup.user
    helper = appointment.helper

    recipient = helper if is_staff else user

    if not recipient:
        return

    appointment_time = appointment.start_time.strftime("%A %B %-d, %I:%M%p")

    pretty_course_name = format_coursecode(get_course())

    if is_staff:
        message = f"Your appointment at {appointment_time} Pacific Time for {pretty_course_name} has been cancelled by the student."
    else:
        message = f"This is a reminder that you have cancelled your appointment with {helper.short_name if helper else 'staff'} at {appointment_time} for {pretty_course_name}."

    send_email(
        sender="OH Queue <cs61a@berkeley.edu>",
        target=recipient.email,
        subject=f"{pretty_course_name} Appointment Cancelled",
        body=(
            cleandoc(
                f"""
    Hi {recipient.short_name},

    {message}
    
    Best,
    The 61A Software Team
    """.strip()
            )
        ),
    )


def get_uid(signup: AppointmentSignup, isStaff: bool) -> str:
    return str(signup.appointment_id) + str(isStaff)
