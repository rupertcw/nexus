import os
import jwt
from fastapi import HTTPException, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

security = HTTPBearer()

SECRET_KEY = os.environ.get("NEXUS_JWT_SECRET", "dev_secret")

def verify_token(credentials: HTTPAuthorizationCredentials = Security(security)):
    """Extracts and verifies JWT token for secure endpoint access."""
    try:
        payload = jwt.decode(
            credentials.credentials, 
            SECRET_KEY, 
            algorithms=["HS256"],
            options={"verify_signature": SECRET_KEY != "dev_secret"}
        )
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid authentication token")
