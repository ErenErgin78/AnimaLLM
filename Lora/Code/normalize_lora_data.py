"""
LoRA Veri Seti Normalizasyon Scripti

Bu script, farklı formatlardaki diyalog verilerini 
LoRA eğitimi için uygun tek bir formata çevirir.

Format dönüşümleri:
1. "Diyalog X user: ... assistant: ..." → "user: ... assistant: ..."
2. "X. user: ...\n    assistant: ..." → "user: ... assistant: ..."
3. "user: ... assistant: ..." → "user: ... assistant: ..." (zaten doğru)
"""

import re
import os
from typing import List, Tuple


def normalize_line(line: str) -> str:
    """
    Tek bir satırı normalize eder ve temizler
    
    Args:
        line: Normalize edilecek satır
        
    Returns:
        str: Normalize edilmiş satır (boş ise None döner)
    """
    if not line or not line.strip():
        return None
    
    # Başta/sonda boşlukları temizle
    line = line.strip()
    
    # Format 1: "Diyalog X user: ... assistant: ..." formatını yakala
    # Regex ile "Diyalog" ve numarayı kaldır
    pattern1 = r'^Diyalog\s+\d+\s+(user:.*)$'
    match1 = re.match(pattern1, line, re.IGNORECASE)
    if match1:
        # "Diyalog X" kısmını kaldır, sadece "user: ... assistant: ..." kısmını al
        normalized = match1.group(1).strip()
        return normalized if normalized else None
    
    # Format 2 için özel işlem gerekir (iki satırlı), 
    # bu fonksiyon sadece tek satır için çalışır
    # Format 2 işlemi process_multiline_format() içinde yapılacak
    
    # Format 3: Zaten doğru format "user: ... assistant: ..."
    # Sadece başta sayı ve nokta varsa temizle (örn: "61. user: ...")
    pattern3 = r'^\d+\.\s*(user:.*)$'
    match3 = re.match(pattern3, line)
    if match3:
        normalized = match3.group(1).strip()
        return normalized if normalized else None
    
    # Eğer "user:" ile başlıyorsa ve "assistant:" içeriyorsa, olduğu gibi bırak
    if 'user:' in line.lower() and 'assistant:' in line.lower():
        return line
    
    # Sadece "user:" ile başlıyorsa (Format 2 - ilk satır), None döndür
    # Çünkü bu çok satırlı formatın ilk kısmı, birleştirilmesi gerekiyor
    if re.match(r'^\d+\.\s*user:', line, re.IGNORECASE):
        # Format 2'nin ilk satırı, sonraki satırla birleştirilecek
        return None
    
    # Diğer durumlar için None döndür (işlenemeyen format)
    return None


def process_multiline_format(lines: List[str], index: int) -> Tuple[str, int]:
    """
    Format 2 (çok satırlı) için özel işlem yapar
    
    Format: "X. user: ...\n    assistant: ..."
    
    Args:
        lines: Tüm satırların listesi
        index: İşlenecek satırın indeksi
        
    Returns:
        Tuple[str, int]: (normalize edilmiş satır, kaç satır kullanıldı)
    """
    current_line = lines[index].strip()
    
    # Format 2: "X. user: ..." ile başlayan satır
    pattern = r'^\d+\.\s*user:(.*)$'
    match = re.match(pattern, current_line, re.IGNORECASE)
    
    if not match:
        return None, 0
    
    user_part = match.group(1).strip()
    
    # Sonraki satırı kontrol et (assistant kısmı)
    if index + 1 < len(lines):
        next_line = lines[index + 1].strip()
        
        # "assistant:" ile başlıyorsa (başta boşluk olabilir)
        assistant_match = re.match(r'^\s*assistant:(.*)$', next_line, re.IGNORECASE)
        if assistant_match:
            assistant_part = assistant_match.group(1).strip()
            # Birleştir
            combined = f"user: {user_part} assistant: {assistant_part}"
            return combined, 2
    
    # Assistant kısmı bulunamadı, sadece user kısmını döndür
    return f"user: {user_part} assistant:", 1


