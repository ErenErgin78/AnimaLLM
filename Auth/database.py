"""
Veritabanı bağlantı ve yönetim modülü
SQLite veritabanı ile çalışır, otomatik tablo oluşturma yapar
"""

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from pathlib import Path
import os

# Auth klasörünü bul
AUTH_DIR = Path(__file__).parent.resolve()

# SQLite veritabanı dosya yolu - Auth/Database klasöründe saklanır
DATABASE_DIR = AUTH_DIR / "Database"
DATABASE_DIR.mkdir(exist_ok=True)  # Klasör yoksa oluştur

# SQLite veritabanı dosya yolu
DATABASE_URL = f"sqlite:///{DATABASE_DIR / 'users.db'}"

# SQLite engine oluştur - connection pooling ve thread safety için ayarlar
# check_same_thread=False: FastAPI async işlemler için gerekli
# echo=False: SQL sorgularını konsola yazdırma (production için)
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},  # SQLite thread safety için
    echo=False  # Debug için True yapılabilir
)

# Session factory oluştur - her request için yeni session
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class - tüm modeller bunu extend edecek
Base = declarative_base()


def get_db():
    """
    Veritabanı session'ı döndürür - dependency injection için kullanılır
    Her request için yeni session oluşturur, işlem bitince kapatır
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        # Her durumda session'ı kapat (exception olsa bile)
        db.close()


def init_db():
    """
    Veritabanı tablolarını oluşturur - ilk çalıştırmada çağrılmalı
    Tüm Base'i extend eden modelleri otomatik oluşturur
    """
    try:
        # Tüm modelleri import et (circular import'u önlemek için)
        from Auth.models import User, Conversation, ChatHistory  # noqa: F401
        
        # Veritabanı migration kontrolü
        db_file = DATABASE_DIR / "users.db"
        if db_file.exists():
            try:
                import sqlite3
                conn = sqlite3.connect(str(db_file))
                cursor = conn.cursor()
                
                # Users tablosu kontrolü
                cursor.execute("PRAGMA table_info(users)")
                user_columns = [row[1] for row in cursor.fetchall()]
                
                # ChatHistory tablosu kontrolü
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='chat_history'")
                chat_history_exists = cursor.fetchone() is not None
                
                chat_history_columns = []
                if chat_history_exists:
                    cursor.execute("PRAGMA table_info(chat_history)")
                    chat_history_columns = [row[1] for row in cursor.fetchall()]
                
                # Conversations tablosu kontrolü
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='conversations'")
                conversations_exists = cursor.fetchone() is not None
                
                conn.close()
                
                # Eski yapı kontrolü - username/name yoksa veya conversation sistemi yoksa
                needs_recreate = False
                
                if 'username' not in user_columns or 'name' not in user_columns:
                    print(f"[DATABASE] Eski users tablosu yapısı tespit edildi")
                    needs_recreate = True
                
                if not conversations_exists:
                    print(f"[DATABASE] Conversations tablosu bulunamadı")
                    needs_recreate = True
                
                if chat_history_exists and 'conversation_id' not in chat_history_columns:
                    print(f"[DATABASE] Eski chat_history tablosu yapısı tespit edildi (conversation_id yok)")
                    needs_recreate = True
                
                if needs_recreate:
                    print(f"[DATABASE] Veritabanı yapısı güncelleniyor...")
                    # Eski tabloları sil
                    conn = sqlite3.connect(str(db_file))
                    cursor = conn.cursor()
                    
                    # Foreign key constraint'leri geçici olarak kapat
                    cursor.execute("PRAGMA foreign_keys = OFF")
                    
                    # Eski tabloları sil
                    if chat_history_exists:
                        cursor.execute("DROP TABLE IF EXISTS chat_history")
                        print(f"[DATABASE] Eski chat_history tablosu silindi")
                    
                    if conversations_exists:
                        cursor.execute("DROP TABLE IF EXISTS conversations")
                        print(f"[DATABASE] Eski conversations tablosu silindi")
                    
                    # Users tablosunu da yeniden oluştur (eğer eski yapıdaysa)
                    if 'username' not in user_columns or 'name' not in user_columns:
                        cursor.execute("DROP TABLE IF EXISTS users")
                        print(f"[DATABASE] Eski users tablosu silindi")
                    
                    conn.commit()
                    conn.close()
                    print(f"[DATABASE] Eski tablolar temizlendi, yeni yapı oluşturulacak")
                    
            except Exception as e:
                # Hata olursa dosyayı yine de sil (güvenli tarafta ol)
                print(f"[DATABASE] Veritabanı kontrolü sırasında hata: {e}, yeniden oluşturuluyor...")
                if db_file.exists():
                    db_file.unlink()
        
        # Tüm tabloları oluştur (yeni yapıyla)
        Base.metadata.create_all(bind=engine)
        print(f"[DATABASE] Veritabanı başlatıldı: {DATABASE_URL}")
        print(f"[DATABASE] Tablolar oluşturuldu (conversations ve chat_history conversation_id ile)")
    except Exception as e:
        print(f"[DATABASE ERROR] Veritabanı başlatma hatası: {e}")
        raise

