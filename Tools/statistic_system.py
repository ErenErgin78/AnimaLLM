"""
İstatistik Sistemi
==================

Bu modül, duygu istatistik sorgularını (today/all ve isteğe bağlı emotion filtresi)
`data/` altındaki kalıcı dosyaları okuyarak hesaplar ve doğal dilde özet üretir.

Güvenlik/sağlamlık notları:
- Dosya okuma try/except ile korunur.
- Kullanıcı mesajı regex ile güvenli biçimde ayrıştırılır (komut enjekte edilmez).
- Hatalarda kullanıcıya sade ve zararsız bir mesaj döner.
"""

from __future__ import annotations

import re
from typing import Any, Dict, Optional, Tuple
from datetime import datetime

from sqlalchemy import func
from sqlalchemy.orm import Session

from Auth.database import get_db
from Auth.models import EmotionLog


class StatisticSystem:
    """Duygu istatistik sistemi - dosyalardan okuyup özet üretir."""

    def __init__(self) -> None:
        # Desteklenen duygular (Emotion sistemi ile uyumlu)
        self.allowed_moods = [
            "Mutlu", "Üzgün", "Öfkeli", "Şaşkın", "Utanmış",
            "Endişeli", "Gülümseyen", "Flörtöz", "Sorgulayıcı", "Yorgun"
        ]

    # -------------------------- Yardımcılar -------------------------- #
    def _normalize_emotion(self, name: str | None) -> Optional[str]:
        if not name:
            return None
        n = str(name).strip().lower()
        for m in self.allowed_moods:
            if m.lower() == n:
                return m
        return None

    def _detect_period_and_emotion(self, user_message: str) -> Tuple[str, Optional[str]]:
        """Mesajdan period (today/all) ve isteğe bağlı emotion’u çıkartır.
        Basit bir regex/keyword yaklaşımı; gerekirse LLM üstünden geliştirilebilir.
        """
        t = (user_message or "").lower()

        # period
        period = "today" if any(k in t for k in ["bugün", "today", "günlük"]) else "all"

        # emotion (desteklenenlerden biri geçiyorsa al)
        detected_emotion: Optional[str] = None
        for m in self.allowed_moods:
            if m.lower() in t:
                detected_emotion = m
                break

        # get_emotion_stats(...) düz metin döndüyse parametreleri yakala (opsiyonel)
        try:
            m1 = re.search(r'get_emotion_stats\(\s*emotion\s*=\s*"([^"]+)"\s*(?:,\s*period\s*=\s*"(today|all)")?\s*\)', t, re.IGNORECASE)
            m2 = re.search(r'get_emotion_stats\(\s*period\s*=\s*"(today|all)"\s*(?:,\s*emotion\s*=\s*"([^"]+)")?\s*\)', t, re.IGNORECASE)
            if m1:
                detected_emotion = self._normalize_emotion(m1.group(1)) or detected_emotion
                period = (m1.group(2) or period) if len(m1.groups()) >= 2 else period
            elif m2:
                period = m2.group(1) or period
                e2 = m2.group(2) if len(m2.groups()) >= 2 else None
                if e2:
                    detected_emotion = self._normalize_emotion(e2) or detected_emotion
        except Exception:
            pass

        return period, detected_emotion

    # -------------------------- Hesaplama --------------------------- #
    def _get_session(self) -> Optional[Session]:
        """Yeni bir veritabanı session'ı oluşturur"""
        try:
            return next(get_db())
        except Exception as e:
            print(f"[STATS] DB bağlantısı oluşturulamadı: {e}")
            return None
    
    def _build_base_query(self, session: Session, user_id: int, period: str = "all"):
        """Temel EmotionLog sorgusunu hazırlar"""
        query = session.query(EmotionLog).filter(EmotionLog.user_id == user_id)
        
        if period == "today":
            start_of_day = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            query = query.filter(EmotionLog.created_at >= start_of_day)
        
        return query
    
    def _read_counts_from_db(self, session: Session, user_id: int, period: str = "all") -> Dict[str, int]:
        """SQLite veritabanından duygu sayılarını okur"""
        counts: Dict[str, int] = {m: 0 for m in self.allowed_moods}
        
        try:
            query = session.query(
                EmotionLog.mood,
                func.count(EmotionLog.id)
            ).filter(EmotionLog.user_id == user_id)
            
            if period == "today":
                start_of_day = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
                query = query.filter(EmotionLog.created_at >= start_of_day)
            
            query = query.group_by(EmotionLog.mood)
            
            for mood, count in query.all():
                if mood in counts:
                    counts[mood] = int(count)
            
        except Exception as e:
            print(f"[STATS] Duygu sayısı okuma hatası (DB): {e}")
        
        return counts
    
    def _read_logs_for_period(self, session: Session, user_id: int, period: str = "all"):
        """Belirtilen period için EmotionLog kayıtlarını döndürür"""
        query = self._build_base_query(session, user_id, period)
        return query.order_by(EmotionLog.created_at.asc()).all()

    def _get_top_moods(self, counts: Dict[str, int], top_n: int = 3, reverse: bool = True) -> list[Tuple[str, int]]:
        """En çok/az görülen duyguları döndürür (top N)"""
        try:
            # Sadece 0'dan büyük değerleri filtrele ve sırala
            filtered = [(mood, count) for mood, count in counts.items() if count > 0]
            sorted_moods = sorted(filtered, key=lambda x: x[1], reverse=reverse)
            return sorted_moods[:top_n]
        except Exception:
            return []

    def _get_first_last_timestamps(self, session: Session, user_id: int, period: str = "all") -> Tuple[Optional[str], Optional[str]]:
        """İlk ve son kayıt tarihlerini döndürür"""
        try:
            query = self._build_base_query(session, user_id, period)
            
            first = query.order_by(EmotionLog.created_at.asc()).limit(1).first()
            last = query.order_by(EmotionLog.created_at.desc()).limit(1).first()
            
            if not first or not last:
                return None, None
            
            first_ts = first.created_at.strftime("%Y-%m-%d %H:%M:%S") if first.created_at else None
            last_ts = last.created_at.strftime("%Y-%m-%d %H:%M:%S") if last.created_at else None
            return first_ts, last_ts
        except Exception as e:
            print(f"[STATS] İlk/son tarih okuma hatası: {e}")
            return None, None

    def _calculate_average_daily_mood_count(self, session: Session, user_id: int, period: str = "all") -> float:
        """Ortalama günlük duygu sayısını hesaplar"""
        try:
            date_format = "%Y-%m-%d"
            
            date_expr = func.strftime("%Y-%m-%d", EmotionLog.created_at)
            
            query = session.query(
                date_expr.label("log_date"),
                func.count(EmotionLog.id).label("count")
            ).filter(EmotionLog.user_id == user_id)
            
            if period == "today":
                start_of_day = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
                query = query.filter(EmotionLog.created_at >= start_of_day)
            
            query = query.group_by("log_date")
            results = query.all()
            
            if not results:
                return 0.0
            
            total_records = sum(int(row.count) for row in results)
            total_days = len(results)
            return round(total_records / total_days, 2) if total_days > 0 else 0.0
        except Exception as e:
            print(f"[STATS] Ortalama günlük sayı hesaplama hatası: {e}")
            return 0.0

    def compute_stats(self, user_id: int, period: str = "all", emotion: Optional[str] = None) -> Dict[str, Any]:
        """İstatistik hesapla ve özet üret - detaylı bilgilerle"""
        if not user_id:
            return {
                "counts": {m: 0 for m in self.allowed_moods},
                "summary": "Duygu istatistiklerini görebilmek için lütfen giriş yapın.",
                "period": period,
                "total_records": 0
            }
        
        session = self._get_session()
        if session is None:
            return {
                "counts": {m: 0 for m in self.allowed_moods},
                "summary": "İstatistikler alınamadı (veritabanı bağlantısı kurulamadı).",
                "period": period,
                "total_records": 0
            }
        
        period_norm = (period or "all").lower()
        if period_norm not in ("all", "today"):
            period_norm = "all"

        try:
            counts = self._read_counts_from_db(session, user_id, period_norm)

            # İsteğe bağlı tek duygu filtresi
            emo_norm = self._normalize_emotion(emotion)
            if emo_norm:
                only = counts.get(emo_norm, 0)
                summary = f"{emo_norm} duygu {only} kez kaydedildi"
                return {
                    "counts": counts,
                    "summary": summary,
                    "period": period_norm,
                    "emotion": emo_norm,
                    "total_records": only,
                    "top_3_most": [],
                    "top_3_least": [],
                    "first_timestamp": None,
                    "last_timestamp": None,
                    "average_daily": 0.0
                }

            # Detaylı istatistikler hesapla
            total_records = sum(counts.values())
            
            # En çok görülen top 3 duygu
            top_3_most = self._get_top_moods(counts, top_n=3, reverse=True)
            
            # En az görülen top 3 duygu (sadece 0'dan büyük olanlar)
            top_3_least = self._get_top_moods(counts, top_n=3, reverse=False)
            
            # İlk ve son kayıt tarihleri
            first_timestamp, last_timestamp = self._get_first_last_timestamps(session, user_id, period=period_norm)
            
            # Ortalama günlük duygu sayısı
            avg_daily = self._calculate_average_daily_mood_count(session, user_id, period=period_norm)
            
            # Genel özet
            parts = [f"{cnt} kez {m.lower()}" for m, cnt in counts.items() if cnt > 0]
            base_summary = ", ".join(parts) if parts else "Henüz duygu kaydı yok"
            
            # Detaylı özet oluştur
            detail_parts = [base_summary]
            
            if total_records > 0:
                detail_parts.append(f"Toplam {total_records} kayıt")
                
                if avg_daily > 0:
                    detail_parts.append(f"Ortalama günlük {avg_daily} duygu")
                
                if top_3_most:
                    most_str = ", ".join([f"{m.lower()} ({c} kez)" for m, c in top_3_most])
                    detail_parts.append(f"En çok görülenler: {most_str}")
                
                if first_timestamp and last_timestamp:
                    first_date = first_timestamp.split(" ")[0]
                    last_date = last_timestamp.split(" ")[0]
                    if period_norm == "today":
                        detail_parts.append(f"Bugün: {first_timestamp}")
                    else:
                        detail_parts.append(f"İlk kayıt: {first_date}, Son kayıt: {last_date}")
            
            summary = ". ".join(detail_parts)
            
            result = {
                "counts": counts,
                "summary": summary,
                "period": period_norm,
                "total_records": total_records,
                "top_3_most": top_3_most,
                "top_3_least": top_3_least,
                "first_timestamp": first_timestamp,
                "last_timestamp": last_timestamp,
                "average_daily": avg_daily
            }
            return result
        finally:
            session.close()

    # -------------------------- Dış API ----------------------------- #
    def answer(self, user_message: str, user_id: int | None = None) -> Dict[str, Any]:
        """Kullanıcı mesajını yorumla ve istatistik cevabı üret."""
        if not user_id:
            return {
                "stats": True,
                "flow_type": "STATS",
                "response": "Duygu istatistiklerini görebilmek için lütfen giriş yapın.",
                "counts": {m: 0 for m in self.allowed_moods},
                "period": "all",
                "total_records": 0
            }
        
        try:
            period, emotion = self._detect_period_and_emotion(user_message or "")
            result = self.compute_stats(user_id=user_id, period=period, emotion=emotion)
            return {
                "stats": True,
                "flow_type": "STATS",  # Frontend'deki node tanıma için gerekli
                "response": result.get("summary", ""),
                **result
            }
        except Exception as e:
            return {
                "stats": True,
                "flow_type": "STATS",  # Frontend'deki node tanıma için gerekli
                "response": f"İstatistik hesaplanamadı: {e}"
            }


