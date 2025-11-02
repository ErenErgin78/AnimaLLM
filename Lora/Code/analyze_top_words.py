"""
Verisetindeki en çok kullanılan 10 kelimeyi bulan script.
"""

import json
import re
from collections import Counter
from pathlib import Path
from typing import List, Dict

# Dinamik dosya yolları - Script'in bulunduğu klasöre göre otomatik ayarlanır
SCRIPT_DIR = Path(__file__).parent.resolve()
PROJECT_ROOT = SCRIPT_DIR.parent.parent.resolve()
DATA_DIR = PROJECT_ROOT / "Lora" / "Data"

# Dosya yolu
INPUT_FILE = DATA_DIR / "final2.json"


def extract_words(text: str) -> List[str]:
    """
    Bir metinden kelimeleri çıkarır. Türkçe karakterleri destekler.
    
    Args:
        text: İşlenecek metin
        
    Returns:
        List[str]: Küçük harfe çevrilmiş kelime listesi
    """
    if not text or not isinstance(text, str):
        return []
    
    # Türkçe karakterli kelimeleri de yakalamak için regex kullan
    # \w+ Unicode harfleri de dahil eder (Türkçe karakterler dahil)
    words = re.findall(r'\b\w+\b', text.lower())
    
    return words


def count_words_in_dataset(data: List[Dict[str, str]]) -> Counter:
    """
    Verisetindeki tüm user ve assistant mesajlarından kelimeleri çıkarır ve sayar.
    
    Args:
        data: JSON verisi (diyalog listesi)
        
    Returns:
        Counter: Kelime sayılarını tutan Counter objesi
    """
    all_words = []
    
    try:
        for item in data:
            if not isinstance(item, dict):
                continue
            
            # User mesajından kelimeleri çıkar
            user_text = item.get('user', '')
            if user_text:
                words = extract_words(user_text)
                all_words.extend(words)
            
            # Assistant mesajından kelimeleri çıkar
            assistant_text = item.get('assistant', '')
            if assistant_text:
                words = extract_words(assistant_text)
                all_words.extend(words)
        
        # Kelime sayılarını hesapla
        word_counter = Counter(all_words)
        
        return word_counter
        
    except Exception as e:
        print(f"[ERROR] Kelime sayma hatası: {e}")
        raise


def main():
    """
    Ana fonksiyon - final.json dosyasını okuyup en çok kullanılan 10 kelimeyi bulur.
    """
    print("=" * 80)
    print("VERİSETİNDEKİ EN ÇOK KULLANILAN 10 KELİME ANALİZİ")
    print("=" * 80)
    print(f"Girdi dosyası: {INPUT_FILE}")
    print("=" * 80)
    print()
    
    # Dosya varlık kontrolü
    if not INPUT_FILE.exists():
        print(f"[ERROR] Dosya bulunamadı: {INPUT_FILE}")
        return 1
    
    try:
        # JSON dosyasını oku
        print(f"[READ] JSON dosyası okunuyor: {INPUT_FILE}")
        with open(INPUT_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        if not isinstance(data, list):
            print(f"[ERROR] JSON dosyası array formatında olmalı, alınan tip: {type(data)}")
            return 1
        
        print(f"[READ] Toplam {len(data)} diyalog okundu")
        print()
        
        # Kelimeleri say
        print("[ANALYZE] Kelimeler analiz ediliyor...")
        word_counter = count_words_in_dataset(data)
        
        total_words = sum(word_counter.values())
        unique_words = len(word_counter)
        
        print(f"[ANALYZE] Toplam {total_words} kelime, {unique_words} farklı kelime bulundu")
        print()
        
        # En çok kullanılan 10 kelimeyi al
        top_words = word_counter.most_common(10)
        
        # Sonuçları yazdır
        print("=" * 80)
        print("EN ÇOK KULLANILAN 10 KELİME:")
        print("=" * 80)
        for i, (word, count) in enumerate(top_words, 1):
            percentage = (count / total_words) * 100
            print(f"{i:2d}. {word:20s} : {count:6d} kez ({percentage:5.2f}%)")
        print("=" * 80)
        
        return 0
        
    except json.JSONDecodeError as e:
        print(f"[ERROR] JSON parse hatası: {e}")
        return 1
    except FileNotFoundError as e:
        print(f"[ERROR] Dosya bulunamadı: {e}")
        return 1
    except PermissionError as e:
        print(f"[ERROR] Dosya izin hatası: {e}")
        return 1
    except Exception as e:
        print(f"[ERROR] Beklenmeyen hata: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit(main())

