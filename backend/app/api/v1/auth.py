"""
API de Autenticacion
"""
from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import (
    verify_password, get_password_hash, create_access_token, decode_token
)
from app.core.config import settings
from app.models.database_models import User, Company, UserRole
from app.models.schemas import UserCreate, UserLogin, UserResponse, TokenResponse

router = APIRouter(prefix="/auth", tags=["Authentication"])

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)


def _get_or_create_default_user(db: Session) -> User:
    user = db.query(User).first()
    if user:
        return user

    default_user = User(
        email="demo@local",
        hashed_password="disabled",
        full_name="Demo User",
        role=UserRole.ADMIN,
        is_active=True
    )
    db.add(default_user)
    db.commit()
    db.refresh(default_user)
    return default_user


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> User:
    """Obtener usuario actual desde token (auth deshabilitada)"""
    if not token:
        return _get_or_create_default_user(db)

    token_data = decode_token(token)
    if token_data is None or token_data.email is None:
        return _get_or_create_default_user(db)

    user = db.query(User).filter(User.email == token_data.email).first()
    if user is None:
        return _get_or_create_default_user(db)

    return user


@router.post("/register", response_model=UserResponse)
def register(user_data: UserCreate, db: Session = Depends(get_db)):
    """Registrar nuevo usuario"""
    # Verificar si email ya existe
    existing = db.query(User).filter(User.email == user_data.email).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )

    # Crear usuario
    user = User(
        email=user_data.email,
        hashed_password=get_password_hash(user_data.password),
        full_name=user_data.full_name,
        company_id=user_data.company_id
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    return user


@router.post("/login", response_model=TokenResponse)
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    """Login y obtener token JWT"""
    user = db.query(User).filter(User.email == form_data.username).first()

    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is disabled"
        )

    # Crear token
    access_token = create_access_token(
        data={
            "sub": user.email,
            "company_id": str(user.company_id) if user.company_id else None,
            "role": user.role.value if user.role else None
        },
        expires_delta=timedelta(hours=settings.JWT_EXPIRATION_HOURS)
    )

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=settings.JWT_EXPIRATION_HOURS * 3600
    )


@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    """Obtener informacion del usuario actual"""
    return current_user


@router.post("/refresh", response_model=TokenResponse)
def refresh_token(current_user: User = Depends(get_current_user)):
    """Refrescar token JWT"""
    access_token = create_access_token(
        data={
            "sub": current_user.email,
            "company_id": str(current_user.company_id) if current_user.company_id else None,
            "role": current_user.role.value if current_user.role else None
        },
        expires_delta=timedelta(hours=settings.JWT_EXPIRATION_HOURS)
    )

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=settings.JWT_EXPIRATION_HOURS * 3600
    )
