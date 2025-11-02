"""
Kahve ve müzik içeren diyalogların yarısını final.json'dan silen script.
"""

import json
import random
from pathlib import Path
from typing import List, Dict

# Dinamik dosya yolları - Script'in bulunduğu klasöre göre otomatik ayarlanır
SCRIPT_DIR = Path(__file__).parent.resolve()
PROJECT_ROOT = SCRIPT_DIR.parent.parent.resolve()
DATA_DIR = PROJECT_ROOT / "Lora" / "Data"

# Dosya yolları
INPUT_FILE = DATA_DIR / "final.json"
BACKUP_FILE = DATA_DIR / "finalbackup2.json"

def contains_keyword(item: Dict[str, str], keyword: str) -> bool:
    """
    Bir diyalogun user veya assistant mesajında belirtilen anahtar kelimeyi içerip içermediğini kontrol eder.
    
    Args:
        item: {"user": "...", "assistant": "..."} formatında bir diyalog
        keyword: Aranacak anahtar kelime
        
    Returns:
        bool: Anahtar kelime bulunursa True, aksi halde False
    """
    if not isinstance(item, dict) or 'user' not in item or 'assistant' not in item:
        return False
    
    # Hem user hem assistant mesajlarını birleştir ve küçük harfe çevir (case-insensitive arama için)
    combined_text = (item.get('user', '') + ' ' + item.get('assistant', '')).lower()
    
    # Anahtar kelimeyi kontrol et
    return keyword.lower() in combined_text

def remove_keyword_entries(data: List[Dict[str, str]], keywords: List[str], remove_ratio: float = 0.5) -> tuple:
    """
    Her keyword için ayrı ayrı, o keyword'ü içeren diyalogların belirli bir oranını kaldırır.
    
    Args:
        data: JSON verisi (diyalog listesi)
        keywords: Her biri için ayrı ayrı işlem yapılacak anahtar kelimeler listesi
        remove_ratio: Her keyword için kaldırılacak oran (0.5 = yarısı)
        
    Returns:
        tuple: (temizlenmiş veri, toplam kaldırılan diyalog sayısı, keyword bazında istatistikler)
    """
    # Silinecek index'leri tutacak set (bir diyalog birden fazla keyword içeriyorsa sadece bir kere silinir)
    indices_to_remove = set()
    
    # Her keyword için istatistik tut
    keyword_stats = {}
    
    # Her keyword için ayrı ayrı işlem yap
    for keyword in keywords:
        # Bu keyword'ü içeren diyalogları bul
        matching_indices = []
        for idx, item in enumerate(data):
            # Eğer bu diyalog daha önce silinmediyse kontrol et
            if idx not in indices_to_remove and contains_keyword(item, keyword):
                matching_indices.append(idx)
        
        matching_count = len(matching_indices)
        print(f"[FIND] '{keyword}' içeren {matching_count} diyalog bulundu")
        
        if matching_count == 0:
            keyword_stats[keyword] = {'total': 0, 'removed': 0}
            continue
        
        # Kaldırılacak diyalog sayısını hesapla (tam sayıya yuvarla, en az 1)
        num_to_remove = max(1, int(matching_count * remove_ratio))
        
        # Rastgele olarak seçilen diyalogların index'lerini al
        # Her keyword için farklı seed kullan (keyword'ün hash değerine göre)
        keyword_seed = hash(keyword) % (2**32)  # Hash'i 32-bit integer'a çevir
        random.seed(keyword_seed)  # Her keyword için tutarlı ama farklı seed
        selected_indices = random.sample(matching_indices, num_to_remove)
        indices_to_remove.update(selected_indices)
        
        keyword_stats[keyword] = {'total': matching_count, 'removed': num_to_remove}
        print(f"[REMOVE] '{keyword}' için {num_to_remove} diyalog seçildi (toplam {matching_count} içinden)")
    
    # Kaldırılacak diyalogları filtrele
    cleaned_data = [item for idx, item in enumerate(data) if idx not in indices_to_remove]
    total_removed = len(data) - len(cleaned_data)
    
    return cleaned_data, total_removed, keyword_stats

def main():
    """
    Ana fonksiyon - final.json dosyasını okuyup, kahve ve müzik içeren diyalogların yarısını siler.
    """
    print("=" * 80)
    print("KAHVE ve MÜZİK İÇEREN DİYALOGLARIN YARISINI SİLME")
    print("=" * 80)
    print(f"Girdi dosyası: {INPUT_FILE}")
    print(f"Yedek dosyası: {BACKUP_FILE}")
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
        
        original_count = len(data)
        print(f"[READ] Toplam {original_count} diyalog okundu")
        print()
        
        # Yedek oluştur (güvenlik için)
        print(f"[BACKUP] Yedek dosyası oluşturuluyor: {BACKUP_FILE}")
        with open(BACKUP_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"[BACKUP] Yedek dosyası oluşturuldu")
        print()
        
        # Her keyword için ayrı ayrı yarısını kaldır
        keywords = ['bi','çok']  # Hem Türkçe karakterli hem de olmayan versiyonları kontrol et
        cleaned_data, removed_count, keyword_stats = remove_keyword_entries(data, keywords, remove_ratio=0.5)
        
        print()
        print(f"[STATS] Genel İstatistikler:")
        print(f"  - Toplam diyalog: {original_count}")
        print(f"  - Toplam silinen diyalog: {removed_count}")
        print(f"  - Kalan diyalog: {len(cleaned_data)}")
        print()
        print(f"[STATS] Keyword Bazında İstatistikler:")
        for keyword, stats in keyword_stats.items():
            print(f"  - '{keyword}': {stats['removed']}/{stats['total']} silindi ({(stats['removed']/stats['total']*100) if stats['total'] > 0 else 0:.1f}%)")
        print()
        
        # Temizlenmiş veriyi dosyaya yaz
        print(f"[WRITE] Temizlenmiş veri dosyaya yazılıyor: {INPUT_FILE}")
        with open(INPUT_FILE, 'w', encoding='utf-8') as f:
            json.dump(cleaned_data, f, ensure_ascii=False, indent=2)
        print(f"[WRITE] Dosya başarıyla güncellendi")
        print()
        
        print("=" * 80)
        print("[COMPLETE] İşlem tamamlandı!")
        print(f"[INFO] Yedek dosyası: {BACKUP_FILE}")
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

