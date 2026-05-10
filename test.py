# test.py
from fastapi import FastAPI

app = FastAPI(title="Test API", version="1.0")

@app.get("/")
async def root():
    return {"message": "Hello World"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("test:app", reload=True)