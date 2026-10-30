"""Firebase token verification shared by all authenticated routes."""
import os
from pathlib import Path
from dotenv import load_dotenv
from fastapi import HTTPException, Header
import firebase_admin
from firebase_admin import auth, credentials

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

def firebase_app():
    try:
        return firebase_admin.get_app()
    except ValueError:
        path = os.getenv("FIREBASE_SERVICE_ACCOUNT_PATH")
        if not path:
            raise HTTPException(status_code=503, detail="Firebase service account is not configured")
        credential_path = Path(path).expanduser()
        if not credential_path.is_absolute():
            credential_path = Path(__file__).resolve().parents[2] / credential_path
        try:
            return firebase_admin.initialize_app(credentials.Certificate(str(credential_path)))
        except Exception:
            raise HTTPException(status_code=503, detail="Firebase service account could not be loaded")

async def get_current_user(authorization: str = Header(None)) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid authorization header")
    app = firebase_app()
    try:
        decoded = auth.verify_id_token(authorization[7:], app=app)
        return decoded["uid"]
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
