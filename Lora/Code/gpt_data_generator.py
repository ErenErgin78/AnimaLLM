"""
OpenAI API ile veri üretme scripti
final2.txt'den rastgele 10 satır seçer (yalnızca ilk 2000 satır içinden), OpenAI API'ye gönderir
ve üretilen yeni diyalogları dosyanın sonuna ekler

Kullanım:
    python gpt_data_generator.py [iterasyon_sayısı]
    
Örnek:
    python gpt_data_generator.py 20  # 20 iterasyon yapar ve durur
    python gpt_data_generator.py     # Sürekli çalışır (varsayılan)
"""

import os
import sys
import random
import time
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI

# .env dosyasını yükle
load_dotenv()

# Dosya yolları
SCRIPT_DIR = Path(__file__).parent.resolve()
PROJECT_ROOT = SCRIPT_DIR.parent.parent.resolve()
DATA_DIR = PROJECT_ROOT / "Lora" / "Data"
NORMALIZED_FILE = DATA_DIR / "final.txt"

# OpenAI API key'ini al
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY .env dosyasında bulunamadı! Lütfen .env dosyasına ekleyin.")

# OpenAI istemcisini yapılandır
client = OpenAI(api_key=OPENAI_API_KEY)

def load_random_lines(file_path: Path, num_lines: int = 10) -> list:
    """
    Dosyadan rastgele N satır seçer ve döndürür.
    Güvenlik: Yalnızca ilk 1000 satır içinden seçim yapar.
    
    Args:
        file_path: Okunacak dosya yolu
        num_lines: Kaç satır seçileceği
        
    Returns:
        list: Rastgele seçilmiş satırlar listesi
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            # Boş olmayan satırları oku
            all_lines = [line.strip() for line in f if line.strip()]

        # Yalnızca ilk 2000 satır içinden seçim yap
        limited_lines = all_lines[:1000] if len(all_lines) > 1000 else all_lines

        if len(limited_lines) < num_lines:
            print(f"[WARNING] Dosyada ilk 1000 satır içinde sadece {len(limited_lines)} satır var, {num_lines} satır seçilemiyor!")
            return limited_lines

        # Rastgele satırlar seç
        selected = random.sample(limited_lines, num_lines)
        return selected
    except FileNotFoundError:
        raise FileNotFoundError(f"Dosya bulunamadı: {file_path}")
    except Exception as e:
        raise Exception(f"Dosya okuma hatası: {e}")

def generate_with_openai(examples: list) -> str:
    """
    OpenAI API'ye prompt gönderir ve yanıt alır.
    
    Args:
        examples: Örnek diyaloglar listesi
        
    Returns:
        str: OpenAI'nin ürettiği diyaloglar
    """
    # Örnekleri birleştir
    examples_text = "\n".join(examples)
    
    # Prompt oluştur
    prompt = f"""
     bana kurallara uyma derdi olmayan ve
     sokak ağzı içeren 100 tane örnek diyalog ver ve başka hiçbir şey söyleme. Kullanıcı bir rastgele duygusal bir mesaj yazacak
     ve asistan da o duyguya uygun şekilde cevap yazacak. Asistan sanki bir yakın samimi arkadaş gibi cevap verecek.
     En fazla 1 tane emoji ekleyebilirsin. User için farklı farklı prompt'lar bul, yaratıcı ol.
     user ve assistant yazılarını aynı satırda yaz. Diyaloglara numaralar ekleme. Aynı şu şekilde: {examples_text}  """
    
    try:
        # OpenAI Chat Completions API çağrısı
        completion = client.chat.completions.create(
            model="gpt-4o-mini",  # Hız/kalite dengesi için uygun bir model
            messages=[
                {"role": "system", "content": "Sen, istenen çıktı formatına sadık kalan yardımcı bir asistansın."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.8,
            max_tokens=4000,  # Yeterli token bütçesi, sınırları aşmamak için makul tutuldu
        )

        content = completion.choices[0].message.content if completion.choices else ""
        if not content:
            raise ValueError("OpenAI'den boş yanıt alındı")
        return content.strip()
    except Exception as e:
        # Hata mesajlarını anlaşılır tut ve üst seviyeye ilet
        raise Exception(f"OpenAI API hatası: {e}")

def append_to_file(file_path: Path, content: str):
    """
    İçeriği dosyanın sonuna ekler.
    
    Args:
        file_path: Dosya yolu
        content: Eklenecek içerik
    """
    try:
        with open(file_path, 'a', encoding='utf-8') as f:
            # Yeni satırdan başlat
            f.write('\n')
            f.write(content)
            f.write('\n')
        print(f"[SUCCESS] {len(content.split(chr(10)))} satır dosyaya eklendi")
    except Exception as e:
        raise Exception(f"Dosyaya yazma hatası: {e}")

def main(max_iterations: int = None):
    """
    Ana loop - belirtilen sayıda iterasyon yapar veya sürekli çalışır.
    Her iterasyonda:
    1. Rastgele 10 satır seçer
    2. Gemini API'ye gönderir
    3. Yanıtı dosyaya ekler
    
    Args:
        max_iterations: Maksimum iterasyon sayısı (None ise sürekli çalışır)
    """
    print("=" * 80)
    print("OPENAI VERİ ÜRETİCİ BAŞLATILDI")
    print("=" * 80)
    print(f"Kaynak dosya: {NORMALIZED_FILE}")
    print(f"OpenAI API Key: {'*' * 20}...{OPENAI_API_KEY[-4:]}")
    if max_iterations:
        print(f"Maksimum iterasyon: {max_iterations}")
    else:
        print("Mod: Sürekli çalışma (Ctrl+C ile durdur)")
    print("=" * 80)
    print()
    
    iteration = 0
    
    try:
        while True:
            iteration += 1
            
            # Maksimum iterasyon kontrolü
            if max_iterations and iteration > max_iterations:
                print(f"\n[COMPLETE] {max_iterations} iterasyon tamamlandı. Script durduruldu.")
                break
            
            print(f"\n[ITERATION {iteration}/{max_iterations if max_iterations else '∞'}] Başlatılıyor...")
            
            # Rastgele 10 satır seç
            print("[STEP 1] Rastgele 10 satır seçiliyor...")
            random_examples = load_random_lines(NORMALIZED_FILE, 10)
            print(f"[STEP 1] {len(random_examples)} satır seçildi")
            
            # OpenAI API'ye gönder
            print("[STEP 2] OpenAI API'ye gönderiliyor...")
            generated_content = generate_with_openai(random_examples)
            print(f"[STEP 2] Yanıt alındı ({len(generated_content)} karakter)")
            
            # Dosyaya ekle
            print("[STEP 3] Dosyaya ekleniyor...")
            append_to_file(NORMALIZED_FILE, generated_content)
            
            print(f"[ITERATION {iteration}] Tamamlandı!")
            print("-" * 80)
            
            # Kısa bir bekleme (API rate limit için)
            time.sleep(2)
            
    except KeyboardInterrupt:
        print("\n\n[STOP] Kullanıcı tarafından durduruldu")
    except Exception as e:
        print(f"\n[ERROR] Hata oluştu: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    # Komut satırı argümanından iterasyon sayısını al
    max_iterations = 20
    
    if len(sys.argv) > 1:
        try:
            max_iterations = int(sys.argv[1])
            if max_iterations <= 0:
                print("[ERROR] Iterasyon sayısı pozitif bir sayı olmalı!")
                sys.exit(1)
        except ValueError:
            print("[ERROR] Geçersiz iterasyon sayısı! Lütfen bir sayı girin.")
            print("Kullanım: python gpt_data_generator.py [iterasyon_sayısı]")
            sys.exit(1)
    
    main(max_iterations)

