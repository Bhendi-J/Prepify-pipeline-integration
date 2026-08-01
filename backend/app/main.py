from fastapi import FastAPI #for creating the FastAPI application instance

from app.api.router import router as api_router


app = FastAPI() #creating a FastAPI application instance
app.include_router(api_router) #register the application API routes

@app.get("/")
def root(): 
    return {"message": "Hello World"} #returning a simple JSON response with a message when the root endpoint is accessed

