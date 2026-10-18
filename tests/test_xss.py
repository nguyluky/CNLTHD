
from app.schemas.auth import RegisterIn
from app.schemas.services import ServiceUpdateIn


def test_name_encode_all_special_html_characters():
    payload = {
        "name": "<script>alert('xss')</script>Deluxe Haircut <b>Pro</b>",
    }
    request = ServiceUpdateIn(name=payload["name"])
    assert request.name == "&lt;script&gt;alert(&#x27;xss&#x27;)&lt;/script&gt;Deluxe Haircut &lt;b&gt;Pro&lt;/b&gt;"


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
    assert 'rel="noopener noreferrer"' in str(service.description)

def test_full_name_encode_all_special_html_characters():
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
    assert request.full_name == "&lt;script&gt;alert(&#x27;xss&#x27;)&lt;/script&gt;John &lt;b&gt;Lenon&lt;/b&gt;"