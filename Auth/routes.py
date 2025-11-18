"""
Auth API route'ları
Kullanıcı kayıt, giriş, çıkış ve profil endpoint'leri
"""

import os
import httpx
from urllib.parse import urlencode
from fastapi import APIRouter, Depends, HTTPException, status, Query, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import func
from Auth.database import get_db, SessionLocal
from Auth.schemas import (
    UserRegister, UserLogin, UserResponse, TokenResponse,
    ChatHistoryCreate, ChatHistoryResponse, ChatHistoryListResponse,
    ConversationCreate, ConversationResponse, ConversationListResponse,
    ConversationMessagesResponse, WorkspaceStateRequest, WorkspaceStateResponse
)
from Auth.auth_service import create_user, authenticate_user, create_access_token
from Auth.dependencies import get_current_user
from Auth.models import User
from Auth.conversation_service import (
    create_conversation, get_conversations, get_conversation_by_id,
    get_conversation_messages, add_message_to_conversation,
    delete_conversation, update_conversation_title
)
from Auth.workspace_service import get_workspace_state, upsert_workspace_state
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv()

# Router oluştur - tüm auth endpoint'leri burada
router = APIRouter(prefix="/auth", tags=["Authentication"])


async def call_n8n_webhook(user_data: dict):
    """
    n8n webhook'larını GET request ile çağırır - hem /webhook-test/ hem de /webhook/ endpoint'lerine istek gönderir
    Kullanıcı kayıt bilgilerini ve toplam kullanıcı sayısını query parametreleri olarak gönderir
    """
    db = None
    try:
        # .env dosyasından webhook UUID'sini al
        webhook_uuid = os.getenv("N8N_WEBHOOK")
        if not webhook_uuid:
            print("[N8N WEBHOOK] N8N_WEBHOOK değişkeni .env dosyasında tanımlı değil, webhook çağrısı atlanıyor")
            return
        
        # UUID'yi temizle (boşlukları kaldır)
        webhook_uuid = webhook_uuid.strip()
        
        # Veritabanından toplam kullanıcı sayısını al
        try:
            db = SessionLocal()
            total_users = db.query(func.count(User.id)).scalar() or 0
        except Exception as e:
            print(f"[N8N WEBHOOK] Toplam kullanıcı sayısı alınamadı: {e}")
            total_users = 0
        finally:
            if db:
                db.close()
        
        # Query parametrelerini hazırla - None değerleri filtrele ve string'e çevir
        params = {k: str(v) for k, v in user_data.items() if v is not None}
        # Toplam kullanıcı sayısını ekle
        params["total_users"] = str(total_users)
        
        # Query string'i oluştur
        query_string = urlencode(params) if params else ""
        
        # İki webhook URL'i oluştur
        base_url = "http://localhost:5678"
        webhook_urls = [
            f"{base_url}/webhook-test/{webhook_uuid}",
            f"{base_url}/webhook/{webhook_uuid}"
        ]
        
        # Her iki URL'e de GET isteği gönder
        async with httpx.AsyncClient(timeout=10.0) as client:
            for webhook_url in webhook_urls:
                try:
                    # URL'e query parametrelerini ekle
                    if query_string:
                        full_url = f"{webhook_url}?{query_string}"
                    else:
                        full_url = webhook_url
                    
                    response = await client.get(full_url)
                    response.raise_for_status()
                    print(f"[N8N WEBHOOK] {webhook_url} başarıyla çağrıldı: {response.status_code}")
                
                except httpx.TimeoutException:
                    print(f"[N8N WEBHOOK] {webhook_url} çağrısı timeout oldu (10 saniye)")
                except httpx.HTTPStatusError as e:
                    print(f"[N8N WEBHOOK] {webhook_url} HTTP hatası: {e.response.status_code} - {e.response.text}")
                except Exception as e:
                    print(f"[N8N WEBHOOK] {webhook_url} çağrısı hatası: {e}")
    
    except Exception as e:
        print(f"[N8N WEBHOOK] Webhook çağrısı genel hatası: {e}")
    finally:
        # Veritabanı bağlantısını kapat (eğer açıksa)
        if db:
            try:
                db.close()
            except Exception:
                pass


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    user_data: UserRegister,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Yeni kullanıcı kaydı oluşturur ve n8n webhook'unu tetikler
    """
    try:
        # Yeni kullanıcı oluştur
        new_user = create_user(db, user_data)
        
        # Webhook için kullanıcı bilgilerini hazırla (şifre hariç)
        webhook_data = {
            "id": new_user.id,
            "username": new_user.username,
            "name": new_user.name,
            "email": new_user.email,
            "created_at": new_user.created_at.isoformat() if new_user.created_at else None
        }
        
        # n8n webhook'unu background task olarak çağır (non-blocking)
        background_tasks.add_task(call_n8n_webhook, webhook_data)
        
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
        # JWT standardında "sub" (subject) user_id'yi temsil eder - string olmalı
        token_data = {
            "sub": str(user.id),  # JWT standardına uygun olarak string'e çevir
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


# =============================================================================
# CHAT HISTORY ENDPOINTS - Sohbet Geçmişi API'leri
# =============================================================================

@router.post("/chat-history", response_model=ChatHistoryResponse, status_code=status.HTTP_201_CREATED)
def create_chat_history_endpoint(
    chat_data: ChatHistoryCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Yeni sohbet geçmişi kaydı oluşturur
    """
    try:
        # Sohbet kaydı oluştur
        new_chat = create_chat_history(
            db=db,
            user_id=current_user.id,
            user_message=chat_data.user_message,
            bot_response=chat_data.bot_response,
            flow_type=chat_data.flow_type
        )
        
        # Response döndür
        return ChatHistoryResponse(
            id=new_chat.id,
            user_id=new_chat.user_id,
            user_message=new_chat.user_message,
            bot_response=new_chat.bot_response,
            flow_type=new_chat.flow_type,
            created_at=new_chat.created_at
        )
        
    except HTTPException:
        # HTTPException'ı tekrar fırlat
        raise
    except Exception as e:
        print(f"[CHAT HISTORY ERROR] Sohbet kaydı oluşturma hatası: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Sohbet kaydı oluşturulamadı"
        )


