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

import os
import json
import re
from typing import Any, Dict, Optional, Tuple
from datetime import datetime
from pathlib import Path


# Veri dizini ve dosyalar
DATA_DIR = Path(__file__).parent / "data"
CHAT_HISTORY_FILE = DATA_DIR / "chat_history.txt"
MOOD_COUNTER_FILE = DATA_DIR / "mood_counter.txt"


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
    def _read_mood_history(self) -> list[Dict[str, Any]]:
        """mood_counter.txt içindeki zaman damgalı duygu kayıtlarını okur"""
        try:
            if MOOD_COUNTER_FILE.exists():
                raw = MOOD_COUNTER_FILE.read_text(encoding="utf-8").strip()
                if not raw:
                    return []
                
                data = json.loads(raw)
                
                # Yeni format: JSON array (zaman damgalı kayıtlar)
                if isinstance(data, list):
                    return data
                
                # Eski format: JSON object (sayılar) - geriye uyumluluk
                elif isinstance(data, dict):
                    history = []
                    today = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    for mood, count in data.items():
                        if isinstance(count, int) and count > 0:
                            # Her sayı için bir kayıt oluştur (bugünün tarihiyle)
                            for _ in range(min(count, 1000)):  # Güvenlik için maksimum 1000
                                history.append({
                                    "mood": str(mood).strip(),
                                    "timestamp": today
                                })
                    return history
        except Exception as e:
            print(f"[STATS] Duygu geçmişi okuma hatası: {e}")
        return []

    def _read_persisted_counts(self) -> Dict[str, int]:
        """mood_counter.txt içindeki tüm zamanlar sayacını oku (yoksa boş)."""
        counts: Dict[str, int] = {m: 0 for m in self.allowed_moods}
        try:
            history = self._read_mood_history()
            for record in history:
                if isinstance(record, dict):
                    mood = str(record.get("mood", "")).strip()
                    if mood in counts:
                        counts[mood] += 1
        except Exception as e:
            print(f"[STATS] Duygu sayacı okuma hatası: {e}")
        return counts

    def _read_today_counts_from_mood_history(self) -> Dict[str, int]:
        """mood_counter.txt içinden sadece bugün tarihli kayıtlardan duygu say."""
        counts: Dict[str, int] = {m: 0 for m in self.allowed_moods}
        today_str = datetime.now().strftime("%Y-%m-%d")
        try:
            history = self._read_mood_history()
            for record in history:
                if isinstance(record, dict):
                    timestamp = str(record.get("timestamp", ""))
                    # Timestamp bugünün tarihiyle başlıyorsa say
                    if timestamp.startswith(today_str):
                        mood = str(record.get("mood", "")).strip()
                        if mood in counts:
                            counts[mood] += 1
        except Exception as e:
            print(f"[STATS] Bugünkü duygu sayacı okuma hatası: {e}")
        return counts

    def _get_top_moods(self, counts: Dict[str, int], top_n: int = 3, reverse: bool = True) -> list[Tuple[str, int]]:
        """En çok/az görülen duyguları döndürür (top N)"""
        try:
            # Sadece 0'dan büyük değerleri filtrele ve sırala
            filtered = [(mood, count) for mood, count in counts.items() if count > 0]
            sorted_moods = sorted(filtered, key=lambda x: x[1], reverse=reverse)
            return sorted_moods[:top_n]
        except Exception:
            return []

    def _get_first_last_timestamps(self, period: str = "all") -> Tuple[Optional[str], Optional[str]]:
        """İlk ve son kayıt tarihlerini döndürür"""
        try:
            history = self._read_mood_history()
            if not history:
                return None, None
            
            # Period filtresi uygula
            if period == "today":
                today_str = datetime.now().strftime("%Y-%m-%d")
                filtered_history = [
                    r for r in history 
                    if isinstance(r, dict) and str(r.get("timestamp", "")).startswith(today_str)
                ]
            else:
                filtered_history = history
            
            if not filtered_history:
                return None, None
            
            # Timestamp'leri parse et ve sırala
            timestamps = []
            for record in filtered_history:
                if isinstance(record, dict):
                    ts_str = str(record.get("timestamp", ""))
                    if ts_str:
                        try:
                            ts = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S")
                            timestamps.append((ts, ts_str))
                        except Exception:
                            continue
            
            if not timestamps:
                return None, None
            
            timestamps.sort(key=lambda x: x[0])
            first_ts = timestamps[0][1]
            last_ts = timestamps[-1][1]
            return first_ts, last_ts
        except Exception as e:
            print(f"[STATS] İlk/son tarih okuma hatası: {e}")
            return None, None

    def _calculate_average_daily_mood_count(self, period: str = "all") -> float:
        """Ortalama günlük duygu sayısını hesaplar"""
        try:
            history = self._read_mood_history()
            if not history:
                return 0.0
            
            # Period filtresi uygula
            if period == "today":
                today_str = datetime.now().strftime("%Y-%m-%d")
                filtered_history = [
                    r for r in history 
                    if isinstance(r, dict) and str(r.get("timestamp", "")).startswith(today_str)
                ]
            else:
                filtered_history = history
            
            if not filtered_history:
                return 0.0
            
            # Tarihe göre grupla
            dates = set()
            for record in filtered_history:
                if isinstance(record, dict):
                    ts_str = str(record.get("timestamp", ""))
                    if ts_str:
                        try:
                            date_part = ts_str.split(" ")[0]  # Sadece tarih kısmı
                            dates.add(date_part)
                        except Exception:
                            continue
            
            if not dates:
                return 0.0
            
            # Toplam kayıt sayısını tarih sayısına böl
            total_records = len(filtered_history)
            total_days = len(dates)
            return round(total_records / total_days, 2) if total_days > 0 else 0.0
        except Exception as e:
            print(f"[STATS] Ortalama günlük sayı hesaplama hatası: {e}")
            return 0.0

    def compute_stats(self, period: str = "all", emotion: Optional[str] = None) -> Dict[str, Any]:
        """İstatistik hesapla ve özet üret - detaylı bilgilerle"""
        period_norm = (period or "all").lower()
        if period_norm not in ("all", "today"):
            period_norm = "all"

        if period_norm == "today":
            # Bugünkü kayıtları mood_counter.txt'den oku
            counts = self._read_today_counts_from_mood_history()
        else:
            # Tüm kayıtları mood_counter.txt'den oku
            counts = self._read_persisted_counts()

        # İsteğe bağlı tek duygu filtresi
        emo_norm = self._normalize_emotion(emotion)
        if emo_norm:
            only = counts.get(emo_norm, 0)
            summary = f"{emo_norm} duygu {only} kez kaydedildi"
            return {"counts": counts, "summary": summary, "period": period_norm, "emotion": emo_norm}

        # Detaylı istatistikler hesapla
        total_records = sum(counts.values())
        
        # En çok görülen top 3 duygu
        top_3_most = self._get_top_moods(counts, top_n=3, reverse=True)
        
        # En az görülen top 3 duygu (sadece 0'dan büyük olanlar)
        top_3_least = self._get_top_moods(counts, top_n=3, reverse=False)
        
        # İlk ve son kayıt tarihleri
        first_timestamp, last_timestamp = self._get_first_last_timestamps(period=period_norm)
        
        # Ortalama günlük duygu sayısı
        avg_daily = self._calculate_average_daily_mood_count(period=period_norm)
        
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
        
        return {
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

    # -------------------------- Dış API ----------------------------- #
    def answer(self, user_message: str) -> Dict[str, Any]:
        """Kullanıcı mesajını yorumla ve istatistik cevabı üret."""
        try:
            period, emotion = self._detect_period_and_emotion(user_message or "")
            result = self.compute_stats(period=period, emotion=emotion)
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


