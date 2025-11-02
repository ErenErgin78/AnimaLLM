"""
final2.txt dosyasındaki gereksiz boşlukları temizleyen script.
- user: ve assistant: etiketleri ile mesajlar arasında tek boşluk olmalı
- Mesajların başındaki ve sonundaki boşluklar temizlenir
- Mesaj içindeki birden fazla boşluklar tek boşluğa indirgenir
- Boş satırlar kaldırılır
"""

import re
from pathlib import Path

# Dinamik dosya yolları - Script'in bulunduğu klasöre göre otomatik ayarlanır
SCRIPT_DIR = Path(__file__).parent.resolve()
PROJECT_ROOT = SCRIPT_DIR.parent.parent.resolve()
DATA_DIR = PROJECT_ROOT / "Lora" / "Data"

# Dosya yolları
INPUT_FILE = DATA_DIR / "final2.txt"
BACKUP_FILE = DATA_DIR / "final2.txt.backup"


def clean_message(text: str) -> str:
    """
    Bir mesaj metnindeki gereksiz boşlukları temizler.
    
    Args:
        text: Temizlenecek metin
        
    Returns:
        str: Temizlenmiş metin
    """
    if not text:
        return ""
    
    # Başındaki ve sonundaki boşlukları temizle
    text = text.strip()
    
    # Birden fazla boşluğu tek boşluğa indirge
    text = re.sub(r'\s+', ' ', text)
    
    return text


def fix_line(line: str) -> str:
    """
    Bir satırı düzeltir: user: ve assistant: mesajlarını temizler ve düzgün formata getirir.
    
    Args:
        line: Düzeltilecek satır
        
    Returns:
        str: Düzeltilmiş satır (veya boş string)
    """
    line = line.strip()
    
    # Boş satırları atla
    if not line:
        return ""
    
    # user: ve assistant: formatını kontrol et
    if 'user:' not in line or 'assistant:' not in line:
        # Format doğru değilse, olduğu gibi bırak (belki zaten düzgün)
        return line
    
    # user: ve assistant: kısımlarını ayır
    # user: ile başlayıp assistant: ile devam eden format
    match = re.match(r'user:\s*(.+?)\s*assistant:\s*(.+)$', line, re.IGNORECASE)
    
    if match:
        user_msg = match.group(1)
        assistant_msg = match.group(2)
        
        # Mesajları temizle
        user_msg = clean_message(user_msg)
        assistant_msg = clean_message(assistant_msg)
        
        # Düzgün formatta birleştir: user: [mesaj] assistant: [mesaj]
        fixed_line = f"user: {user_msg} assistant: {assistant_msg}"
        
        return fixed_line
    
    # Eğer regex eşleşmezse, manuel olarak ayır
    parts = line.split('assistant:')
    if len(parts) == 2:
        user_part = parts[0].replace('user:', '', 1).strip()
        assistant_part = parts[1].strip()
        
        user_msg = clean_message(user_part)
        assistant_msg = clean_message(assistant_part)
        
        fixed_line = f"user: {user_msg} assistant: {assistant_msg}"
        
        return fixed_line
    
    # Format anlaşılmadıysa olduğu gibi bırak
    return line


def fix_lines(lines: list) -> list:
    """
    Satırları düzeltir: user: ve assistant: mesajlarını temizler.
    
    Args:
        lines: Düzeltilecek satırlar listesi
        
    Returns:
        list: Düzeltilmiş satırlar listesi
    """
    fixed_lines = []
    
    for line in lines:
        fixed_line = fix_line(line)
        
        # Boş satırları atla (sadece boşluk içeren satırlar)
        if fixed_line:
            fixed_lines.append(fixed_line + '\n')
    
    return fixed_lines


def main():
    """
    Ana fonksiyon - final2.txt dosyasındaki gereksiz boşlukları temizler.
    """
    print("=" * 80)
    print("FINAL2.TXT BOŞLUKLARI DÜZELTME")
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
        # Yedek oluştur
        print(f"[BACKUP] Yedek dosyası oluşturuluyor: {BACKUP_FILE}")
        with open(INPUT_FILE, 'r', encoding='utf-8') as f:
            backup_content = f.read()
        
        with open(BACKUP_FILE, 'w', encoding='utf-8') as f:
            f.write(backup_content)
        
        print(f"[BACKUP] Yedek dosyası oluşturuldu")
        print()
        
        # Dosyayı oku ve düzelt
        print(f"[READ] Dosya okunuyor: {INPUT_FILE}")
        with open(INPUT_FILE, 'r', encoding='utf-8') as f:
            original_lines = f.readlines()
        
        original_line_count = len(original_lines)
        print(f"[READ] Toplam {original_line_count} satır okundu")
        print()
        
        # Satırları düzelt
        print("[FIX] Satırlar düzeltiliyor...")
        fixed_lines = fix_lines(original_lines)
        
        fixed_line_count = len(fixed_lines)
        print(f"[FIX] {original_line_count} satır -> {fixed_line_count} satır")
        print()
        
        # Düzeltilmiş dosyayı yaz
        print(f"[WRITE] Düzeltilmiş dosya yazılıyor: {INPUT_FILE}")
        with open(INPUT_FILE, 'w', encoding='utf-8') as f:
            f.writelines(fixed_lines)
        
        print(f"[WRITE] Dosya başarıyla güncellendi")
        print()
        
        print("=" * 80)
        print("[COMPLETE] İşlem tamamlandı!")
        print(f"[INFO] Yedek dosyası: {BACKUP_FILE}")
        print("=" * 80)
        
        return 0
        
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