def normalize_lora_data(input_file: str, output_file: str) -> None:
    """
    Ana normalizasyon fonksiyonu
    
    Args:
        input_file: Girdi dosyası yolu
        output_file: Çıktı dosyası yolu
    """
    try:
        # Dosya varlığını kontrol et
        if not os.path.exists(input_file):
            raise FileNotFoundError(f"Dosya bulunamadı: {input_file}")
        
        # Dosyayı güvenli şekilde oku (encoding kontrolü)
        encodings = ['utf-8', 'utf-8-sig', 'latin-1', 'cp1254']
        content = None
        encoding_used = None
        
        for enc in encodings:
            try:
                with open(input_file, 'r', encoding=enc) as f:
                    content = f.readlines()
                    encoding_used = enc
                    break
            except UnicodeDecodeError:
                continue
        
        if content is None:
            raise ValueError("Dosya encoding'i algılanamadı")
        
        print(f"Dosya okundu: {len(content)} satır (encoding: {encoding_used})")
        
        normalized_lines = []
        i = 0
        skipped_count = 0
        
        while i < len(content):
            line = content[i]
            
            # Format 2 kontrolü (çok satırlı format)
            normalized_line, lines_used = process_multiline_format(content, i)
            
            if normalized_line:
                normalized_lines.append(normalized_line)
                i += lines_used
                continue
            
            # Tek satırlı formatları işle
            normalized = normalize_line(line)
            
            if normalized:
                normalized_lines.append(normalized)
                i += 1
            else:
                # Boş satır veya işlenemeyen format, atla
                if line.strip():
                    skipped_count += 1
                i += 1
        
        print(f"Normalize edildi: {len(normalized_lines)} diyalog")
        if skipped_count > 0:
            print(f"Atlandı: {skipped_count} satır")
        
        # Çıktı dosyasına yaz
        # Güvenlik: Dosya yolunu kontrol et, path injection'a karşı koruma
        safe_output = os.path.normpath(output_file)
        output_dir = os.path.dirname(safe_output) if os.path.dirname(safe_output) else '.'
        
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir, exist_ok=True)
        
        with open(safe_output, 'w', encoding='utf-8') as f:
            for line in normalized_lines:
                # Her satırın sonuna newline ekle
                f.write(line + '\n')
        
        print(f"Çıktı dosyası kaydedildi: {output_file}")
        print(f"Toplam diyalog sayısı: {len(normalized_lines)}")
        
    except FileNotFoundError as e:
        print(f"HATA: {e}")
        raise
    except PermissionError as e:
        print(f"HATA: Dosya yazma izni yok: {e}")
        raise
    except Exception as e:
        print(f"Beklenmeyen hata: {type(e).__name__}: {e}")
        raise


def validate_normalized_data(output_file: str) -> None:
    """
    Normalize edilmiş veriyi doğrular
    
    Args:
        output_file: Doğrulanacak dosya yolu
    """
    try:
        with open(output_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        valid_count = 0
        invalid_count = 0
        
        for i, line in enumerate(lines, 1):
            line = line.strip()
            if not line:
                continue
            
            # Her satırda "user:" ve "assistant:" olmalı
            has_user = 'user:' in line.lower()
            has_assistant = 'assistant:' in line.lower()
            
            if has_user and has_assistant:
                valid_count += 1
            else:
                invalid_count += 1
                print(f"Uyarı - Satır {i}: Geçersiz format: {line[:50]}...")
        
        print(f"\nDoğrulama sonuçları:")
        print(f"  Geçerli diyalog: {valid_count}")
        print(f"  Geçersiz satır: {invalid_count}")
        
    except Exception as e:
        print(f"Doğrulama hatası: {e}")


if __name__ == "__main__":
    """
    Ana program - Script çalıştırıldığında bu kısım çalışır
    """
    input_file = "LORA_DATA.txt"
    output_file = "LORA_DATA_normalized.txt"
    
    print("=" * 60)
    print("LoRA Veri Seti Normalizasyon İşlemi Başlıyor")
    print("=" * 60)
    
    try:
        # Normalizasyon işlemini başlat
        normalize_lora_data(input_file, output_file)
        
        # Doğrulama yap
        print("\n" + "=" * 60)
        print("Doğrulama İşlemi")
        print("=" * 60)
        validate_normalized_data(output_file)
        
        print("\n" + "=" * 60)
        print("İşlem tamamlandı!")
        print("=" * 60)
        
    except Exception as e:
        print(f"\nKRİTİK HATA: {e}")
        print("İşlem başarısız oldu.")
        exit(1)

