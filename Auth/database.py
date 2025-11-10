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
        from Auth.models import User  # noqa: F401
        
        # Eski veritabanı dosyasını sil (eğer varsa ve yapı uyumsuzsa)
        db_file = DATABASE_DIR / "users.db"
        if db_file.exists():
            try:
                # Mevcut tablo yapısını kontrol et
                import sqlite3
                conn = sqlite3.connect(str(db_file))
                cursor = conn.cursor()
                cursor.execute("PRAGMA table_info(users)")
                columns = [row[1] for row in cursor.fetchall()]
                conn.close()
                
                # username veya name kolonları yoksa eski veritabanını sil
                if 'username' not in columns or 'name' not in columns:
                    print(f"[DATABASE] Eski veritabanı yapısı tespit edildi, yeniden oluşturuluyor...")
                    db_file.unlink()  # Dosyayı sil
                    print(f"[DATABASE] Eski veritabanı dosyası silindi")
            except Exception as e:
                # Hata olursa dosyayı yine de sil (güvenli tarafta ol)
                print(f"[DATABASE] Veritabanı kontrolü sırasında hata: {e}, yeniden oluşturuluyor...")
                if db_file.exists():
                    db_file.unlink()
        
        # Tüm tabloları oluştur (yeni yapıyla)
        Base.metadata.create_all(bind=engine)
        print(f"[DATABASE] Veritabanı başlatıldı: {DATABASE_URL}")
        print(f"[DATABASE] Tablolar oluşturuldu (username ve name kolonları dahil)")
    except Exception as e:
        print(f"[DATABASE ERROR] Veritabanı başlatma hatası: {e}")
        raise

