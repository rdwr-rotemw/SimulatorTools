"""
Main FastAPI application entrypoint (scaffold).

What to implement here:
- Configure app-wide middleware, CORS, exception handlers
- Register routers from `routes/`
- Wire startup/shutdown events
- Optionally configure logging and dependency injection
"""

from fastapi import FastAPI

# Import routers (routes/__init__.py should expose them)
from .routes import router as api_router

app = FastAPI(title="Simulators Tools Backend")

# Register API routes
app.include_router(api_router)

# Example startup/shutdown placeholders
@app.on_event("startup")
async def on_startup():
    # TODO: initialize DB connections, caches, telemetry, etc.
    pass

@app.on_event("shutdown")
async def on_shutdown():
    # TODO: gracefully close resources
    pass

# Minimal run guard for local dev
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.app.main:app", host="0.0.0.0", port=8000, reload=True)
