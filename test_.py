import asyncio
import threading
import time
import httpx
import pytest
from fastapi import FastAPI
import uvicorn
from multiprocessing import Process


get_user_async = lambda: asyncio.sleep(2.0, result={"username": "test_user"})
get_user_sync = lambda: time.sleep(2.0) or {"username": "test_user"}

validate_password_sync = lambda: time.sleep(2.0) or True

app = FastAPI()


@app.get("/blocking-sync")
async def blocking_async():
    user = await get_user_async()
    validate_password = validate_password_sync()

    return {"message": ""}


@app.get("/blocking-concurrent")
async def nonblocking_sync():
    user = await get_user_async()  # get user from db
    validate_password = await asyncio.to_thread(validate_password_sync)

    return {"message": ""}


@app.get("/concurrent-nonblocking")
def nonblocking_concurrent():
    user = get_user_sync()
    validate_password = validate_password_sync()

    return {"message": ""}


@app.get("/fast")
async def fast_endpoint():
    return {"message": "return immediately!"}


def _start_server():
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")


def run_server():
    p = Process(target=_start_server, args=())
    p.start()


async def main():
    async with httpx.AsyncClient() as client:
        total_requests_to_send = 10

        # send 5 concurrent requests to the blocking-sync endpoint and measure the time taken for each request
        async def send_request(endpoint, start_time, index):
            print(f"Sending request {index + 1} to /{endpoint}")
            response = await client.get(
                f"http://localhost:8000/{endpoint}", timeout=10000
            )
            end_time = time.time()
            print(
                f"Request {index + 1} to /{endpoint} took {end_time - start_time:.2f} seconds"
            )

        endpoints = [
            "blocking-sync",
            "blocking-concurrent",
            "concurrent-nonblocking",
            "fast",
        ]

        for endpoint in endpoints:
            print(
                f"Sending {total_requests_to_send} concurrent requests to /{endpoint}"
            )
            request_batch_start_time = time.time()
            tasks = [
                send_request(endpoint, request_batch_start_time, i)
                for i in range(total_requests_to_send)
            ]
            await asyncio.gather(*tasks)
            all_end_time = time.time()
            print(
                f"Total time for {total_requests_to_send} requests to /{endpoint}: {all_end_time - request_batch_start_time:.2f} seconds\n"
            )
            print("-" * 50)


if __name__ == "__main__":
    asyncio.run(main())
