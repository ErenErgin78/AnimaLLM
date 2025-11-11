"""
Conversation servisi
SQLite veritabanında conversation (sohbet oturumu) CRUD işlemleri
"""

from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import desc
from fastapi import HTTPException, status
from Auth.models import Conversation, ChatHistory, User


def create_conversation(
    db: Session,
    user_id: int,
    title: str
) -> Conversation:
    """
    Yeni conversation (sohbet oturumu) oluşturur
    
    Args:
        db: Veritabanı session'ı
        user_id: Kullanıcı ID'si
        title: Sohbet başlığı
    
    Returns:
        Conversation: Oluşturulan conversation
    
    Raises:
        HTTPException: Kullanıcı bulunamazsa veya conversation oluşturulamazsa
    """
    try:
        # Kullanıcıyı kontrol et
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Kullanıcı bulunamadı"
            )
        
        # Başlığı temizle ve kontrol et
        title = title.strip() if title else "Yeni Sohbet"
        if not title:
            title = "Yeni Sohbet"
        
        # Maksimum uzunluk kontrolü
        if len(title) > 200:
            title = title[:200]
        
        # Yeni conversation oluştur
        new_conversation = Conversation(
            user_id=user_id,
            title=title
        )
        
        # Veritabanına kaydet
        db.add(new_conversation)
        db.commit()  # Transaction'ı commit et
        db.refresh(new_conversation)  # Yeni oluşturulan ID'yi al
        
        print(f"[CONVERSATION] Yeni conversation oluşturuldu: user_id={user_id}, title='{title}'")
        return new_conversation
        
    except HTTPException:
        # HTTPException'ı tekrar fırlat
        raise
    except Exception as e:
        # Diğer hatalar için rollback yap
        db.rollback()
        print(f"[CONVERSATION ERROR] Conversation oluşturma hatası: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Conversation oluşturulamadı"
        )


def get_conversations(
    db: Session,
    user_id: int,
    limit: int = 50,
    offset: int = 0
) -> List[Conversation]:
    """
    Kullanıcının conversation'larını getirir (tarihe göre azalan sırada)
    
    Args:
        db: Veritabanı session'ı
        user_id: Kullanıcı ID'si
        limit: Maksimum kayıt sayısı (default: 50)
        offset: Atlanacak kayıt sayısı (pagination için, default: 0)
    
    Returns:
        List[Conversation]: Conversation listesi
    """
    try:
        # SQL injection koruması - SQLAlchemy ORM kullanıldığı için otomatik korunur
        # Kullanıcının conversation'larını getir (tarihe göre azalan sırada)
        conversations = db.query(Conversation)\
            .filter(Conversation.user_id == user_id)\
            .order_by(desc(Conversation.updated_at))\
            .limit(limit)\
            .offset(offset)\
            .all()
        
        return conversations
        
    except Exception as e:
        print(f"[CONVERSATION ERROR] Conversation listesi getirme hatası: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Conversation listesi getirilemedi"
        )


def get_conversation_by_id(
    db: Session,
    conversation_id: int,
    user_id: int
) -> Optional[Conversation]:
    """
    Belirli bir conversation'ı getirir (sadece kendi conversation'larını görebilir)
    
    Args:
        db: Veritabanı session'ı
        conversation_id: Conversation ID'si
        user_id: Kullanıcı ID'si
    
    Returns:
        Optional[Conversation]: Conversation veya None
    """
    try:
        # SQL injection koruması - SQLAlchemy ORM kullanıldığı için otomatik korunur
        conversation = db.query(Conversation)\
            .filter(Conversation.id == conversation_id)\
            .filter(Conversation.user_id == user_id)\
            .first()
        
        return conversation
        
    except Exception as e:
        print(f"[CONVERSATION ERROR] Conversation getirme hatası: {e}")
        return None


def get_conversation_messages(
    db: Session,
    conversation_id: int,
    user_id: int
) -> List[ChatHistory]:
    """
    Conversation'daki mesajları getirir (tarihe göre artan sırada)
    
    Args:
        db: Veritabanı session'ı
        conversation_id: Conversation ID'si
        user_id: Kullanıcı ID'si (yetki kontrolü için)
    
    Returns:
        List[ChatHistory]: Mesaj listesi
    
    Raises:
        HTTPException: Conversation bulunamazsa veya yetki yoksa
    """
    try:
        # Conversation'ı kontrol et ve yetki kontrolü yap
        conversation = get_conversation_by_id(db, conversation_id, user_id)
        if not conversation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation bulunamadı veya yetkiniz yok"
            )
        
        # Mesajları getir (tarihe göre artan sırada - en eski mesajdan başla)
        messages = db.query(ChatHistory)\
            .filter(ChatHistory.conversation_id == conversation_id)\
            .order_by(ChatHistory.created_at.asc())\
            .all()
        
        return messages
        
    except HTTPException:
        # HTTPException'ı tekrar fırlat
        raise
    except Exception as e:
        print(f"[CONVERSATION ERROR] Mesajlar getirme hatası: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Mesajlar getirilemedi"
        )


