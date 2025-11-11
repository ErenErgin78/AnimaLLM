"""
Duygu Analizi Sistemi - LoRA Model Entegrasyonu
===============================================

Bu modül LoRA model ile metin üretimi ve LLM ile duygu analizi yapar.
- LoRA modelinden kullanıcı mesajına cevap üretir
- LLM'den (Gemini/GPT) duygu analizi yapar
- mood_emojis.json'dan duyguya göre emoji seçer
"""

import json
import os
import random
import re
import html
from typing import Any, Dict, Optional
from datetime import datetime
from pathlib import Path
from openai import OpenAI

from Auth.database import get_db
from Auth.models import EmotionLog

# LoRA model için gerekli importlar
try:
    from transformers import GPT2LMHeadModel, AutoTokenizer
    from peft import PeftModel
    TRANSFORMERS_AVAILABLE = True
except ImportError:
    TRANSFORMERS_AVAILABLE = False
    print("[WARNING] transformers veya peft kütüphaneleri bulunamadı. LoRA model kullanılamayacak.")

# Güvenlik sabitleri
MAX_EMOTION_MESSAGE_LENGTH = 1000
DANGEROUS_EMOTION_PATTERNS = [
    r'<script[^>]*>.*?</script>',
    r'javascript:',
    r'data:text/html',
    r'vbscript:',
    r'on\w+\s*=',
    r'<iframe[^>]*>',
    r'<object[^>]*>',
    r'<embed[^>]*>',
]

# Duygu → emoji veri kaynağını yükle (uygulama başında bir kez)
MOOD_EMOJIS: Dict[str, list[str]] = {}
# mood_emojis.json dosyası (proje kökü /data)
DATA_DIR = Path(__file__).resolve().parents[1] / "data"

try:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    data_path = DATA_DIR / "mood_emojis.json"
    if data_path.exists():
        import json
        MOOD_EMOJIS = json.loads(data_path.read_text(encoding="utf-8"))
except Exception:
    MOOD_EMOJIS = {}


