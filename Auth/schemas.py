"""
Pydantic şemaları - API request/response validasyonu
Kullanıcı giriş, kayıt ve yanıt şemalarını tanımlar
"""

from pydantic import BaseModel, EmailStr, Field, field_validator
from datetime import datetime
from typing import Optional, List
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


class ChatHistoryCreate(BaseModel):
    """
    Sohbet geçmişi oluşturma şeması - yeni sohbet kaydı için
    
    Attributes:
        user_message: Kullanıcı mesajı
        bot_response: Bot yanıtı
        flow_type: Akış tipi (RAG, ANIMAL, EMOTION, STATS, HELP)
    """
    
    user_message: str = Field(..., min_length=1, description="Kullanıcı mesajı")
    bot_response: str = Field(..., min_length=1, description="Bot yanıtı")
    flow_type: Optional[str] = Field(None, max_length=20, description="Akış tipi")


class ChatHistoryResponse(BaseModel):
    """
    Sohbet mesajı yanıt şeması - API response için
    
    Attributes:
        id: Mesaj ID'si
        conversation_id: Conversation ID'si
        user_message: Kullanıcı mesajı
        bot_response: Bot yanıtı
        flow_type: Akış tipi
        created_at: Mesaj oluşturulma tarihi
    """
    
    id: int = Field(..., description="Mesaj ID'si")
    conversation_id: int = Field(..., description="Conversation ID'si")
    user_message: str = Field(..., description="Kullanıcı mesajı")
    bot_response: str = Field(..., description="Bot yanıtı")
    flow_type: Optional[str] = Field(None, description="Akış tipi")
    created_at: datetime = Field(..., description="Mesaj oluşturulma tarihi")
    
    class Config:
        """Pydantic config - ORM mode aktif"""
        from_attributes = True


class ChatHistoryListResponse(BaseModel):
    """
    Sohbet geçmişi liste yanıt şeması - pagination ile
    
    Attributes:
        total: Toplam kayıt sayısı
        limit: Sayfa başına kayıt sayısı
        offset: Atlanacak kayıt sayısı
        items: Sohbet geçmişi kayıtları listesi
    """
    
    total: int = Field(..., description="Toplam kayıt sayısı")
    limit: int = Field(..., description="Sayfa başına kayıt sayısı")
    offset: int = Field(..., description="Atlanacak kayıt sayısı")
    items: List[ChatHistoryResponse] = Field(..., description="Sohbet geçmişi kayıtları")


class ConversationCreate(BaseModel):
    """
    Conversation oluşturma şeması
    
    Attributes:
        title: Sohbet başlığı (opsiyonel, ilk mesajdan otomatik oluşturulabilir)
    """
    
    title: Optional[str] = Field(None, max_length=200, description="Sohbet başlığı")


class ConversationResponse(BaseModel):
    """
    Conversation yanıt şeması
    
    Attributes:
        id: Conversation ID'si
        user_id: Kullanıcı ID'si
        title: Sohbet başlığı
        created_at: Oluşturulma tarihi
        updated_at: Son güncelleme tarihi
    """
    
    id: int = Field(..., description="Conversation ID'si")
    user_id: int = Field(..., description="Kullanıcı ID'si")
    title: str = Field(..., description="Sohbet başlığı")
    created_at: datetime = Field(..., description="Oluşturulma tarihi")
    updated_at: datetime = Field(..., description="Son güncelleme tarihi")
    
    class Config:
        """Pydantic config - ORM mode aktif"""
        from_attributes = True


class ConversationListResponse(BaseModel):
    """
    Conversation liste yanıt şeması
    
    Attributes:
        items: Conversation listesi
    """
    
    items: List[ConversationResponse] = Field(..., description="Conversation listesi")


class ConversationMessagesResponse(BaseModel):
    """
    Conversation mesajları yanıt şeması
    
    Attributes:
        conversation: Conversation bilgileri
        messages: Mesaj listesi
    """
    
    conversation: ConversationResponse = Field(..., description="Conversation bilgileri")
    messages: List[ChatHistoryResponse] = Field(..., description="Mesaj listesi")
