import logging
from contextlib import asynccontextmanager
import time

import structlog
from fastapi import FastAPI, HTTPException, Depends
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from datetime import datetime

from pydantic import SecretStr
from pydantic_settings import BaseSettings
from truenas_api_client import Client
from fastapi import Request

# logging.basicConfig(level=logging.INFO)
logger = structlog.get_logger()


class Settings(BaseSettings):
    truenas_host: str
    truenas_api_key: SecretStr
    truenas_api_user: str

    model_config = dict(env_file=".env")


class TrueNASDaemon:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.uri = f"wss://{settings.truenas_host}/api/current"
        self.client = None

    def setup(self):
        """Initialize the client connection"""
        if self.client is None:
            self.client = Client(uri=self.uri, verify_ssl=False, ping_interval=30)
            logger.info(f"Sending key: {self.settings.truenas_api_key} to {self.uri}")
            result = self.client.call(
                "auth.login_ex",
                {
                    "mechanism": "API_KEY_PLAIN",
                    "username": self.settings.truenas_api_user,
                    "api_key": self.settings.truenas_api_key.get_secret_value(),
                },
            )
            if result["response_type"] == "SUCCESS":
                logger.info("TrueNAS client initialized and authenticated")
            else:
                logger.error(f"Authentication failed: {result['response_type']}")
                raise HTTPException(status_code=401, detail="Authentication failed")

    def cleanup(self):
        """Cleanup client resources"""
        if self.client:
            self.client.close()
            self.client = None

    def send_request(self, method: str, params: list) -> dict:
        """Send request using the established client connection"""
        if not self.client:
            raise HTTPException(
                status_code=503, detail="TrueNAS client not initialized"
            )
        try:
            return self.client.call(method, *params)
        except Exception as e:
            logger.error(f"Request failed: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))

    def reset_connection(self):
        """Force a connection reset"""
        self.cleanup()
        self.setup()

    def is_connected(self):
        """Check if the connection is alive"""
        try:
            return self.client is not None and self.client.ping() == "pong"
        except Exception:
            return False


@asynccontextmanager
async def lifespan(app: FastAPI):
    logging.getLogger("uvicorn.access").handlers.clear()
    settings = Settings()
    truenas_daemon = TrueNASDaemon(settings)
    truenas_daemon.setup()

    yield {"truenas_daemon": truenas_daemon}

    truenas_daemon.cleanup()


app = FastAPI(title="TrueNAS REST-to-WebSocket Bridge", lifespan=lifespan)
security = HTTPBasic()


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()

    # Get the client's IP address
    forwarded_for = request.headers.get("X-Forwarded-For")
    client_ip = forwarded_for.split(",")[0] if forwarded_for else request.client.host

    # Log the incoming request
    logger.info(
        "Request started",
        method=request.method,
        path=request.url.path,
        client_ip=client_ip,
    )

    response = await call_next(request)

    # Calculate request processing time
    process_time = time.time() - start_time

    # Log the completed request
    logger.info(
        "Request completed",
        method=request.method,
        path=request.url.path,
        status_code=response.status_code,
        duration=f"{process_time:.3f}s",
        client_ip=client_ip,
    )

    return response


@app.post("/api/{path:path}")
async def handle_api_request(
    request: Request,
    path: str,
    request_data: dict,
    credentials: HTTPBasicCredentials = Depends(security),
):
    """Handle REST API requests"""
    truenas_daemon = request.state.truenas_daemon
    method = path.replace("/", ".")
    params = [request_data] if request_data else []
    logger.info(
        "Sending request",
        method=method,
        params=params,
        host=truenas_daemon.settings.truenas_host,
    )
    return request.state.truenas_daemon.send_request(method, params)


@app.get("/health")
async def health_check(request: Request):
    """Health check endpoint"""
    truenas_daemon = request.state.truenas_daemon
    try:
        status = (
            "healthy"
            if truenas_daemon.client and truenas_daemon.client.ping() == "pong"
            else "unhealthy"
        )
    except:
        status = "unhealthy"

    return {"status": status, "timestamp": datetime.utcnow().isoformat()}


if __name__ == "__main__":
    import uvicorn

    settings = Settings()
    uvicorn.run(app, host="0.0.0.0", port=8000)#, log_config=None)
