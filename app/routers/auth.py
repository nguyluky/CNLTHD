from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import config
from app.core.database import User, get_db
from app.schemas.auth import LoginOut, RegisterIn, RegisterOut

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", 
            description="Register a new user",
            response_model=RegisterOut, status_code=201, responses={409: {"description": "User already exists"}})
async def register(
    body: RegisterIn,
    db: AsyncSession = Depends(get_db)
):
    """
    Register a new user.
    - **full_name**: Full name of the user
    - **email**: Email address of the user unique
    - **password**: Password for the user account
    - **phone**: Phone number of the user unique
    """

    # check if user already exists
    existing_user = await db.scalar(
        select(User).where(or_(User.email == body.email, User.phone == body.phone))
    )
    if existing_user:
        raise HTTPException(status_code=409, detail="User already exists")

    # remove password from body before creating user
    user = User(**body.model_dump(exclude={"password"}))
    user.hash_password(body.password)
    db.add(user)
    await db.commit()
    await db.refresh(user)

    return {"message": "User registered successfully"}


@router.post("/login", 
            description="Login with email and password",
            response_model=LoginOut, status_code=200)
async def login(
    body: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: AsyncSession = Depends(get_db)
):

    user = await db.scalar(select(User).where(User.email == body.username))
    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    
    # verify password
    if not user.verify_password(body.password):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    
    token = user.create_access_token(timedelta(minutes=config.ACCESS_TOKEN_EXPIRE_MINUTES))
    return {
        "message": "Login successful",
        "email": user.email,
        "access_token": token
    }