from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging

from app.config import settings
from app.llm_providers import openai_manager
from app.api.chat import router as chat_router
from app.api.health import router as health_router

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    logger.info("Starting Oliver Backend...")
    
    try:
        # Initialize OpenAI client
        openai_manager.initialize_client()
        logger.info(f"Successfully initialized OpenAI client with model: {settings.OPENAI_MODEL}")
        
        # Log current configuration
        provider_info = openai_manager.get_current_provider_info()
        logger.info(f"Provider info: {provider_info}")
        
        yield
        
    except Exception as e:
        logger.error(f"Failed to initialize application: {e}")
        # Don't crash the app, but log the error
        yield
    
    finally:
        logger.info("Shutting down Oliver Backend...")

# Create FastAPI app
app = FastAPI(
    title="Oliver Backend",
    description="AI-powered compliance assistant backend using OpenAI Responses API",
    version="1.0.0",
    lifespan=lifespan
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        settings.FRONTEND_URL,
        "http://localhost:3000",
        "http://localhost:3001",
        "https://localhost:3000",  # HTTPS support
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(health_router)
app.include_router(chat_router)

# Exception handlers
@app.exception_handler(ValueError)
async def value_error_handler(request, exc):
    return HTTPException(status_code=400, detail=str(exc))

@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    logger.error(f"Unhandled exception: {exc}")
    return HTTPException(status_code=500, detail="Internal server error")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=settings.PORT,
        reload=True,
        log_level="info"
    ) 