class EmotionChatbot:
    def __init__(self, client: OpenAI = None) -> None:
        """Emotion chatbot başlatır - LoRA model ve LLM (Gemini/GPT) hazırlar"""
        self.client = client
        self.use_gemini = False
        if client is None:
            self.use_gemini = True
            # Gemini API'yi yapılandır - uyarıları bastır
            import google.generativeai as genai
            import warnings
            import logging
            warnings.filterwarnings("ignore", category=UserWarning)
            os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
            os.environ['GRPC_VERBOSITY'] = 'ERROR'
            logging.getLogger("google").setLevel(logging.ERROR)
            logging.getLogger("google.api_core").setLevel(logging.ERROR)
            logging.getLogger("absl").setLevel(logging.ERROR)
            genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
        
        self.stats: Dict[str, Any] = {
            "requests": 0,
            "last_request_at": None,
        }
        self.allowed_moods = [
            "Mutlu", "Üzgün", "Öfkeli", "Şaşkın", "Utanmış",
            "Endişeli", "Gülümseyen", "Flörtöz", "Sorgulayıcı", "Yorgun"
        ]
        self.emotion_counts: Dict[str, int] = {m: 0 for m in self.allowed_moods}
        
        # LoRA model ve tokenizer için lazy loading
        self.lora_model = None
        self.lora_tokenizer = None
        self._lora_loaded = False
        self._lora_loading = False  # Asenkron yükleme durumu

    def _sanitize_emotion_input(self, text: str) -> str:
        """Duygu sistemi için güvenli input sanitization"""
        if not text:
            return ""
        text = html.escape(text, quote=True)
        for pattern in DANGEROUS_EMOTION_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                print(f"[SECURITY] Duygu sisteminde tehlikeli pattern: {pattern}")
                return "[Güvenlik nedeniyle mesaj filtrelendi]"
        text = re.sub(r'\s+', ' ', text).strip()
        return text

    def _validate_emotion_message_length(self, text: str) -> bool:
        """Duygu mesajı uzunluk kontrolü"""
        return len(text) <= MAX_EMOTION_MESSAGE_LENGTH

    def _convert_messages_to_prompt(self, messages: list[Dict[str, Any]]) -> str:
        """OpenAI mesaj formatını Gemini prompt formatına çevirir"""
        prompt_parts = []
        for msg in messages:
            role = msg.get("role", "")
            content = msg.get("content", "")
            if content:
                if role == "system":
                    prompt_parts.append(f"Sistem: {content}")
                elif role == "user":
                    prompt_parts.append(f"Kullanıcı: {content}")
                elif role == "assistant":
                    prompt_parts.append(f"Asistan: {content}")
        return "\n".join(prompt_parts)

    def _log_mood_to_db(self, user_id: int, mood: str) -> None:
        """Duygu kaydını SQLite veritabanına ekler"""
        if not user_id or not mood:
            return
        
        try:
            db = next(get_db())
        except Exception as e:
            print(f"[EMOTION] DB bağlantısı oluşturulamadı: {e}")
            return
        
        try:
            log = EmotionLog(
                user_id=int(user_id),
                mood=str(mood).strip()
            )
            db.add(log)
            db.commit()
            print(f"[EMOTION] Duygu kaydı SQLite'a yazıldı: user_id={user_id}, mood={mood}")
        except Exception as e:
            db.rollback()
            print(f"[EMOTION] Duygu kaydı ekleme hatası (DB): {e}")
        finally:
            db.close()

    def get_functions(self) -> list[Dict[str, Any]]:
        """Emotion sistemi için function-calling kullanılmıyor"""
        return []

    def preload_lora_model_async(self) -> None:
        """Asenkron olarak LoRA modelini önceden yükle (program başlatıldığında)"""
        if self._lora_loading or self._lora_loaded:
            return
        
        self._lora_loading = True
        
        import threading
        def load_in_background():
            try:
                self._load_lora_model()
                print("[EMOTION] LoRA model asenkron olarak yüklendi ✅")
            except Exception as e:
                print(f"[EMOTION] LoRA model yükleme hatası: {e}")
                import traceback
                print(f"[EMOTION] Traceback: {traceback.format_exc()}")
            finally:
                self._lora_loading = False
        
        thread = threading.Thread(target=load_in_background, daemon=True)
        thread.start()
    
    def _load_lora_model(self):
        """LoRA modeli yükler - Base model üzerine adaptör takılır"""
        if self._lora_loaded:
            return
        
        if not TRANSFORMERS_AVAILABLE:
            print("[ERROR] LoRA model yüklenemedi: transformers/peft kütüphaneleri bulunamadı")
            self._lora_loaded = True
            return
        
        try:
            import torch
            
            # LoRA adaptör yolunu dinamik olarak belirle
            # Tools klasöründen bir seviye yukarı proje köküne çık ve Lora/Model/main'i hedefle
            project_root = Path(__file__).resolve().parents[1]
            base_path = project_root
            lora_path = project_root / "Lora" / "Model" / "main"
            
            if not lora_path.exists():
                print(f"[ERROR] LoRA adaptör yolu bulunamadı: {lora_path}")
                self._lora_loaded = True
                return
            
            # Adapter dosyalarını dinamik olarak kontrol et
            # adapter_config.json ve lora.safetensors (veya adapter_model.safetensors) dosyalarını ara
            adapter_config_path = lora_path / "adapter_config.json"
            
            # Model dosyasını kontrol et - önce adapter_model.safetensors, sonra lora.safetensors
            adapter_model_path = lora_path / "adapter_model.safetensors"
            if not adapter_model_path.exists():
                adapter_model_path = lora_path / "lora.safetensors"
            
            # Eğer adapter_config.json yoksa, "en iyi" klasöründen al (fallback)
            if not adapter_config_path.exists():
                fallback_config_path = project_root / "Lora" / "Model" / "en iyi" / "adapter_config.json"
                if fallback_config_path.exists():
                    print(f"[LoRA] adapter_config.json main klasöründe bulunamadı, 'en iyi' klasöründen kullanılıyor")
                    # Config'i main klasörüne kopyala veya doğrudan kullan
                    # PeftModel.from_pretrained zaten config dosyasını kendi bulabilir
                    # Ama en güvenlisi main klasörüne kopyalamak
                    import shutil
                    try:
                        shutil.copy2(fallback_config_path, adapter_config_path)
                        print(f"[LoRA] adapter_config.json 'en iyi' klasöründen main klasörüne kopyalandı")
                    except Exception as e:
                        print(f"[WARNING] adapter_config.json kopyalanamadı: {e}")
                        # Fallback olarak "en iyi" klasörünü kullan
                        lora_path = project_root / "Lora" / "Model" / "en iyi"
                        adapter_config_path = lora_path / "adapter_config.json"
                        adapter_model_path = lora_path / "adapter_model.safetensors"
            
            if not adapter_config_path.exists():
                print(f"[ERROR] adapter_config.json bulunamadı: {lora_path}")
                self._lora_loaded = True
                return
            
            if not adapter_model_path.exists():
                print(f"[ERROR] LoRA model dosyası bulunamadı (adapter_model.safetensors veya lora.safetensors): {lora_path}")
                self._lora_loaded = True
                return
            
            print(f"[LoRA] Base model yükleniyor: ytu-ce-cosmos/turkish-gpt2-large")
            
            # Base model ve tokenizer'ı yükle
            base_model_name = "ytu-ce-cosmos/turkish-gpt2-large"
            use_gpu = torch.cuda.is_available()
            
            base_model = GPT2LMHeadModel.from_pretrained(
                base_model_name,
                torch_dtype=torch.float16 if use_gpu else torch.float32
            )
            
            if use_gpu:
                base_model = base_model.cuda()
                print(f"[LoRA] Base model GPU'ya taşındı")
            
            # Tokenizer'ı yükle - önce local'den dene, yoksa base model'den
            tokenizer_path = lora_path / "tokenizer.json"
            if tokenizer_path.exists():
                tokenizer = AutoTokenizer.from_pretrained(str(lora_path))
            else:
                tokenizer = AutoTokenizer.from_pretrained(base_model_name)
            
            # Pad token ekle (eğer yoksa)
            if tokenizer.pad_token is None:
                tokenizer.pad_token = tokenizer.eos_token if hasattr(tokenizer, 'eos_token') and tokenizer.eos_token else tokenizer.add_special_tokens({'pad_token': '[PAD]'})
            
            print("[LoRA] Base model yüklendi, LoRA adaptörü ekleniyor...")
            
            # LoRA adaptörünü base model üzerine tak
            # Windows path sorununu çözmek için: local path için from_pretrained yerine load_adapter kullan
            try:
                # Önce from_pretrained ile dene
                lora_path_str = str(lora_path.resolve())
                self.lora_model = PeftModel.from_pretrained(
                    base_model,
                    lora_path_str,
                    device_map="auto" if use_gpu else None
                )
            except Exception as e:
                # Eğer path validation hatası varsa, manuel yükleme yap
                error_str = str(e).lower()
                if "repo id" in error_str or "hfvalidationerror" in error_str or "validation" in error_str:
                    print(f"[LoRA] Path validation hatası, manuel yükleme deneniyor...")
                    try:
                        from peft import PeftConfig
                        # Config dosyasını oku
                        import json
                        with open(adapter_config_path, 'r', encoding='utf-8') as f:
                            config_dict = json.load(f)
                        
                        # PeftModel oluştur (base model + config)
                        config = PeftConfig.from_dict(config_dict)
                        self.lora_model = PeftModel(base_model, config, adapter_name="default")
                        
                        # Weight dosyasını yükle (adapter_model.safetensors veya lora.safetensors)
                        if adapter_model_path.exists():
                            print(f"[LoRA] Weight dosyası yükleniyor: {adapter_model_path.name}")
                            if str(adapter_model_path).endswith('.safetensors'):
                                try:
                                    from safetensors.torch import load_file
                                    state_dict = load_file(str(adapter_model_path))
                                    print(f"[LoRA] Safetensors dosyası başarıyla yüklendi")
                                except ImportError:
                                    print(f"[LoRA WARNING] safetensors.torch bulunamadı, torch ile deneniyor...")
                                    import torch
                                    # .safetensors dosyasını torch.load ile açmaya çalışma, hata verir
                                    raise ImportError("safetensors kütüphanesi gerekli (.safetensors dosyası için)")
                            else:
                                import torch
                                state_dict = torch.load(str(adapter_model_path), map_location='cpu')
                            
                            # PEFT'in beklediği format: adapter_model.safetensors zaten doğru formatta olmalı
                            # Eğer key'ler base_model.model. ile başlıyorsa olduğu gibi bırak
                            # Eğer lora_ ile başlıyorsa default. prefix'i ekle
                            peft_state_dict = {}
                            for key, value in state_dict.items():
                                if key.startswith('base_model.model.'):
                                    # Base model key'leri olduğu gibi bırak
                                    peft_state_dict[key] = value
                                elif 'lora_' in key or 'default.' in key:
                                    # LoRA key'leri - zaten doğru formatta olabilir
                                    if key.startswith('default.'):
                                        peft_state_dict[key] = value
                                    else:
                                        # default. prefix'i ekle
                                        peft_state_dict[f'default.{key}'] = value
                                else:
                                    # Diğer key'leri de ekle
                                    peft_state_dict[key] = value
                            
                            # State dict'i yükle
                            print(f"[LoRA] State dict yükleniyor ({len(peft_state_dict)} key)...")
                            missing_keys, unexpected_keys = self.lora_model.load_state_dict(peft_state_dict, strict=False)
                            if missing_keys:
                                print(f"[LoRA WARNING] Eksik keys: {len(missing_keys)} adet (ilk 5: {missing_keys[:5]})")
                            if unexpected_keys:
                                print(f"[LoRA WARNING] Beklenmeyen keys: {len(unexpected_keys)} adet (ilk 5: {unexpected_keys[:5]})")
                            print("[LoRA] Adapter manuel yükleme ile başarıyla yüklendi")
                        else:
                            raise Exception(f"Adapter weight dosyası bulunamadı: {adapter_model_path}")
                    except Exception as e2:
                        print(f"[ERROR] Manuel yükleme de başarısız oldu: {e2}")
                        import traceback
                        print(f"[ERROR] Traceback: {traceback.format_exc()}")
                        raise e
                else:
                    # Diğer hatalar için original hatayı fırlat
                    raise e
            
            self.lora_tokenizer = tokenizer
            
            # Model tipini ve LoRA durumunu kontrol et
            if hasattr(self.lora_model, 'peft_config'):
                print(f"[LoRA] LoRA adaptörü başarıyla eklendi")
            else:
                print("[WARNING] LoRA adaptörü eklenmiş gibi görünmüyor, PEFT config bulunamadı")
            
            self.lora_model.eval()  # Inference modu
            self._lora_loaded = True
            
            # Model bilgilerini yazdır
            if use_gpu:
                print(f"[LoRA] Model device: {next(self.lora_model.parameters()).device}")
            
            print("[LoRA] Model başarıyla yüklendi ve hazır")
            
        except Exception as e:
            print(f"[ERROR] LoRA model yükleme hatası: {e}")
            import traceback
            print(f"[ERROR] Traceback: {traceback.format_exc()}")
            self._lora_loaded = True
    
    def _generate_with_lora(self, prompt: str, max_new_tokens: int = 40) -> str:
        """LoRA modelinden metin üretir - sadece kullanıcı mesajını kullanır"""
        if not TRANSFORMERS_AVAILABLE or self.lora_model is None or self.lora_tokenizer is None:
            return ""
        
        try:
            import torch
            import re
            
            # Prompt'u tokenize et
            model_max_len = getattr(self.lora_tokenizer, 'model_max_length', 512)
            safe_max_length = min(512, model_max_len) if model_max_len < 10000 else 512
            
            encoded = self.lora_tokenizer(
                prompt,
                return_tensors="pt",
                padding=True,
                truncation=True,
                max_length=safe_max_length
            )
            input_ids = encoded.input_ids
            attention_mask = encoded.attention_mask
            input_length = input_ids.shape[-1]
            
            # GPU'ya taşı (varsa)
            if torch.cuda.is_available():
                input_ids = input_ids.cuda()
                attention_mask = attention_mask.cuda()
            else:
                device = None
                if hasattr(self.lora_model, 'device'):
                    device = self.lora_model.device
                elif hasattr(self.lora_model, 'base_model'):
                    if hasattr(self.lora_model.base_model, 'device'):
                        device = self.lora_model.base_model.device
                
                if device is not None:
                    input_ids = input_ids.to(device)
                    attention_mask = attention_mask.to(device)
            
            # Token ID'lerini güvenli şekilde belirle
            if self.lora_tokenizer.pad_token_id is not None:
                pad_token_id = int(self.lora_tokenizer.pad_token_id)
            elif self.lora_tokenizer.eos_token_id is not None:
                pad_token_id = int(self.lora_tokenizer.eos_token_id)
            else:
                pad_token_id = 0
            
            if self.lora_tokenizer.eos_token_id is not None:
                eos_token_id = int(self.lora_tokenizer.eos_token_id)
            elif self.lora_tokenizer.pad_token_id is not None:
                eos_token_id = int(self.lora_tokenizer.pad_token_id)
            else:
                eos_token_id = pad_token_id
            
            # Text generation parametreleri
            min_length_value = input_length + 3
            max_possible_length = safe_max_length if safe_max_length < 10000 else 512
            min_length_value = min(min_length_value, max_possible_length)
            
            with torch.no_grad():
                outputs = self.lora_model.generate(
                    input_ids=input_ids,
                    attention_mask=attention_mask,
                    max_new_tokens=int(max_new_tokens),
                    min_length=int(min_length_value),
                    do_sample=True,
                    repetition_penalty=float(1.2),
                    no_repeat_ngram_size=int(0),
                    top_k=int(50),
                    top_p=float(0.95),
                    temperature=float(0.8),
                    pad_token_id=int(pad_token_id),
                    eos_token_id=int(eos_token_id)
                )
            
            # Sadece modelin ürettiği yanıtı al (prompt'u çıkar)
            response_ids = outputs[0][input_ids.shape[-1]:]
            generated_response = self.lora_tokenizer.decode(response_ids, skip_special_tokens=True)
            
            # EOS token'dan sonrasını temizle
            if self.lora_tokenizer.eos_token:
                generated_response = generated_response.split(self.lora_tokenizer.eos_token)[0].strip()
            
            generated_text = generated_response
            
            # Post-processing: "assistant:" ve "user:" öneklerini temizle
            assistant_match = re.search(r'assistant\s*:\s*', generated_text, flags=re.IGNORECASE)
            if assistant_match:
                generated_text = generated_text[assistant_match.end():].strip()
            
            user_match = re.search(r'user\s*:\s*', generated_text, flags=re.IGNORECASE)
            if user_match:
                generated_text = generated_text[user_match.end():].strip()
            
            # Prompt içeriyorsa temizle
            if prompt.strip() in generated_text:
                generated_text = generated_text.replace(prompt.strip(), "", 1).strip()
            
            # Virgülle başlayan metinleri temizle
            if generated_text.startswith(','):
                parts = generated_text.split(',', 1)
                if len(parts) > 1:
                    generated_text = parts[1].strip()
                else:
                    generated_text = generated_text.lstrip(',').strip()
            
            # Prompt'un ilk birkaç kelimesini kontrol et ve varsa çıkar
            prompt_words = prompt.strip().split()[:5]
            if len(prompt_words) >= 3:
                prompt_prefix = ' '.join(prompt_words)
                if generated_text.startswith(prompt_prefix):
                    generated_text = generated_text[len(prompt_prefix):].strip()
            
            # Emoji sayısını sınırla (en fazla 1 emoji)
            generated_text = self._limit_emoji_count(generated_text, max_emojis=1)
            
            return generated_text
            
        except Exception as e:
            print(f"[ERROR] LoRA metin üretme hatası: {e}")
            return ""
    
    def _limit_emoji_count(self, text: str, max_emojis: int = 1) -> str:
        """Metindeki emoji sayısını sınırlar - dataset'e uygun"""
        import re
        
        # Unicode emoji pattern'i
        emoji_pattern = re.compile(
            "["
            "\U0001F600-\U0001F64F"  # emoticons
            "\U0001F300-\U0001F5FF"  # symbols & pictographs
            "\U0001F680-\U0001F6FF"  # transport & map symbols
            "\U0001F1E0-\U0001F1FF"  # flags
            "\U00002702-\U000027B0"
            "\U000024C2-\U0001F251"
            "\U0001F900-\U0001F9FF"  # Supplemental Symbols and Pictographs
            "\U0001FA00-\U0001FAFF"  # Chess Symbols
            "\U00002600-\U000026FF"  # Miscellaneous Symbols
            "\U00002700-\U000027BF"  # Dingbats
            "]+",
            flags=re.UNICODE
        )
        
        # Tüm emoji bloklarını bul
        emoji_blocks = []
        i = 0
        while i < len(text):
            if emoji_pattern.match(text[i]):
                start = i
                end = i + 1
                while end < len(text):
                    if text[end] == '\u200d' and end + 1 < len(text):
                        if emoji_pattern.match(text[end + 1]):
                            end += 2
                        else:
                            break
                    elif emoji_pattern.match(text[end]):
                        end += 1
                    else:
                        break
                emoji_blocks.append((start, end))
                i = end
            else:
                i += 1
        
        # Emoji sayısı max_emojis'den fazlaysa sadece ilk max_emojis kadarını tut
        if len(emoji_blocks) > max_emojis:
            parts = []
            last_end = 0
            
            for idx, (start, end) in enumerate(emoji_blocks[:max_emojis]):
                if last_end < start:
                    parts.append(text[last_end:start])
                last_end = end
            
            if last_end < len(text):
                remaining = text[last_end:]
                remaining = emoji_pattern.sub('', remaining)
                remaining = remaining.replace('\u200d', '')
                parts.append(remaining)
            
            kept_emojis = ''.join(text[start:end] for start, end in emoji_blocks[:max_emojis])
            
            result = ''.join(parts).strip()
            if kept_emojis:
                result = (result + ' ' + kept_emojis).strip() if result else kept_emojis
            
            text = result
        
        # Fazla boşlukları temizle
        text = re.sub(r'\s+', ' ', text).strip()
        
        return text

    def chat(self, user_message: str, user_id: int | None = None) -> Dict[str, Any]:
        """Ana sohbet fonksiyonu - LoRA modelinden cevap, sonra LLM'den duygu"""
        # Güvenlik kontrolleri
        if not user_message:
            return {"response": "Mesaj boş olamaz"}
        
        if not self._validate_emotion_message_length(user_message):
            return {"response": f"Mesaj çok uzun. Maksimum {MAX_EMOTION_MESSAGE_LENGTH} karakter olabilir."}
        
        user_message = self._sanitize_emotion_input(user_message)
        if user_message == "[Güvenlik nedeniyle mesaj filtrelendi]":
            return {"response": "Güvenlik nedeniyle mesaj filtrelendi"}
        
        self.stats["requests"] += 1
        self.stats["last_request_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # ADIM 1: LoRA modelinden cevap al (sadece kullanıcı mesajı ile)
        print("[EMOTION] LoRA modelinden cevap alınıyor...")
        
        # LoRA modeli önceden yüklenmiş olmalı, kontrol et
        if not self._lora_loaded:
            if self._lora_loading:
                print("[EMOTION] LoRA modeli hala yükleniyor, bekleniyor...")
                import time
                for _ in range(60):
                    if self._lora_loaded:
                        break
                    time.sleep(1)
            if not self._lora_loaded:
                print("[EMOTION] LoRA modeli yüklenmedi, şimdi yükleniyor...")
                self._load_lora_model()
        
        if not TRANSFORMERS_AVAILABLE or self.lora_model is None:
            return {"response": "LoRA model yüklenemedi. Lütfen transformers ve peft kütüphanelerini yükleyin."}
        
        try:
            import torch
        except ImportError:
            return {"response": "LoRA model yüklenemedi. Lütfen torch kütüphanesini yükleyin."}
        
        # LoRA'ya sadece kullanıcının mesajını gönder
        lora_response = self._generate_with_lora(user_message, max_new_tokens=40)
        
        if not lora_response:
            return {"response": "LoRA modelinden cevap alınamadı."}
        
        print(f"[EMOTION] LoRA cevabı: {lora_response[:100]}...")
        
        # ADIM 2: LLM'den duygu analizi (kullanıcı mesajı + LoRA cevabı)
        print("[EMOTION] LLM'den duygu analizi yapılıyor...")
        
        emotion_prompt = f"""Görev: Verilen kullanıcı mesajını ve asistan cevabını analiz et ve sadece 1 duygu belirle.

Kullanıcı mesajı: "{user_message}"
Asistan cevabı: "{lora_response}"

Sadece aşağıdaki JSON formatını döndür, başka hiçbir şey yazma:

{{"ruh_hali": "Mutlu"}}

Seçilebilecek ruh halleri (sadece bu listeden seç):
- Mutlu
- Üzgün
- Öfkeli
- Şaşkın
- Utanmış
- Endişeli
- Gülümseyen
- Flörtöz
- Sorgulayıcı
- Yorgun

ÖNEMLİ TALİMATLAR:
1. Kullanıcı mesajındaki duygu ifadeleri daima birinci önceliktir. Kullanıcı kendini 'üzgün' olarak tanımlıyorsa, asistan cevabı ne olursa olsun 'Üzgün' seçmelisin.
2. Asistan cevabı, kullanıcıya verilen yanıtı temsil eder ve bağlamı pekiştirmek içindir.
3. Girdi formatı dışında hiçbir metin yazma, yalnızca tek bir JSON nesnesi döndür."""
        
        messages_payload: list[Dict[str, Any]] = [
            {"role": "system", "content": "Sen bir duygu analiz asistanısın. Verilen metni analiz edip sadece JSON formatında duygu döndürürsün. Başka hiçbir şey yazmazsın."},
            {"role": "user", "content": emotion_prompt}
        ]
        
        # LLM'den duygu analizi al
        try:
            if self.use_gemini:
                import google.generativeai as genai
                model = genai.GenerativeModel('gemini-2.5-flash')
                prompt_text = self._convert_messages_to_prompt(messages_payload)
                response = model.generate_content(prompt_text)
                emotion_content = response.text
                print(f"[EMOTION] Gemini duygu cevabı: {emotion_content}")
            else:
                completion = self.client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=messages_payload,
                    temperature=0.2,
                )
                emotion_content = completion.choices[0].message.content or ""
        except Exception as e:
            print(f"[ERROR] LLM duygu analizi hatası: {e}")
            emotion_content = json.dumps({
                "ruh_hali": random.choice(["Mutlu", "Üzgün", "Şaşkın"])
            })
        
        # JSON çıkar
        def extract_json_object(text: str) -> Dict[str, Any] | None:
            t = text.replace("```json", "").replace("```", "").strip()
            start = t.find('{')
            if start == -1:
                return None
            depth = 0
            in_string = False
            escape = False
            end_index = -1
            for i in range(start, len(t)):
                ch = t[i]
                if in_string:
                    if escape:
                        escape = False
                    elif ch == '\\':
                        escape = True
                    elif ch == '"':
                        in_string = False
                else:
                    if ch == '"':
                        in_string = True
                    elif ch == '{':
                        depth += 1
                    elif ch == '}':
                        depth -= 1
                        if depth == 0:
                            end_index = i
                            break
            if end_index == -1:
                return None
            candidate = t[start:end_index + 1]
            try:
                return json.loads(candidate)
            except Exception:
                return None
        
        emotion_data = extract_json_object(emotion_content)
        
        # Fallback: JSON parse edilemezse rastgele duygu
        if not emotion_data:
            print("[WARNING] LLM'den JSON parse edilemedi, rastgele duygu seçiliyor")
            emotion_data = {
                "ruh_hali": random.choice(["Mutlu", "Üzgün", "Şaşkın"])
            }
        
        # Duygu kaydını zaman damgasıyla ekle
        mood_raw = str(emotion_data.get("ruh_hali", ""))
        normalized_mood = mood_raw.strip()
        if normalized_mood in self.emotion_counts:
            self.emotion_counts[normalized_mood] += 1
            print(f"[EMOTION] Duygu kaydedildi: {normalized_mood}")
        else:
            print(f"[EMOTION] Duygu kaydedilemedi: '{normalized_mood}' allowed_moods listesinde yok")
        
        if user_id:
            self._log_mood_to_db(user_id, normalized_mood)
        
        # Emoji seçim: mood_emojis.json'dan duyguya göre rastgele
        def normalize_mood(name: str) -> str:
            """Duygu ismini mood_emojis.json'daki anahtarlara normalize eder"""
            n = name.strip()
            n_lower = n.lower()
            
            # Direkt JSON anahtarlarını kontrol et
            json_keys = list(MOOD_EMOJIS.keys())
            for key in json_keys:
                if key.lower() == n_lower:
                    return key
            
            # Yazım hatalarını düzelt
            mapping = {
                "güllümseyen": "Gülümseyen",
                "gülümseyen": "Gülümseyen",
                "gullumseyen": "Gülümseyen",
                "gulumsyen": "Gülümseyen",
                "utangaç": "Utanmış",
                "utanmış": "Utanmış",
                "utanmis": "Utanmış",
                "utangac": "Utanmış",
                "mutlu": "Mutlu",
                "üzgün": "Üzgün",
                "uzgun": "Üzgün",
                "öfkeli": "Öfkeli",
                "ofkeli": "Öfkeli",
                "şaşkın": "Şaşkın",
                "saskin": "Şaşkın",
                "endişeli": "Endişeli",
                "endiseli": "Endişeli",
                "flörtöz": "Flörtöz",
                "flortoz": "Flörtöz",
                "flörtoz": "Flörtöz",
                "flortöz": "Flörtöz",
                "sorgulayıcı": "Sorgulayıcı",
                "sorgulayici": "Sorgulayıcı",
                "yorgun": "Yorgun",
            }
            
            normalized = mapping.get(n_lower)
            if normalized and normalized in json_keys:
                return normalized
            
            return n
        
        def pick_emoji(mood: str) -> Optional[str]:
            """mood_emojis.json'dan duyguya göre rastgele emoji seçer"""
            key = normalize_mood(mood)
            print(f"[EMOTION] Duygu normalize edildi: '{mood}' -> '{key}'")
            
            # JSON'daki anahtarları direkt kontrol et
            options = MOOD_EMOJIS.get(key)
            if options:
                try:
                    selected_emoji = random.choice(options)
                    print(f"[EMOTION] Emoji seçildi: {selected_emoji} (duygu: {key}, seçenekler: {len(options)})")
                    return selected_emoji
                except Exception as e:
                    print(f"[EMOTION] Emoji seçim hatası: {e}")
                    return None
            
            # Fallback: fuzzy matching
            print(f"[EMOTION] Direkt eşleşme bulunamadı, fuzzy matching deneniyor...")
            for json_key in MOOD_EMOJIS.keys():
                if json_key.lower() in key.lower() or key.lower() in json_key.lower():
                    options = MOOD_EMOJIS.get(json_key)
                    if options:
                        try:
                            selected_emoji = random.choice(options)
                            print(f"[EMOTION] Emoji seçildi (fuzzy): {selected_emoji} (duygu: {key} -> {json_key})")
                            return selected_emoji
                        except Exception as e:
                            print(f"[EMOTION] Fuzzy emoji seçim hatası: {e}")
                            continue
            
            print(f"[EMOTION] Emoji bulunamadı: {key}")
            return None
        
        emoji = pick_emoji(mood_raw)
        if emoji:
            print(f"[EMOTION] Final emoji: {emoji}")
        else:
            print(f"[EMOTION] WARNING: Emoji None döndü! Duygu: {mood_raw}")
            # Fallback: eğer emoji bulunamazsa varsayılan emoji kullan
            emoji = '❓'
            print(f"[EMOTION] Fallback emoji kullanılıyor: {emoji}")
        
        # Response format: Frontend'in beklediği format
        return {
            "response": lora_response,  # LoRA cevabı
            "emoji": emoji,  # Tek emoji (mutlaka bir değer olmalı)
            "mood": mood_raw,  # Duygu
            "stats": self.stats,  # İstatistikler
        }