def add_message_to_conversation(
    db: Session,
    conversation_id: int,
    user_id: int,
    user_message: str,
    bot_response: str,
    flow_type: Optional[str] = None
) -> ChatHistory:
    """
    Conversation'a yeni mesaj ekler
    
    Args:
        db: Veritabanı session'ı
        conversation_id: Conversation ID'si
        user_id: Kullanıcı ID'si (yetki kontrolü için)
        user_message: Kullanıcı mesajı
        bot_response: Bot yanıtı
        flow_type: Akış tipi (RAG, ANIMAL, EMOTION, STATS, HELP)
    
    Returns:
        ChatHistory: Oluşturulan mesaj kaydı
    
    Raises:
        HTTPException: Conversation bulunamazsa veya yetki yoksa
    """
    try:
        # Conversation'ı kontrol et ve yetki kontrolü yap
        conversation = get_conversation_by_id(db, conversation_id, user_id)
        if not conversation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation bulunamadı veya yetkiniz yok"
            )
        
        # Mesajları temizle
        user_message = user_message.strip() if user_message else ""
        bot_response = bot_response.strip() if bot_response else ""
        
        # Boş mesaj kontrolü
        if not user_message or not bot_response:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Mesaj boş olamaz"
            )
        
        # Yeni mesaj kaydı oluştur
        new_message = ChatHistory(
            conversation_id=conversation_id,
            user_message=user_message,
            bot_response=bot_response,
            flow_type=flow_type
        )
        
        # Veritabanına kaydet
        db.add(new_message)
        
        # Conversation'ın updated_at'ini güncelle (onupdate otomatik çalışır ama manuel de güncelleyebiliriz)
        from datetime import datetime
        conversation.updated_at = datetime.utcnow()
        
        db.commit()  # Transaction'ı commit et
        db.refresh(new_message)  # Yeni oluşturulan ID'yi al
        
        print(f"[CONVERSATION] Mesaj eklendi: conversation_id={conversation_id}, flow_type={flow_type}")
        return new_message
        
    except HTTPException:
        # HTTPException'ı tekrar fırlat
        raise
    except Exception as e:
        # Diğer hatalar için rollback yap
        db.rollback()
        print(f"[CONVERSATION ERROR] Mesaj ekleme hatası: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Mesaj eklenemedi"
        )


def delete_conversation(
    db: Session,
    conversation_id: int,
    user_id: int
) -> bool:
    """
    Belirli bir conversation'ı siler (sadece kendi conversation'larını silebilir)
    
    Args:
        db: Veritabanı session'ı
        conversation_id: Silinecek conversation ID'si
        user_id: Kullanıcı ID'si
    
    Returns:
        bool: Silme işlemi başarılı mı?
    
    Raises:
        HTTPException: Conversation bulunamazsa veya yetki yoksa
    """
    try:
        # SQL injection koruması - SQLAlchemy ORM kullanıldığı için otomatik korunur
        # Conversation'ı bul ve kullanıcı kontrolü yap
        conversation = get_conversation_by_id(db, conversation_id, user_id)
        
        if not conversation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation bulunamadı veya yetkiniz yok"
            )
        
        # Conversation'ı sil (cascade ile mesajlar da silinir)
        db.delete(conversation)
        db.commit()
        
        print(f"[CONVERSATION] Conversation silindi: conversation_id={conversation_id}, user_id={user_id}")
        return True
        
    except HTTPException:
        # HTTPException'ı tekrar fırlat
        raise
    except Exception as e:
        # Diğer hatalar için rollback yap
        db.rollback()
        print(f"[CONVERSATION ERROR] Conversation silme hatası: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Conversation silinemedi"
        )


def update_conversation_title(
    db: Session,
    conversation_id: int,
    user_id: int,
    new_title: str
) -> Conversation:
    """
    Conversation başlığını günceller
    
    Args:
        db: Veritabanı session'ı
        conversation_id: Conversation ID'si
        user_id: Kullanıcı ID'si
        new_title: Yeni başlık
    
    Returns:
        Conversation: Güncellenmiş conversation
    
    Raises:
        HTTPException: Conversation bulunamazsa veya yetki yoksa
    """
    try:
        # Conversation'ı bul ve yetki kontrolü yap
        conversation = get_conversation_by_id(db, conversation_id, user_id)
        if not conversation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation bulunamadı veya yetkiniz yok"
            )
        
        # Başlığı temizle ve kontrol et
        new_title = new_title.strip() if new_title else "Yeni Sohbet"
        if not new_title:
            new_title = "Yeni Sohbet"
        
        # Maksimum uzunluk kontrolü
        if len(new_title) > 200:
            new_title = new_title[:200]
        
        # Başlığı güncelle
        conversation.title = new_title
        db.commit()
        db.refresh(conversation)
        
        print(f"[CONVERSATION] Başlık güncellendi: conversation_id={conversation_id}, new_title='{new_title}'")
        return conversation
        
    except HTTPException:
        # HTTPException'ı tekrar fırlat
        raise
    except Exception as e:
        # Diğer hatalar için rollback yap
        db.rollback()
        print(f"[CONVERSATION ERROR] Başlık güncelleme hatası: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Başlık güncellenemedi"
        )

