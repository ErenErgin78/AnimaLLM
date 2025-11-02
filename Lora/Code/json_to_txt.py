"""
JSON formatındaki veriyi TXT formatına çeviren script.
Her satırda user ve assistant mesajları birlikte olacak: user: [mesaj] assistant: [mesaj]
"""

import json
from pathlib import Path
from typing import List, Dict

# Dinamik dosya yolları - Script'in bulunduğu klasöre göre otomatik ayarlanır
SCRIPT_DIR = Path(__file__).parent.resolve()
PROJECT_ROOT = SCRIPT_DIR.parent.parent.resolve()
DATA_DIR = PROJECT_ROOT / "Lora" / "Data"

# Dosya yolları
INPUT_FILE = DATA_DIR / "final.json"
OUTPUT_FILE = DATA_DIR / "final2.txt"


def json_to_txt(data: List[Dict[str, str]], output_file: Path) -> None:
    """
    JSON verisini TXT formatına çevirir. Her satırda user ve assistant mesajları birlikte olur.
    
    Args:
        data: JSON verisi (diyalog listesi)
        output_file: Yazılacak TXT dosyası yolu
    """
    total_lines = 0
    written_lines = 0
    error_count = 0
    
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            for item in data:
                total_lines += 1
                
                if not isinstance(item, dict):
                    error_count += 1
                    continue
                
                # User ve assistant mesajlarını al
                user_msg = item.get('user', '').strip()
                assistant_msg = item.get('assistant', '').strip()
                
                # Boş mesajları atla
                if not user_msg or not assistant_msg:
                    error_count += 1
                    continue
                
                # Format: user: [mesaj] assistant: [mesaj]
                line = f"user: {user_msg} assistant: {assistant_msg}\n"
                f.write(line)
                written_lines += 1
        
        print(f"[WRITE] Toplam {total_lines} diyalog işlendi")
        print(f"[WRITE] Başarıyla yazılan: {written_lines} satır")
        print(f"[WRITE] Atlanan/Hatalı: {error_count} diyalog")
        
    except Exception as e:
        raise Exception(f"Dosya yazma hatası: {e}")


def main():
    """
    Ana fonksiyon - final.json dosyasını okuyup final.txt formatına çevirir.
    """
    print("=" * 80)
    print("JSON -> TXT DÖNÜŞTÜRÜCÜ")
    print("=" * 80)
    print(f"Girdi dosyası: {INPUT_FILE}")
    print(f"Çıktı dosyası: {OUTPUT_FILE}")
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
        
        # TXT formatına çevir
        print(f"[CONVERT] TXT dosyasına dönüştürülüyor: {OUTPUT_FILE}")
        json_to_txt(data, OUTPUT_FILE)
        print()
        
        print("=" * 80)
        print("[COMPLETE] İşlem tamamlandı!")
        print(f"[INFO] Çıktı dosyası: {OUTPUT_FILE}")
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

