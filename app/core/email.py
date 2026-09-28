

from bird import APIError, AsyncBird
from app.core.logger import logger
from app.core.config import config


# email service abstrac class

class EmailServiceInterface:
    async def send_email(self, to: str, subject: str, html: str) -> dict | None:
        raise NotImplementedError

    async def send_confirmation_email(self, to: str, confirmation_link: str) -> dict | None:
        raise NotImplementedError

class EmailService(EmailServiceInterface):

    # static hold instance of EmailService
    instance = None

    @staticmethod
    def get_instance(api_key: str):
        if EmailService.instance is None:
            EmailService.instance = EmailService(api_key)
        return EmailService.instance

    def __init__(self, api_key: str):
        self.client = AsyncBird(api_key=api_key)
        self.confirmation_email_template = open("email_templates/confirmation.html", "r").read()

    async def send_email(self, to: str, subject: str, html: str) -> dict | None:
        """
        Send an email using the Bird API.

        Args:
            to (str): Recipient email address.
            subject (str): Subject of the email.
            html (str): HTML content of the email.

        Returns:
            dict: Response from the Bird API.
        """
        try:
            response = await self.client.email.send(
                from_="noreply@nguyluky.dev",
                to=[to],
                subject=subject,
                html=html
            )
            logger.info(f"Email sent successfully: {response}")
            return {
                "id": response.id,
                "status": response.status,
            }
        except APIError as e:
            logger.error(f"Failed to send email: {e}")
            return None

    async def send_confirmation_email(self, to: str, confirmation_link: str) -> dict | None:
        """
        Send a confirmation email to the specified recipient.

        Args:
            to (str): Recipient email address.

        Returns:
            dict: Response from the Bird API.
        """
        subject = "Please confirm your email address"
        html_content = self.confirmation_email_template.replace("{{confirmation_link}}", confirmation_link)

        return await self.send_email(to, subject, html_content)


class MockEmailService(EmailServiceInterface):
    async def send_email(self, to: str, subject: str, html: str) -> dict | None:
        logger.info(f"Mock send email to {to} with subject '{subject}'")
        return {
            "id": "mock_id",
            "status": "mock_status",
        }

    async def send_confirmation_email(self, to: str, confirmation_link: str) -> dict | None:
        logger.info(f"Mock send confirmation email to {to} with link '{confirmation_link}'")
        return {
            "id": "mock_id",
            "status": "mock_status",
        }
