"""
Kullanıcı çalışma alanı servis fonksiyonları
- Node yerleşimlerini ve tema ayarlarını kaydeder
- Kullanıcı giriş yaptığında son kaydı döndürür
"""

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from fastapi import HTTPException, status
from typing import Optional

from Auth.models import UserWorkspaceState, User


def get_workspace_state(db: Session, user_id: int) -> Optional[UserWorkspaceState]:
    """Kullanıcının kayıtlı çalışma alanını getirir"""
    # Kullanıcının çalışma alanı satırını tek sorguda çek
    return db.query(UserWorkspaceState).filter(UserWorkspaceState.user_id == user_id).first()


def upsert_workspace_state(
    db: Session,
    user_id: int,
    layout_json: str,
    matrix_json: Optional[str],
    theme: Optional[str]
) -> UserWorkspaceState:
    """Kullanıcının çalışma alanı kaydını günceller veya oluşturur"""
    try:
        # Kullanıcının varlığını doğrula
        user_exists = db.query(User.id).filter(User.id == user_id).first()
        if not user_exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Kullanıcı bulunamadı"
            )

        # Mevcut kayıt varsa güncelle, yoksa oluştur
        state = get_workspace_state(db, user_id)
        if state:
            state.layout_json = layout_json
            state.matrix_json = matrix_json
            state.theme = theme
        else:
            # Yeni tablo kaydı ekle
            state = UserWorkspaceState(
                user_id=user_id,
                layout_json=layout_json,
                matrix_json=matrix_json,
                theme=theme
            )
            db.add(state)

        # Değişiklikleri veritabanına yaz
        db.commit()
        db.refresh(state)
        return state
    except HTTPException:
        raise
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Çalışma alanı kaydı yapılamadı: {exc}"
        )

