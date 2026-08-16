from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, EmailStr

from app.integrations.supabase import auth_service

router = APIRouter(prefix="/api/auth", tags=["auth"])

_bearer = HTTPBearer(auto_error=False)


class SignUpRequest(BaseModel):
    email: EmailStr
    password: str


class VerifyOtpRequest(BaseModel):
    email: EmailStr
    token: str


class ResendOtpRequest(BaseModel):
    email: EmailStr


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    new_password: str


def _map_error(exc: Exception) -> HTTPException:
    status_code = getattr(exc, "status_code", None)
    if isinstance(status_code, int) and status_code >= 400:
        return HTTPException(status_code=status_code, detail=str(exc))
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post("/signup", summary="Register with email + password")
def signup(payload: SignUpRequest):
    try:
        return auth_service.sign_up(email=payload.email, password=payload.password)
    except Exception as exc:  # noqa: BLE001
        raise _map_error(exc) from exc


@router.post("/verify-otp", summary="Verify the email OTP")
def verify_otp(payload: VerifyOtpRequest):
    try:
        return auth_service.verify_otp(email=payload.email, token=payload.token)
    except Exception as exc:  # noqa: BLE001
        raise _map_error(exc) from exc


@router.post("/resend-otp", summary="Resend the verification OTP")
def resend_otp(payload: ResendOtpRequest):
    try:
        return auth_service.resend_otp(email=payload.email)
    except Exception as exc:  # noqa: BLE001
        raise _map_error(exc) from exc


@router.post("/login", summary="Log in with email + password")
def login(payload: LoginRequest):
    try:
        return auth_service.sign_in(email=payload.email, password=payload.password)
    except Exception as exc:  # noqa: BLE001
        raise _map_error(exc) from exc


@router.post("/forgot-password", summary="Send the password reset email")
def forgot_password(payload: ForgotPasswordRequest):
    try:
        return auth_service.reset_password_for_email(email=payload.email)
    except Exception as exc:  # noqa: BLE001
        raise _map_error(exc) from exc


@router.post("/reset-password", summary="Set a new password (recovery session)")
def reset_password(
    payload: ResetPasswordRequest,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
):
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    try:
        return auth_service.update_password(
            access_token=credentials.credentials,
            new_password=payload.new_password,
        )
    except Exception as exc:  # noqa: BLE001
        raise _map_error(exc) from exc


@router.post("/logout", summary="Sign out the current session")
def logout(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
):
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    try:
        return auth_service.sign_out(access_token=credentials.credentials)
    except Exception as exc:  # noqa: BLE001
        raise _map_error(exc) from exc
