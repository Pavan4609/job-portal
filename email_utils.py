import os
import smtplib

from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from dotenv import load_dotenv


# Get the folder where email_utils.py is located
BASE_DIR = os.path.dirname(
    os.path.abspath(__file__)
)

# Load .env from project root
ENV_FILE = os.path.join(
    BASE_DIR,
    ".env"
)

load_dotenv(ENV_FILE)


MAIL_USERNAME = os.getenv("MAIL_USERNAME")
MAIL_PASSWORD = os.getenv("MAIL_PASSWORD")


def send_email(to_email, subject, message):

    try:

        if not MAIL_USERNAME:

            print("ERROR: MAIL_USERNAME is missing in .env")

            return False

        if not MAIL_PASSWORD:

            print("ERROR: MAIL_PASSWORD is missing in .env")

            return False

        print("Email account:", MAIL_USERNAME)
        print("Trying to send email to:", to_email)

        msg = MIMEMultipart()

        msg["From"] = MAIL_USERNAME
        msg["To"] = to_email
        msg["Subject"] = subject

        msg.attach(
            MIMEText(message, "plain")
        )

        server = smtplib.SMTP(
            "smtp.gmail.com",
            587
        )

        server.starttls()

        server.login(
            MAIL_USERNAME,
            MAIL_PASSWORD
        )

        server.sendmail(
            MAIL_USERNAME,
            to_email,
            msg.as_string()
        )

        server.quit()

        print("Email sent successfully!")

        return True

    except Exception as error:

        print("================================")
        print("EMAIL ERROR:")
        print(error)
        print("================================")

        return False