@router.get("/chat-history", response_model=ChatHistoryListResponse)
def get_chat_history_endpoint(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    limit: int = Query(50, ge=1, le=100, description="Sayfa başına kayıt sayısı"),
    offset: int = Query(0, ge=0, description="Atlanacak kayıt sayısı")
):
    """
    Kullanıcının sohbet geçmişini getirir (pagination ile)
    """
    try:
        # Sohbet geçmişini getir
        chat_items = get_chat_history(
            db=db,
            user_id=current_user.id,
            limit=limit,
            offset=offset
        )
        
        # Toplam kayıt sayısını getir
        total = get_chat_history_count(db=db, user_id=current_user.id)
        
        # Response listesi oluştur
        items = [
            ChatHistoryResponse(
                id=item.id,
                user_id=item.user_id,
                user_message=item.user_message,
                bot_response=item.bot_response,
                flow_type=item.flow_type,
                created_at=item.created_at
            )
            for item in chat_items
        ]
        
        # Response döndür
        return ChatHistoryListResponse(
            total=total,
            limit=limit,
            offset=offset,
            items=items
        )
        
    except Exception as e:
        print(f"[CHAT HISTORY ERROR] Sohbet geçmişi getirme hatası: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Sohbet geçmişi getirilemedi"
        )


@router.delete("/chat-history/{chat_id}", status_code=status.HTTP_200_OK)
def delete_chat_history_endpoint(
    chat_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Belirli bir sohbet kaydını siler (sadece kendi kayıtlarını silebilir)
    """
    try:
        # Sohbet kaydını sil
        success = delete_chat_history(
            db=db,
            user_id=current_user.id,
            chat_id=chat_id
        )
        
        if success:
            return {"message": "Sohbet kaydı başarıyla silindi"}
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Sohbet kaydı bulunamadı"
            )
        
    except HTTPException:
        # HTTPException'ı tekrar fırlat
        raise
    except Exception as e:
        print(f"[CHAT HISTORY ERROR] Sohbet kaydı silme hatası: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Sohbet kaydı silinemedi"
        )


@router.delete("/chat-history", status_code=status.HTTP_200_OK)
def delete_all_chat_history_endpoint(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Kullanıcının tüm sohbet geçmişini siler
    """
    try:
        # Tüm sohbet geçmişini sil
        deleted_count = delete_all_chat_history(
            db=db,
            user_id=current_user.id
        )
        
        return {
            "message": "Tüm sohbet geçmişi başarıyla silindi",
            "deleted_count": deleted_count
        }
        
    except Exception as e:
        print(f"[CHAT HISTORY ERROR] Tüm sohbet geçmişi silme hatası: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Sohbet geçmişi silinemedi"
        )


# =============================================================================
# CONVERSATION ENDPOINTS - ChatGPT Tarzı Sohbet Oturumları
# =============================================================================

@router.post("/conversations", response_model=ConversationResponse, status_code=status.HTTP_201_CREATED)
def create_conversation_endpoint(
    conversation_data: ConversationCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Yeni conversation (sohbet oturumu) oluşturur
    """
    try:
        # Başlık belirtilmemişse varsayılan başlık kullan
        title = conversation_data.title if conversation_data.title else "Yeni Sohbet"
        
        # Conversation oluştur
        new_conversation = create_conversation(
            db=db,
            user_id=current_user.id,
            title=title
        )
        
        # Response döndür
        return ConversationResponse(
            id=new_conversation.id,
            user_id=new_conversation.user_id,
            title=new_conversation.title,
            created_at=new_conversation.created_at,
            updated_at=new_conversation.updated_at
        )
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"[CONVERSATION ERROR] Conversation oluşturma hatası: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Conversation oluşturulamadı"
        )


@router.get("/conversations", response_model=ConversationListResponse)
def get_conversations_endpoint(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    limit: int = Query(50, ge=1, le=100, description="Maksimum kayıt sayısı"),
    offset: int = Query(0, ge=0, description="Atlanacak kayıt sayısı")
):
    """
    Kullanıcının conversation'larını getirir (tarihe göre azalan sırada)
    """
    try:
        # Conversation'ları getir
        conversations = get_conversations(
            db=db,
            user_id=current_user.id,
            limit=limit,
            offset=offset
        )
        
        # Response listesi oluştur
        items = [
            ConversationResponse(
                id=conv.id,
                user_id=conv.user_id,
                title=conv.title,
                created_at=conv.created_at,
                updated_at=conv.updated_at
            )
            for conv in conversations
        ]
        
        # Response döndür
        return ConversationListResponse(items=items)
        
    except Exception as e:
        print(f"[CONVERSATION ERROR] Conversation listesi getirme hatası: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Conversation listesi getirilemedi"
        )


@router.get("/workspace/state", response_model=WorkspaceStateResponse, status_code=status.HTTP_200_OK)
def get_workspace_state_endpoint(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Kullanıcının son kaydettiği çalışma alanı durumunu döndürür"""
    # Kayıt varsa doğrudan döndür, yoksa varsayılan boş ayar yolla
    state = get_workspace_state(db, current_user.id)
    if state:
        return WorkspaceStateResponse(
            layout_json=state.layout_json,
            matrix_json=state.matrix_json,
            theme=state.theme,
            updated_at=state.updated_at
        )
    now = datetime.now(timezone.utc)
    return WorkspaceStateResponse(
        layout_json="{}",
        matrix_json=None,
        theme=None,
        updated_at=now
    )


@router.post("/workspace/state", response_model=WorkspaceStateResponse, status_code=status.HTTP_200_OK)
def upsert_workspace_state_endpoint(
    payload: WorkspaceStateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Kullanıcının çalışma alanı ayarını kaydeder"""
    state = upsert_workspace_state(
        db=db,
        user_id=current_user.id,
        layout_json=payload.layout_json,
        matrix_json=payload.matrix_json,
        theme=payload.theme
    )
    return WorkspaceStateResponse(
        layout_json=state.layout_json,
        matrix_json=state.matrix_json,
        theme=state.theme,
        updated_at=state.updated_at
    )


@router.get("/conversations/{conversation_id}/messages", response_model=ConversationMessagesResponse)
def get_conversation_messages_endpoint(
    conversation_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Conversation'daki mesajları getirir
    """
    try:
        # Conversation'ı getir
        conversation = get_conversation_by_id(db, conversation_id, current_user.id)
        if not conversation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation bulunamadı veya yetkiniz yok"
            )
        
        # Mesajları getir
        messages = get_conversation_messages(db, conversation_id, current_user.id)
        
        # Response oluştur
        conversation_response = ConversationResponse(
            id=conversation.id,
            user_id=conversation.user_id,
            title=conversation.title,
            created_at=conversation.created_at,
            updated_at=conversation.updated_at
        )
        
        messages_response = [
            ChatHistoryResponse(
                id=msg.id,
                conversation_id=msg.conversation_id,
                user_message=msg.user_message,
                bot_response=msg.bot_response,
                flow_type=msg.flow_type,
                created_at=msg.created_at
            )
            for msg in messages
        ]
        
        return ConversationMessagesResponse(
            conversation=conversation_response,
            messages=messages_response
        )
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"[CONVERSATION ERROR] Mesajlar getirme hatası: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Mesajlar getirilemedi"
        )


@router.post("/conversations/{conversation_id}/messages", response_model=ChatHistoryResponse, status_code=status.HTTP_201_CREATED)
def add_message_to_conversation_endpoint(
    conversation_id: int,
    chat_data: ChatHistoryCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Conversation'a yeni mesaj ekler
    """
    try:
        # Mesaj ekle
        new_message = add_message_to_conversation(
            db=db,
            conversation_id=conversation_id,
            user_id=current_user.id,
            user_message=chat_data.user_message,
            bot_response=chat_data.bot_response,
            flow_type=chat_data.flow_type
        )
        
        # Response döndür
        return ChatHistoryResponse(
            id=new_message.id,
            conversation_id=new_message.conversation_id,
            user_message=new_message.user_message,
            bot_response=new_message.bot_response,
            flow_type=new_message.flow_type,
            created_at=new_message.created_at
        )
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"[CONVERSATION ERROR] Mesaj ekleme hatası: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Mesaj eklenemedi"
        )


@router.delete("/conversations/{conversation_id}", status_code=status.HTTP_200_OK)
def delete_conversation_endpoint(
    conversation_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Belirli bir conversation'ı siler (sadece kendi conversation'larını silebilir)
    """
    try:
        # Conversation'ı sil
        success = delete_conversation(
            db=db,
            conversation_id=conversation_id,
            user_id=current_user.id
        )
        
        if success:
            return {"message": "Conversation başarıyla silindi"}
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation bulunamadı"
            )
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"[CONVERSATION ERROR] Conversation silme hatası: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Conversation silinemedi"
        )


@router.patch("/conversations/{conversation_id}/title", response_model=ConversationResponse)
def update_conversation_title_endpoint(
    conversation_id: int,
    title_data: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Conversation başlığını günceller
    """
    try:
        new_title = title_data.get("title", "")
        if not new_title:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Başlık boş olamaz"
            )
        
        # Başlığı güncelle
        updated_conversation = update_conversation_title(
            db=db,
            conversation_id=conversation_id,
            user_id=current_user.id,
            new_title=new_title
        )
        
        # Response döndür
        return ConversationResponse(
            id=updated_conversation.id,
            user_id=updated_conversation.user_id,
            title=updated_conversation.title,
            created_at=updated_conversation.created_at,
            updated_at=updated_conversation.updated_at
        )
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"[CONVERSATION ERROR] Başlık güncelleme hatası: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Başlık güncellenemedi"
        )

