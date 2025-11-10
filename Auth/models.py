"""
Kullanıcı veritabanı modeli
SQLAlchemy ORM ile kullanıcı tablosunu tanımlar
"""

from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.sql import func
from Auth.database import Base


class User(Base):
    """
    Kullanıcı modeli - veritabanı tablosu
    
    Attributes:
        id: Kullanıcı benzersiz ID'si (primary key, auto-increment)
        email: Kullanıcı e-posta adresi (unique, not null)
        hashed_password: Hashlenmiş şifre (bcrypt ile hashlenmiş, not null)
        created_at: Kullanıcı kayıt tarihi (otomatik, default: şu anki zaman)
    """
    
    __tablename__ = "users"  # Tablo adı
    
    # Primary key - otomatik artan ID
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    
    # Kullanıcı adı - unique ve index'li (hızlı arama için)
    # String(50): Maksimum 50 karakter (kullanıcı adı için yeterli)
    username = Column(String(50), unique=True, index=True, nullable=False)
    
    # İsim - kullanıcının gerçek adı
    # String(100): Maksimum 100 karakter (isim için yeterli)
    name = Column(String(100), nullable=False)
    
    # E-posta adresi - unique ve index'li (hızlı arama için)
    # String(255): Maksimum 255 karakter (e-posta için yeterli)
    email = Column(String(255), unique=True, index=True, nullable=False)
    
    # Hashlenmiş şifre - bcrypt ile hashlenmiş şifre
    # String(255): bcrypt hash'i için yeterli uzunluk
    hashed_password = Column(String(255), nullable=False)
    
    # Oluşturulma tarihi - otomatik olarak şu anki zamanı kaydeder
    # server_default: Veritabanı seviyesinde default değer
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),  # SQLite için CURRENT_TIMESTAMP
        nullable=False
    )
    
    def __repr__(self):
        """Kullanıcı objesinin string temsili - debug için"""
        return f"<User(id={self.id}, username='{self.username}', email='{self.email}', created_at='{self.created_at}')>"

