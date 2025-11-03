"""
Veri dosyasını (final.txt) JSON formatına çevirir.
Her satır formatı: user: [mesaj] assistant: [mesaj]

JSON çıktısı: [{"user": "...", "assistant": "..."}, ...]
"""

import json
import re
from pathlib import Path
from typing import List, Dict


def parse_dialogue_line(line: str) -> Dict[str, str]:
    """
    Bir diyalog satırını parse eder ve user/assistant mesajlarını ayırır.
    
    Args:
        line: Diyalog satırı (format: "user: ... assistant: ...")
        
    Returns:
        Dict: {"user": "...", "assistant": "..."} formatında dict
    """
    line = line.strip()
    if not line:
        return None
    
    # "user:" ve "assistant:" ayırıcılarını bul
    # Regex ile güvenli şekilde parse et
    pattern = r'^user:\s*(.+?)\s+assistant:\s*(.+)$'
    match = re.match(pattern, line, re.IGNORECASE)
    
    if match:
        user_msg = match.group(1).strip()
        assistant_msg = match.group(2).strip()
        return {"user": user_msg, "assistant": assistant_msg}
    else:
        # Eğer format uymazsa, raw olarak kaydet
        print(f"[WARNING] Parse edilemedi: {line[:50]}...")
        return None


def convert_txt_to_json(input_file: Path, output_file: Path) -> None:
    """
    TXT dosyasını okuyup JSON formatına çevirir ve kaydeder.
    
    Args:
        input_file: Okunacak TXT dosyası yolu
        output_file: Yazılacak JSON dosyası yolu
    """
    if not input_file.exists():
        raise FileNotFoundError(f"Girdi dosyası bulunamadı: {input_file}")
    
    dialogues = []
    total_lines = 0
    parsed_lines = 0
    error_lines = 0
    
    print(f"[CONVERT] Dosya okunuyor: {input_file}")
    
    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                total_lines += 1
                
                # Satırı parse et
                parsed = parse_dialogue_line(line)
                
                if parsed:
                    dialogues.append(parsed)
                    parsed_lines += 1
                else:
                    error_lines += 1
                    if error_lines <= 5:  # İlk 5 hatayı göster
                        print(f"[WARNING] Satır {line_num} parse edilemedi: {line[:80]}...")
        
        print(f"[CONVERT] İstatistikler:")
        print(f"[CONVERT] - Toplam satır: {total_lines}")
        print(f"[CONVERT] - Başarıyla parse edilen: {parsed_lines}")
        print(f"[CONVERT] - Hatalı satır: {error_lines}")
        
        if len(dialogues) == 0:
            raise ValueError("Hiçbir diyalog parse edilemedi!")
        
        # JSON formatında kaydet (indent=2 ile okunabilir format)
        print(f"[CONVERT] JSON dosyası yazılıyor: {output_file}")
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(dialogues, f, ensure_ascii=False, indent=2)
        
        print(f"[CONVERT] Başarılı! {len(dialogues)} diyalog JSON formatına çevrildi.")
        print(f"[CONVERT] Çıktı dosyası: {output_file}")
        
    except Exception as e:
        raise Exception(f"Dosya dönüştürme hatası: {e}")


def main():
    """Ana fonksiyon - Dosya yollarını ayarlar ve dönüştürme işlemini başlatır"""
    # Dosya yolları
    script_dir = Path(__file__).parent
    project_root = script_dir.parent.parent
    data_dir = project_root / "Lora" / "Data"
    
    input_file = data_dir / "final.txt"
    output_file = data_dir / "final.json"
    
    print("=" * 80)
    print("TXT -> JSON DÖNÜŞTÜRÜCÜ")
    print("=" * 80)
    print(f"Girdi dosyası: {input_file}")
    print(f"Çıktı dosyası: {output_file}")
    print("=" * 80)
    print()
    
    try:
        convert_txt_to_json(input_file, output_file)
        
        print()
        print("=" * 80)
        print("DÖNÜŞTÜRME TAMAMLANDI!")
        print("=" * 80)
        
    except Exception as e:
        print(f"\n[ERROR] Hata oluştu: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())

