"""
Auth API route'ları
Kullanıcı kayıt, giriş, çıkış ve profil endpoint'leri
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from Auth.database import get_db
from Auth.schemas import UserRegister, UserLogin, UserResponse, TokenResponse
from Auth.auth_service import create_user, authenticate_user, create_access_token
from Auth.dependencies import get_current_user
from Auth.models import User

# Router oluştur - tüm auth endpoint'leri burada
router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(
    user_data: UserRegister,
    db: Session = Depends(get_db)
):
    """
    Yeni kullanıcı kaydı oluşturur
    """
    try:
        # Yeni kullanıcı oluştur
        new_user = create_user(db, user_data)
        
        # Kullanıcı bilgilerini döndür (şifre hariç)
        return UserResponse(
            id=new_user.id,
            username=new_user.username,
            name=new_user.name,
            email=new_user.email,
            created_at=new_user.created_at
        )
        
    except HTTPException:
        # HTTPException'ı tekrar fırlat
        raise
    except Exception as e:
        print(f"[AUTH ERROR] Kayıt hatası: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Kayıt işlemi başarısız"
        )


@router.post("/login", response_model=TokenResponse)
def login(
    user_data: UserLogin,
    db: Session = Depends(get_db)
):
    """
    Kullanıcı girişi yapar ve JWT token döndürür
    """
    try:
        # Kullanıcı kimlik doğrulaması
        user = authenticate_user(db, user_data.email, user_data.password)
        
        if user is None:
            # Güvenlik nedeniyle genel hata mesajı (hangi bilginin yanlış olduğunu söyleme)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="E-posta veya şifre hatalı",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # JWT token oluştur
        # JWT standardında "sub" (subject) user_id'yi temsil eder
        token_data = {
            "sub": user.id,
            "email": user.email
        }
        access_token = create_access_token(data=token_data)
        
        # Token ve kullanıcı bilgilerini döndür
        return TokenResponse(
            access_token=access_token,
            token_type="bearer",
            user=UserResponse(
                id=user.id,
                username=user.username,
                name=user.name,
                email=user.email,
                created_at=user.created_at
            )
        )
        
    except HTTPException:
        # HTTPException'ı tekrar fırlat
        raise
    except Exception as e:
        print(f"[AUTH ERROR] Giriş hatası: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Giriş işlemi başarısız"
        )


@router.post("/logout", status_code=status.HTTP_200_OK)
def logout(
    current_user: User = Depends(get_current_user)
):
    """
    Kullanıcı çıkışı yapar
    Not: JWT token'lar stateless olduğu için token'ı geçersizleştirmek için
    client-side'da token'ı silmek yeterlidir
    """
    try:
        return {
            "message": "Başarıyla çıkış yapıldı",
            "detail": "Token'ı client-side'da silin"
        }
    except Exception as e:
        print(f"[AUTH ERROR] Çıkış hatası: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Çıkış işlemi başarısız"
        )


@router.get("/me", response_model=UserResponse)
def get_current_user_info(
    current_user: User = Depends(get_current_user)
):
    """
    Mevcut kullanıcı bilgilerini döndürür (token'dan)
    """
    try:
        return UserResponse(
            id=current_user.id,
            username=current_user.username,
            name=current_user.name,
            email=current_user.email,
            created_at=current_user.created_at
        )
    except Exception as e:
        print(f"[AUTH ERROR] Kullanıcı bilgisi alma hatası: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Kullanıcı bilgisi alınamadı"
        )

