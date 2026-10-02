from app.core.database import get_db, User, UserRole
from app.schemas.user import UserOut
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import APIRouter, Depends, HTTPException, status

router = APIRouter(prefix="/barbers", tags=["Barber"])

@router.get(
    "",
    description="Get all barbers",
    response_model=list[UserOut],
    status_code=status.HTTP_200_OK,
)
async def get_barbers(
    db: AsyncSession = Depends(get_db)
    ):
    """
    Get all barbers.
    """
    barbers = (await db.scalars(select(User).where(User.role == UserRole.barber,))).all()
    if  not barbers or len(barbers) <= 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No barbers found")
    
    return barbers

@router.get(
    "/{barber_id}",
    description="Get barber by ID",
    response_model=UserOut,
    status_code=status.HTTP_200_OK,
)
async def get_barber(
    barber_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    Get a barber by ID.
    """
    barber = (await db.scalar(select(User).where(User.id == barber_id, User.role == UserRole.barber)))
    if not barber:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Barber not found")

    return barber