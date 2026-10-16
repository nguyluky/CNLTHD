
from app.schemas.auth import RegisterIn
from app.schemas.services import ServiceUpdateIn


def test_name_strip_all_html():
    payload = {
        "name": "<script>alert('xss')</script>Deluxe Haircut <b>Pro</b>",
    }
    request = ServiceUpdateIn(name=payload["name"])
    assert request.name == "Deluxe Haircut Pro"


def test_description_keep_safe_html():
    payload = {
        "description": (
            "<p>Best service in town. <script>steal_cookies()</script></p>"
            "<p><strong>Book now!</strong> Check <a href='https://example.com'>link</a></p>"
        )
    }
    service = ServiceUpdateIn(description=payload["description"])

    assert "<script>" not in str(service.description)
    assert "<strong>Book now!</strong>" in str(service.description)
    assert 'href="https://example.com"' in str(service.description)

def test_full_name_strip_all_html():
    payload = {
        "full_name": "<script>alert('xss')</script>John <b>Lenon</b>",
        "email": "customer@example.com",
        "password": "customerpassword",
        "phone": "0901234678",
    }
    request = RegisterIn(
        full_name=payload["full_name"],
        email=payload["email"],
        password=payload["password"],
        phone=payload["phone"]
    )
    # fullname must sanitize all html tags
    assert request.full_name == "John Lenon"