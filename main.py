from fastapi import FastAPI
import uvicorn

app = FastAPI()


@app.get("/")
async def index():
    print('hello')
    return {
        "mess": "hello"
    }

@app.post('/')
def post_index():
    return "hello"

if __name__ == "__main__":
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        # reload=True
    )