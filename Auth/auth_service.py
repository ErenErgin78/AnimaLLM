"""
Kimlik doğrulama servisi
JWT token üretimi, şifre hashleme ve kullanıcı doğrulama işlemleri
"""

from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from Auth.models import User
from Auth.schemas import UserRegister, UserResponse
import os
from dotenv import load_dotenv

load_dotenv()

# Şifre hashleme context'i - bcrypt algoritması kullanır
# bcrypt: Güvenli şifre hashleme algoritması (salt otomatik eklenir)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# JWT ayarları - environment variable'dan alınır
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "your-secret-key-change-this-in-production")
ALGORITHM = "HS256"  # HMAC SHA-256 algoritması
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 7 gün (dakika cinsinden)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Düz metin şifreyi hashlenmiş şifre ile karşılaştırır
    """
    try:
        return pwd_context.verify(plain_password, hashed_password)
    except Exception as e:
        # Hash doğrulama hatası - güvenlik nedeniyle False döndür
        print(f"[AUTH ERROR] Şifre doğrulama hatası: {e}")
        return False


def get_password_hash(password: str) -> str:
    """
    Şifreyi hashler - bcrypt ile güvenli hash üretir
    """
    try:
        return pwd_context.hash(password)
    except Exception as e:
        print(f"[AUTH ERROR] Şifre hashleme hatası: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Şifre hashleme hatası"
        )


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    JWT access token oluşturur
    """
    try:
        to_encode = data.copy()
        
        # Token geçerlilik süresi belirleme
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        
        # Token payload'a expire ekle
        to_encode.update({"exp": expire})
        
        # JWT token oluştur
        encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
        return encoded_jwt
    except Exception as e:
        print(f"[AUTH ERROR] Token oluşturma hatası: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Token oluşturma hatası"
        )


def verify_token(token: str) -> Optional[dict]:
    """
    JWT token'ı doğrular ve payload'ı döndürür
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError as e:
        # Token geçersiz veya süresi dolmuş
        print(f"[AUTH ERROR] Token doğrulama hatası: {e}")
        return None


def get_user_by_email(db: Session, email: str) -> Optional[User]:
    """
    E-posta adresine göre kullanıcı bulur
    """
    try:
        # SQL injection koruması - SQLAlchemy ORM kullanıldığı için otomatik korunur
        # Email lowercase yapılmış olmalı (validation'da yapılıyor)
        user = db.query(User).filter(User.email == email.lower().strip()).first()
        return user
    except Exception as e:
        print(f"[AUTH ERROR] Kullanıcı sorgulama hatası: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Kullanıcı sorgulama hatası"
        )


def get_user_by_username(db: Session, username: str) -> Optional[User]:
    """
    Kullanıcı adına göre kullanıcı bulur
    """
    try:
        # SQL injection koruması - SQLAlchemy ORM kullanıldığı için otomatik korunur
        user = db.query(User).filter(User.username == username.strip()).first()
        return user
    except Exception as e:
        print(f"[AUTH ERROR] Kullanıcı sorgulama hatası: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Kullanıcı sorgulama hatası"
        )


def create_user(db: Session, user_data: UserRegister) -> User:
    """
    Yeni kullanıcı oluşturur
    """
    try:
        # Kullanıcı adı zaten kayıtlı mı kontrol et
        existing_user = get_user_by_username(db, user_data.username)
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Bu kullanıcı adı zaten kayıtlı"
            )
        
        # E-posta zaten kayıtlı mı kontrol et
        existing_user = get_user_by_email(db, user_data.email)
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Bu e-posta adresi zaten kayıtlı"
            )
        
        # Şifreyi hashle
        hashed_password = get_password_hash(user_data.password)
        
        # Yeni kullanıcı oluştur
        new_user = User(
            username=user_data.username.strip(),  # Boşlukları temizle
            name=user_data.name.strip(),  # Boşlukları temizle
            email=user_data.email.lower().strip(),  # Küçük harfe çevir ve boşlukları temizle
            hashed_password=hashed_password
        )
        
        # Veritabanına kaydet
        db.add(new_user)
        db.commit()  # Transaction'ı commit et
        db.refresh(new_user)  # Yeni oluşturulan ID'yi al
        
        print(f"[AUTH] Yeni kullanıcı oluşturuldu: {new_user.username} ({new_user.email})")
        return new_user
        
    except HTTPException:
        # HTTPException'ı tekrar fırlat (status code korunur)
        raise
    except Exception as e:
        # Diğer hatalar için rollback yap
        db.rollback()
        print(f"[AUTH ERROR] Kullanıcı oluşturma hatası: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Kullanıcı oluşturma hatası"
        )


def authenticate_user(db: Session, email: str, password: str) -> Optional[User]:
    """
    Kullanıcı kimlik doğrulaması yapar
    """
    try:
        # Kullanıcıyı bul
        user = get_user_by_email(db, email)
        if not user:
            return None
        
        # Şifreyi doğrula
        if not verify_password(password, user.hashed_password):
            return None
        
        print(f"[AUTH] Kullanıcı doğrulandı: {user.email}")
        return user
        
    except Exception as e:
        print(f"[AUTH ERROR] Kimlik doğrulama hatası: {e}")
        return None

