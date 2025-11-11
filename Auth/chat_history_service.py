"""
Sohbet geçmişi servisi
SQLite veritabanında sohbet geçmişi CRUD işlemleri
"""

from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import desc
from fastapi import HTTPException, status
from Auth.models import ChatHistory, User


def create_chat_history(
    db: Session,
    user_id: int,
    user_message: str,
    bot_response: str,
    flow_type: Optional[str] = None
) -> ChatHistory:
    """
    Yeni sohbet geçmişi kaydı oluşturur
    
    Args:
        db: Veritabanı session'ı
        user_id: Kullanıcı ID'si
        user_message: Kullanıcı mesajı
        bot_response: Bot yanıtı
        flow_type: Akış tipi (RAG, ANIMAL, EMOTION, STATS, HELP)
    
    Returns:
        ChatHistory: Oluşturulan sohbet kaydı
    
    Raises:
        HTTPException: Kullanıcı bulunamazsa veya kayıt oluşturulamazsa
    """
    try:
        # Kullanıcıyı kontrol et
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Kullanıcı bulunamadı"
            )
        
        # SQL injection koruması - SQLAlchemy ORM kullanıldığı için otomatik korunur
        # Mesajları temizle (boşlukları temizle)
        user_message = user_message.strip() if user_message else ""
        bot_response = bot_response.strip() if bot_response else ""
        
        # Boş mesaj kontrolü
        if not user_message or not bot_response:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Mesaj boş olamaz"
            )
        
        # Yeni sohbet kaydı oluştur
        new_chat = ChatHistory(
            user_id=user_id,
            user_message=user_message,
            bot_response=bot_response,
            flow_type=flow_type
        )
        
        # Veritabanına kaydet
        db.add(new_chat)
        db.commit()  # Transaction'ı commit et
        db.refresh(new_chat)  # Yeni oluşturulan ID'yi al
        
        print(f"[CHAT HISTORY] Yeni sohbet kaydı oluşturuldu: user_id={user_id}, flow_type={flow_type}")
        return new_chat
        
    except HTTPException:
        # HTTPException'ı tekrar fırlat
        raise
    except Exception as e:
        # Diğer hatalar için rollback yap
        db.rollback()
        print(f"[CHAT HISTORY ERROR] Sohbet kaydı oluşturma hatası: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Sohbet kaydı oluşturulamadı"
        )


def get_chat_history(
    db: Session,
    user_id: int,
    limit: int = 50,
    offset: int = 0
) -> List[ChatHistory]:
    """
    Kullanıcının sohbet geçmişini getirir (tarihe göre azalan sırada)
    
    Args:
        db: Veritabanı session'ı
        user_id: Kullanıcı ID'si
        limit: Maksimum kayıt sayısı (default: 50)
        offset: Atlanacak kayıt sayısı (pagination için, default: 0)
    
    Returns:
        List[ChatHistory]: Sohbet geçmişi kayıtları listesi
    """
    try:
        # SQL injection koruması - SQLAlchemy ORM kullanıldığı için otomatik korunur
        # Kullanıcının sohbet geçmişini getir (tarihe göre azalan sırada)
        chat_history = db.query(ChatHistory)\
            .filter(ChatHistory.user_id == user_id)\
            .order_by(desc(ChatHistory.created_at))\
            .limit(limit)\
            .offset(offset)\
            .all()
        
        return chat_history
        
    except Exception as e:
        print(f"[CHAT HISTORY ERROR] Sohbet geçmişi getirme hatası: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Sohbet geçmişi getirilemedi"
        )


def get_chat_history_count(db: Session, user_id: int) -> int:
    """
    Kullanıcının toplam sohbet kayıt sayısını döndürür
    
    Args:
        db: Veritabanı session'ı
        user_id: Kullanıcı ID'si
    
    Returns:
        int: Toplam kayıt sayısı
    """
    try:
        # SQL injection koruması - SQLAlchemy ORM kullanıldığı için otomatik korunur
        count = db.query(ChatHistory)\
            .filter(ChatHistory.user_id == user_id)\
            .count()
        
        return count
        
    except Exception as e:
        print(f"[CHAT HISTORY ERROR] Sohbet kayıt sayısı getirme hatası: {e}")
        return 0


def delete_chat_history(db: Session, user_id: int, chat_id: int) -> bool:
    """
    Belirli bir sohbet kaydını siler (sadece kendi kayıtlarını silebilir)
    
    Args:
        db: Veritabanı session'ı
        user_id: Kullanıcı ID'si
        chat_id: Silinecek sohbet kaydı ID'si
    
    Returns:
        bool: Silme işlemi başarılı mı?
    
    Raises:
        HTTPException: Kayıt bulunamazsa veya yetki yoksa
    """
    try:
        # SQL injection koruması - SQLAlchemy ORM kullanıldığı için otomatik korunur
        # Kaydı bul ve kullanıcı kontrolü yap
        chat = db.query(ChatHistory)\
            .filter(ChatHistory.id == chat_id)\
            .filter(ChatHistory.user_id == user_id)\
            .first()
        
        if not chat:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Sohbet kaydı bulunamadı veya yetkiniz yok"
            )
        
        # Kaydı sil
        db.delete(chat)
        db.commit()
        
        print(f"[CHAT HISTORY] Sohbet kaydı silindi: chat_id={chat_id}, user_id={user_id}")
        return True
        
    except HTTPException:
        # HTTPException'ı tekrar fırlat
        raise
    except Exception as e:
        # Diğer hatalar için rollback yap
        db.rollback()
        print(f"[CHAT HISTORY ERROR] Sohbet kaydı silme hatası: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Sohbet kaydı silinemedi"
        )


def delete_all_chat_history(db: Session, user_id: int) -> int:
    """
    Kullanıcının tüm sohbet geçmişini siler
    
    Args:
        db: Veritabanı session'ı
        user_id: Kullanıcı ID'si
    
    Returns:
        int: Silinen kayıt sayısı
    """
    try:
        # SQL injection koruması - SQLAlchemy ORM kullanıldığı için otomatik korunur
        # Kullanıcının tüm kayıtlarını bul ve sil
        deleted_count = db.query(ChatHistory)\
            .filter(ChatHistory.user_id == user_id)\
            .delete()
        
        db.commit()
        
        print(f"[CHAT HISTORY] Tüm sohbet geçmişi silindi: user_id={user_id}, deleted_count={deleted_count}")
        return deleted_count
        
    except Exception as e:
        # Hata durumunda rollback yap
        db.rollback()
        print(f"[CHAT HISTORY ERROR] Tüm sohbet geçmişi silme hatası: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Sohbet geçmişi silinemedi"
        )

