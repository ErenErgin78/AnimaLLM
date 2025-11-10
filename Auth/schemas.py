"""
Pydantic şemaları - API request/response validasyonu
Kullanıcı giriş, kayıt ve yanıt şemalarını tanımlar
"""

from pydantic import BaseModel, EmailStr, Field, field_validator
from datetime import datetime
from typing import Optional
import re


class UserRegister(BaseModel):
    """
    Kullanıcı kayıt şeması - yeni kullanıcı kaydı için
    
    Attributes:
        username: Kullanıcı adı (unique, min 3 karakter)
        name: Kullanıcının gerçek adı
        email: Kullanıcı e-posta adresi (EmailStr ile validasyon)
        password: Kullanıcı şifresi (min 8 karakter, güvenlik için)
    """
    
    username: str = Field(..., min_length=3, max_length=50, description="Kullanıcı adı (min 3 karakter)")
    name: str = Field(..., min_length=2, max_length=100, description="Kullanıcının gerçek adı")
    email: EmailStr = Field(..., description="Kullanıcı e-posta adresi")
    password: str = Field(..., min_length=8, max_length=100, description="Kullanıcı şifresi (min 8 karakter)")
    
    @field_validator('password')
    @classmethod
    def validate_password(cls, v: str) -> str:
        """
        Şifre validasyonu - güvenlik kontrolleri
        """
        if not v:
            raise ValueError("Şifre boş olamaz")
        
        # SQL injection ve XSS koruması - tehlikeli karakterleri kontrol et
        dangerous_chars = ['<', '>', '"', "'", ';', '--', '/*', '*/']
        for char in dangerous_chars:
            if char in v:
                raise ValueError(f"Şifre güvenlik nedeniyle geçersiz karakter içeriyor")
        
        # Minimum uzunluk kontrolü (Field'da zaten var ama ekstra kontrol)
        if len(v) < 8:
            raise ValueError("Şifre en az 8 karakter olmalıdır")
        
        # Maksimum uzunluk kontrolü
        if len(v) > 100:
            raise ValueError("Şifre en fazla 100 karakter olabilir")
        
        return v
    
    @field_validator('username')
    @classmethod
    def validate_username(cls, v: str) -> str:
        """
        Kullanıcı adı validasyonu - güvenlik kontrolleri
        """
        if not v:
            raise ValueError("Kullanıcı adı boş olamaz")
        
        # SQL injection ve XSS koruması - tehlikeli karakterleri kontrol et
        dangerous_chars = ['<', '>', '"', "'", ';', '--', '/*', '*/', ' ', '@']
        for char in dangerous_chars:
            if char in v:
                raise ValueError("Kullanıcı adı güvenlik nedeniyle geçersiz karakter içeriyor")
        
        # Minimum uzunluk kontrolü
        if len(v) < 3:
            raise ValueError("Kullanıcı adı en az 3 karakter olmalıdır")
        
        # Maksimum uzunluk kontrolü
        if len(v) > 50:
            raise ValueError("Kullanıcı adı en fazla 50 karakter olabilir")
        
        # Sadece harf, rakam ve alt çizgi izin ver
        if not re.match(r'^[a-zA-Z0-9_]+$', v):
            raise ValueError("Kullanıcı adı sadece harf, rakam ve alt çizgi içerebilir")
        
        return v.strip()
    
    @field_validator('name')
    @classmethod
    def validate_name(cls, v: str) -> str:
        """
        İsim validasyonu - güvenlik kontrolleri
        """
        if not v:
            raise ValueError("İsim boş olamaz")
        
        # SQL injection koruması - tehlikeli karakterleri kontrol et
        dangerous_chars = ['<', '>', '"', "'", ';', '--', '/*', '*/']
        for char in dangerous_chars:
            if char in v:
                raise ValueError("İsim güvenlik nedeniyle geçersiz karakter içeriyor")
        
        # Minimum uzunluk kontrolü
        if len(v) < 2:
            raise ValueError("İsim en az 2 karakter olmalıdır")
        
        # Maksimum uzunluk kontrolü
        if len(v) > 100:
            raise ValueError("İsim en fazla 100 karakter olabilir")
        
        return v.strip()
    
    @field_validator('email')
    @classmethod
    def validate_email(cls, v: str) -> str:
        """
        E-posta validasyonu - ek güvenlik kontrolleri
        """
        if not v:
            raise ValueError("E-posta boş olamaz")
        
        # E-posta formatı kontrolü (EmailStr zaten kontrol ediyor ama ekstra güvenlik)
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, v):
            raise ValueError("Geçersiz e-posta formatı")
        
        # SQL injection koruması - tehlikeli karakterleri kontrol et
        dangerous_chars = ['<', '>', '"', "'", ';', '--', '/*', '*/', '(', ')', '{', '}']
        for char in dangerous_chars:
            if char in v:
                raise ValueError("E-posta güvenlik nedeniyle geçersiz karakter içeriyor")
        
        # E-posta uzunluğu kontrolü
        if len(v) > 255:
            raise ValueError("E-posta çok uzun (maksimum 255 karakter)")
        
        return v.lower().strip()  # Küçük harfe çevir ve boşlukları temizle


class UserLogin(BaseModel):
    """
    Kullanıcı giriş şeması - mevcut kullanıcı girişi için
    
    Attributes:
        email: Kullanıcı e-posta adresi
        password: Kullanıcı şifresi
    """
    
    email: EmailStr = Field(..., description="Kullanıcı e-posta adresi")
    password: str = Field(..., min_length=1, max_length=100, description="Kullanıcı şifresi")
    
    @field_validator('email')
    @classmethod
    def validate_email(cls, v: str) -> str:
        """E-posta validasyonu - UserRegister ile aynı"""
        if not v:
            raise ValueError("E-posta boş olamaz")
        
        # SQL injection koruması
        dangerous_chars = ['<', '>', '"', "'", ';', '--', '/*', '*/']
        for char in dangerous_chars:
            if char in v:
                raise ValueError("E-posta güvenlik nedeniyle geçersiz karakter içeriyor")
        
        return v.lower().strip()


class UserResponse(BaseModel):
    """
    Kullanıcı yanıt şeması - API response için
    Şifre bilgisi asla döndürülmez (güvenlik)
    
    Attributes:
        id: Kullanıcı ID'si
        username: Kullanıcı adı
        name: Kullanıcının gerçek adı
        email: Kullanıcı e-posta adresi
        created_at: Kullanıcı kayıt tarihi
    """
    
    id: int = Field(..., description="Kullanıcı ID'si")
    username: str = Field(..., description="Kullanıcı adı")
    name: str = Field(..., description="Kullanıcının gerçek adı")
    email: str = Field(..., description="Kullanıcı e-posta adresi")
    created_at: datetime = Field(..., description="Kullanıcı kayıt tarihi")
    
    class Config:
        """Pydantic config - ORM mode aktif (SQLAlchemy objelerini otomatik parse eder)"""
        from_attributes = True  # Pydantic v2 için (eski: orm_mode = True)


class TokenResponse(BaseModel):
    """
    JWT token yanıt şeması - giriş başarılı olduğunda döner
    
    Attributes:
        access_token: JWT access token
        token_type: Token tipi (genellikle "bearer")
        user: Kullanıcı bilgileri (şifre hariç)
    """
    
    access_token: str = Field(..., description="JWT access token")
    token_type: str = Field(default="bearer", description="Token tipi")
    user: UserResponse = Field(..., description="Kullanıcı bilgileri")

