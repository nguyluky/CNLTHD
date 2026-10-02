from typing import Optional
import uuid

from fastapi import Cookie, Depends, HTTPException, HTTPException, Header, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from typing_extensions import Annotated
from fastapi import status

from fastapi.security import OAuth2PasswordBearer

from app.core.logger import logger
from app.core.database import User, get_db
from app.core.security import decode_token
from app.core.config import config
from user_agents import parse
from app.core.email import EmailServiceFactory, EmailServiceInterface, EmailService, MockEmailService

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login", refreshUrl="/auth/refresh")


async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)], db: AsyncSession = Depends(get_db)
):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    invid_token_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid token type",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = decode_token(token)
    except Exception as e:
        raise credentials_exception

    if not payload:
        raise credentials_exception

    if payload.get("type") != "access":
        raise invid_token_exception

    user_email = payload.get("sub")
    if user_email is None:
        raise credentials_exception

    user = await db.scalar(select(User).where(User.email == user_email))

    if user is None:
        raise credentials_exception

    return user


async def get_current_active_user(current_user: User = Depends(get_current_user)):
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user


async def get_current_active_admin(
    req: Request, current_user: User = Depends(get_current_active_user)
):
    if not current_user.is_admin():
        logger.warning(
            f"{current_user.email}({current_user.role.value}) is trying to access admin route {req.url.path}"
        )
        raise HTTPException(status_code=403, detail="Not enough permissions")
    return current_user


def get_email_service() -> EmailServiceInterface:
    # return EmailService.get_instance(api_key=config.BIRD_API_KEY)
    return EmailServiceFactory.create_email_service()


EmailServiceDep = Annotated[EmailServiceInterface, Depends(get_email_service)]


# Schema để chứa dữ liệu trả về từ DI phù hợp với DB Model của bạn
class DeviceInfo(BaseModel):
    device_id: Optional[str] = None
    device_name: Optional[str] = None
    device_type: Optional[str] = None
    os: Optional[str] = None
    browser: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None


async def get_current_device_info(
    request: Request,
    user_agent: Optional[str] = Header(None),
    # Thử lấy device_id từ Header (X-Device-Id) hoặc từ Cookie (device_id)
    x_device_id: Optional[str] = Header(None, alias="X-Device-Id"),
    device_id_cookie: Optional[str] = Cookie(None, alias="device_id"),
) -> DeviceInfo:
    # 1. Xác định device_id (Ưu tiên Header -> Cookie -> Tự tạo mới)
    device_id = x_device_id or device_id_cookie or str(uuid.uuid4())

    # 2. Lấy raw User-Agent và IP
    ua_string = user_agent or request.headers.get("user-agent", "")

    # Xử lý IP (Hỗ trợ nếu chạy sau Proxy như Nginx/Cloudflare)
    ip_address = request.headers.get("x-forwarded-for")
    if ip_address:
        ip_address = ip_address.split(",")[0].strip()
    else:
        ip_address = request.client.host if request.client else None

    # 3. Phân tích User-Agent
    device_name = "Unknown"
    device_type = "Unknown"
    os_name = "Unknown"
    browser_name = "Unknown"

    if ua_string:
        parsed_ua = parse(ua_string)

        # Lấy OS và Browser kèm version
        os_name = f"{parsed_ua.os.family} {parsed_ua.os.version_string}".strip()
        browser_name = (
            f"{parsed_ua.browser.family} {parsed_ua.browser.version_string}".strip()
        )

        # Xác định Device Type
        if parsed_ua.is_pc:
            device_type = "Desktop"
        elif parsed_ua.is_mobile:
            device_type = "Mobile"
        elif parsed_ua.is_tablet:
            device_type = "Tablet"
        elif parsed_ua.is_bot:
            device_type = "Bot"

        # Xác định Device Name (Tên hãng + model nếu là mobile/tablet)
        if parsed_ua.device.family and parsed_ua.device.family != "Other":
            brand = parsed_ua.device.brand or ""
            model = parsed_ua.device.model or ""
            device_name = f"{brand} {model}".strip() or parsed_ua.device.family
        else:
            device_name = "PC / Laptop"

    return DeviceInfo(
        device_id=device_id,
        device_name=device_name[:255]
        if device_name
        else None,  # Cắt chuỗi tránh tràn 255 ký tự của DB
        device_type=device_type[:255] if device_type else None,
        os=os_name[:255] if os_name else None,
        browser=browser_name[:255] if browser_name else None,
        ip_address=ip_address[:45]
        if ip_address
        else None,  # Chuỗi IPv6 tối đa 45 ký tự
        user_agent=ua_string[:255] if ua_string else None,
    )


DeviceInfoDep = Annotated[DeviceInfo, Depends(get_current_device_info)]
