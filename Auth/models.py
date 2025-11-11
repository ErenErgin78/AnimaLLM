"""
Kullanıcı veritabanı modeli
SQLAlchemy ORM ile kullanıcı tablosunu tanımlar
"""

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
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


class Conversation(Base):
    """
    Sohbet oturumu modeli - veritabanı tablosu
    Her kullanıcının sohbet oturumlarını saklar (ChatGPT gibi)
    
    Attributes:
        id: Conversation benzersiz ID'si (primary key, auto-increment)
        user_id: Kullanıcı ID'si (foreign key, User tablosuna referans)
        title: Sohbet başlığı (ilk mesajdan otomatik oluşturulur)
        created_at: Oturum oluşturulma tarihi (otomatik, default: şu anki zaman)
        updated_at: Son güncelleme tarihi (otomatik güncellenir)
    """
    
    __tablename__ = "conversations"  # Tablo adı
    
    # Primary key - otomatik artan ID
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    
    # Foreign key - User tablosuna referans
    # ondelete='CASCADE': Kullanıcı silinirse conversation'lar da silinir
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Sohbet başlığı - String(200): İlk mesajdan otomatik oluşturulur
    title = Column(String(200), nullable=False)
    
    # Oluşturulma tarihi - otomatik olarak şu anki zamanı kaydeder
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),  # SQLite için CURRENT_TIMESTAMP
        nullable=False,
        index=True
    )
    
    # Son güncelleme tarihi - her mesaj eklendiğinde güncellenir
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),  # SQLite için CURRENT_TIMESTAMP
        onupdate=func.now(),  # Güncelleme sırasında otomatik güncellenir
        nullable=False,
        index=True
    )
    
    # Relationship - User ile ilişki
    user = relationship("User", backref="conversations")
    
    # Relationship - ChatHistory ile ilişki (bir conversation birden fazla mesaj içerir)
    messages = relationship("ChatHistory", back_populates="conversation", cascade="all, delete-orphan")
    
    def __repr__(self):
        """Conversation objesinin string temsili - debug için"""
        return f"<Conversation(id={self.id}, user_id={self.user_id}, title='{self.title}', created_at='{self.created_at}')>"


class ChatHistory(Base):
    """
    Sohbet mesajı modeli - veritabanı tablosu
    Her conversation içindeki mesajları saklar
    
    Attributes:
        id: Mesaj benzersiz ID'si (primary key, auto-increment)
        conversation_id: Conversation ID'si (foreign key, Conversation tablosuna referans)
        user_message: Kullanıcı mesajı (not null)
        bot_response: Bot yanıtı (not null)
        flow_type: Akış tipi (RAG, ANIMAL, EMOTION, STATS, HELP)
        created_at: Mesaj oluşturulma tarihi (otomatik, default: şu anki zaman)
    """
    
    __tablename__ = "chat_history"  # Tablo adı
    
    # Primary key - otomatik artan ID
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    
    # Foreign key - Conversation tablosuna referans
    # ondelete='CASCADE': Conversation silinirse mesajlar da silinir
    conversation_id = Column(Integer, ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Kullanıcı mesajı - Text tipi (uzun mesajlar için)
    user_message = Column(Text, nullable=False)
    
    # Bot yanıtı - Text tipi (uzun yanıtlar için)
    bot_response = Column(Text, nullable=False)
    
    # Akış tipi - String(20): RAG, ANIMAL, EMOTION, STATS, HELP
    flow_type = Column(String(20), nullable=True, index=True)
    
    # Oluşturulma tarihi - otomatik olarak şu anki zamanı kaydeder
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),  # SQLite için CURRENT_TIMESTAMP
        nullable=False,
        index=True  # Tarih bazlı sorgular için index
    )
    
    # Relationship - Conversation ile ilişki
    conversation = relationship("Conversation", back_populates="messages")
    
    def __repr__(self):
        """Sohbet mesajı objesinin string temsili - debug için"""
        return f"<ChatHistory(id={self.id}, conversation_id={self.conversation_id}, flow_type='{self.flow_type}', created_at='{self.created_at}')>"

