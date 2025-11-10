"""
FastAPI dependencies - JWT token doğrulama
Korumalı endpoint'ler için kullanıcı doğrulama dependency'si
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from Auth.database import get_db
from Auth.auth_service import verify_token, get_user_by_email
from Auth.models import User

# HTTP Bearer token security scheme
security = HTTPBearer()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    """
    JWT token'dan kullanıcı bilgisini çıkarır ve kullanıcıyı döndürür
    Korumalı endpoint'ler için dependency olarak kullanılır
    """
    try:
        # Token'ı credentials'dan al
        token = credentials.credentials
        
        # Token'ı doğrula
        payload = verify_token(token)
        if payload is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Geçersiz veya süresi dolmuş token",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Token payload'dan kullanıcı bilgilerini al
        user_id: int = payload.get("sub")  # JWT standardında "sub" (subject) user_id'yi temsil eder
        user_email: str = payload.get("email")
        
        if user_id is None or user_email is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token içeriği geçersiz",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Kullanıcıyı veritabanından bul
        user = get_user_by_email(db, user_email)
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Kullanıcı bulunamadı",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Kullanıcı ID'sini kontrol et (ekstra güvenlik)
        if user.id != user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token ve kullanıcı bilgileri eşleşmiyor",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        return user
        
    except HTTPException:
        # HTTPException'ı tekrar fırlat
        raise
    except Exception as e:
        # Beklenmeyen hatalar
        print(f"[AUTH ERROR] Kullanıcı doğrulama hatası: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Kullanıcı doğrulama hatası",
            headers={"WWW-Authenticate": "Bearer"},
        )

