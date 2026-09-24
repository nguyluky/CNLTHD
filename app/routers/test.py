from fastapi import APIRouter
from fastapi.exceptions import HTTPException



router = APIRouter()

# @apiRouter.get("/test", response_model=SuccessResponse, responses={201: {"model": CreatedResponse}})
# async def test(create: bool = False):
#     if create:
#         raise HTTPException(status_code=201, detail="Test resource created")
#     return SuccessResponse(message="Test resource retrieved", content={"test_id": 1})
    