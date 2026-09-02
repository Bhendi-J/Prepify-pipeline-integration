from fastapi import FastAPI #for creating the FastAPI application instance
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import router as api_router
from app.core.config import settings


app = FastAPI() #creating a FastAPI application instance
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        origin.strip()
        for origin in settings.CORS_ORIGINS.split(",")
        if origin.strip()
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(api_router) #register the application API routes

@app.get("/")
def root(): 
    return {"message": "Hello World"} #returning a simple JSON response with a message when the root endpoint is accessed
