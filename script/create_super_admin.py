import os, json

from random import random


from app.core.database import SessionLocal, User, UserRole
from app.main import engine


async def main() -> None:
    async with SessionLocal() as session:
        
        # Create a super admin user
        super_admin = User(
            full_name="Super Admin",
            email="admin@gmail.com",
            role=UserRole.admin,
            phone="1234567890",
        )


        # generate password len 10
        password = random().hex()[:10]
        
        super_admin.hash_password(password)
        session.add(super_admin)
        await session.commit()
        await session.refresh(super_admin)

        
        os.makedirs("./local", exist_ok=True)

        with open("./local/super_admin.json", "w") as f:
            f.write(json.dumps({
                "username": super_admin.email,
                "email": super_admin.email,
                "password": password,
            }, indent=4))

        print(f"Super admin created successfully. Credentials saved in ./local/super_admin.json")

        

if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
            
