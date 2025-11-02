"""
CHAIN SYSTEM - Ana Chatbot Sistemi
==================================

Bu dosya LangChain chain yapısı ile tüm sistemleri koordine eder.
- Chain-based akış yönlendirmesi
- RAG, Animal, Emotion sistemlerini chain olarak çağırma
- Web arayüzü yönetimi
"""

import os
import re
import html
from typing import Any, Dict
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from dotenv import load_dotenv

# LangChain imports
from langchain_openai import OpenAI
from langchain.prompts import PromptTemplate
from langchain.schema import BaseOutputParser
from langchain.memory import ConversationSummaryBufferMemory

# Sistem modüllerini import et
from emotion_system import EmotionChatbot
from statistic_system import StatisticSystem
from animal_system import route_animals, _animal_emoji
from rag_service import rag_service

load_dotenv()

app = FastAPI(title="CHAIN SYSTEM - Akıllı Chatbot Sistemi", version="3.0.0")

# LangChain LLM instance - Fallback mekanizması ile
def get_llm():
    """OpenAI API geçersizse Gemini'yi kullan"""
    import warnings
    import logging
    
    # Uyarıları bastır
    warnings.filterwarnings("ignore")
    os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'  # TensorFlow uyarılarını bastır
    os.environ['GRPC_VERBOSITY'] = 'ERROR'  # gRPC uyarılarını bastır
    logging.getLogger("transformers").setLevel(logging.ERROR)
    logging.getLogger("google").setLevel(logging.ERROR)
    logging.getLogger("google.api_core").setLevel(logging.ERROR)
    logging.getLogger("absl").setLevel(logging.ERROR)
    
    try:
        # OpenAI API'yi test et
        test_llm = OpenAI(temperature=0.1, max_tokens=1000, request_timeout=15)
        # Basit bir test çağrısı yap
        test_llm.invoke("test")
        print("[LLM] OpenAI API kullanılıyor")
        return test_llm
    except Exception:
        # OpenAI API key kullanılamıyor
        print("[LLM] OpenAI API key kullanılamıyor")
        try:
            # Gemini API'yi test et - sadece API key ile
            import google.generativeai as genai
            api_key = os.getenv("GEMINI_API_KEY")
            if not api_key:
                raise Exception("GEMINI_API_KEY bulunamadı")
            genai.configure(api_key=api_key)
            
            # LangChain wrapper oluştur - Google Cloud credentials olmadan
            from langchain_google_genai import ChatGoogleGenerativeAI
            gemini_llm = ChatGoogleGenerativeAI(
                model="gemini-2.5-flash",
                temperature=0.1,
                max_tokens=1000,
                request_timeout=15,
                google_api_key=api_key
            )
            print("[LLM] Gemini API kullanılıyor")
            return gemini_llm
        except Exception:
            print("[LLM] Gemini API key kullanılamıyor")
            raise Exception("Hiçbir API key kullanılamıyor")

llm = get_llm()

# =============================================================================
# CONVERSATIONSUMMARYBUFFERMEMORY - GLOBAL MEMORY SİSTEMİ
# =============================================================================
# Hibrit yaklaşım: uzun konuşmaları özetler, son mesajları hatırlar
# Token limiti ile maliyet kontrolü sağlar
# Tüm chain'ler bu memory sistemi ile konuşma geçmişini paylaşır
memory = ConversationSummaryBufferMemory(
    llm=llm,
    max_token_limit=200,  # 200 token limit - maliyet kontrolü için
    memory_key="chat_history",  # Memory anahtarı - chain'lerde otomatik kullanılır
    return_messages=True  # Mesaj formatında döndür - LangChain uyumluluğu için
)

# Global chatbot instance
chatbot_instance: EmotionChatbot | None = None

# =============================================================================
# ÖZETLEYİCİ (SUMMARIZER) - Uzun kullanıcı mesajlarını kısaltmak için
# =============================================================================
# T5-small ile transformers pipeline kullanılır. Lazy-init yapılır ve tek instance
# tutulur. Kullanıcı mesajı yaklaşık 200 token'i aşarsa tetiklenir.
_summarizer_pipeline = None  # Lazy init: ilk kullanımda yüklenir

def _get_device_id() -> int:
    """Transformers pipeline için cihaz kimliğini döndürür.
    - CUDA (GPU) mevcutsa 0, değilse -1 (CPU)
    """
    try:
        import torch  # Yerinde import: bağımlılık yoksa hata kontrollü yakalanır
        return 0 if getattr(torch, "cuda", None) and torch.cuda.is_available() else -1
    except Exception:
        # Torch yoksa CPU kullan
        return -1


def _get_summarizer():
    """T5-small summarization pipeline'ını döndürür (lazy-init)."""
    global _summarizer_pipeline
    if _summarizer_pipeline is not None:
        return _summarizer_pipeline
    try:
        # Transformers'ı sadece gerektiğinde yükle
        from transformers import pipeline  # type: ignore
        device_id = _get_device_id()
        _summarizer_pipeline = pipeline(
            "summarization",
            model="t5-small",
            device=device_id,
        )
        return _summarizer_pipeline
    except Exception as e:
        # Özetleyici yüklenemezse None döndür ve akışı engelleme
        print(f"[SUMMARIZER] Yükleme hatası: {e}")
        return None


def _summarize_text_if_needed(text: str, estimated_tokens: int, token_threshold: int = 200) -> str:
    """Mesaj token tahmini eşik değerini aşıyorsa metni kısaltır.

    Güvenlik/sağlamlık notları:
    - Transformers bağımlılığı yoksa veya model yüklenemezse orijinal metni döndürür
    - T5 için "summarize:" prefix'i kullanılır; Türkçe girişlerde de çalışır
    - max_new_tokens/min_new_tokens, girdinin uzunluğuna göre ölçeklenir
    """
    try:
        if estimated_tokens <= token_threshold:
            return text

        summarizer = _get_summarizer()
        if summarizer is None:
            return text

        # T5 özetleme: İngilizce ön-ek; Türkçe için de kabul edilebilir
        prefixed = "summarize: " + text

        # Tokenizer varsa giriş uzunluğuna göre dinamik ayar yap
        try:
            input_len = len(summarizer.tokenizer(prefixed)["input_ids"])  # type: ignore[attr-defined]
        except Exception:
            # Tokenizer'a erişilemezse kaba tahmin ile çalış
            input_len = max(60, len(prefixed) // 4)

        # Çıkış uzunluğu: girişin ~%30-50'si; alt/üst sınırlar güvenlik için
        new_tokens = max(32, min(160, int(input_len * 0.4)))
        min_new = max(16, int(new_tokens * 0.4))

        result = summarizer(
            prefixed,
            max_new_tokens=new_tokens,
            min_new_tokens=min_new,
            do_sample=False,
        )
        summary = ""
        try:
            summary = (result[0] or {}).get("summary_text", "").strip()
        except Exception:
            summary = ""

        # Boş dönerse orijinal metni koru
        if not summary:
            return text

        # Konsola kısaltılmış çıktıyı yaz (istenen gereksinim)
        print(f"[SUMMARIZER] Kısaltılmış metin: {summary}")
        return summary
    except Exception as e:
        # Her türlü hata durumunda orijinal metni döndür
        print(f"[SUMMARIZER] Çalışma hatası: {e}")
        return text

# RAG modelini asenkron olarak önceden yükle
print("[CHAIN SYSTEM] RAG modeli asenkron olarak yükleniyor...")
rag_service.preload_model_async()

# LoRA modelini asenkron olarak önceden yükle - Global EmotionChatbot instance oluştur
print("[CHAIN SYSTEM] LoRA modeli asenkron olarak yükleniyor...")
# LoRA yüklemesi için EmotionChatbot instance'ı oluştur (client=None, Gemini kullanacak)
# Chat için lazım olana kadar beklenmez, sadece LoRA yüklemesi için
if chatbot_instance is None:
    chatbot_instance = EmotionChatbot()  # client=None, Gemini kullanacak
chatbot_instance.preload_lora_model_async()

# Güvenlik sabitleri
MAX_MESSAGE_LENGTH = 2000  # Maksimum mesaj uzunluğu
MAX_TOKENS_PER_REQUEST = 1000  # Maksimum token sayısı
DANGEROUS_PATTERNS = [
    r'<script[^>]*>.*?</script>',  # Script injection
    r'javascript:',  # JavaScript URL
    r'data:text/html',  # Data URL
    r'vbscript:',  # VBScript
    r'on\w+\s*=',  # Event handlers
    r'<iframe[^>]*>',  # Iframe injection
    r'<object[^>]*>',  # Object injection
    r'<embed[^>]*>',  # Embed injection
    r'<link[^>]*>',  # Link injection
    r'<meta[^>]*>',  # Meta injection
]

# RAG kaynakları (UI id'leri sabit: pdf-python/anayasa/clean)
RAG_SOURCES = {
    "cat_care.pdf": {"id": "pdf-python", "emoji": "🐱", "alias": "cat"},
    "parrot_care.pdf": {"id": "pdf-anayasa", "emoji": "🦜", "alias": "parrot"},
    "rabbit_care.pdf": {"id": "pdf-clean", "emoji": "🐰", "alias": "rabbit"},
}

# Static files (CSS/JS)
STATIC_DIR = Path(__file__).parent / "static"
try:
    STATIC_DIR.mkdir(parents=True, exist_ok=True)
except Exception:
    pass
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


class FlowDecisionParser(BaseOutputParser):
    """Akış kararı parser'ı - LLM çıktısını temizler"""
    
    def parse(self, text: str) -> str:
        """LLM çıktısını temizleyip akış kararını döndürür"""
        text = text.strip().upper()
        valid_flows = ["ANIMAL", "RAG", "EMOTION", "STATS", "HELP"]
        
        for flow in valid_flows:
            if flow in text:
                return flow
        
        return "HELP"  # Varsayılan fallback - yardım mesajı


def _sanitize_input(text: str) -> str:
    """Güvenli input sanitization - injection saldırılarını önler"""
    if not text:
        return ""
    
    # HTML escape
    text = html.escape(text, quote=True)
    
    # Tehlikeli pattern'leri kontrol et
    for pattern in DANGEROUS_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            print(f"[SECURITY] Tehlikeli pattern tespit edildi: {pattern}")
            return "[Güvenlik nedeniyle mesaj filtrelendi]"
    
    # Fazla boşlukları temizle
    text = re.sub(r'\s+', ' ', text).strip()
    
    return text


def _validate_message_length(text: str) -> bool:
    """Mesaj uzunluğunu kontrol eder"""
    return len(text) <= MAX_MESSAGE_LENGTH


def _estimate_tokens(text: str) -> int:
    """Yaklaşık token sayısını hesaplar (Türkçe için)"""
    # Türkçe için yaklaşık hesaplama: 1 token ≈ 4 karakter
    return len(text) // 4


# =============================================================================
# CHAIN SYSTEM - LangChain Chain Yapıları
# =============================================================================

def create_flow_decision_chain():
    """Akış kararı chain'i oluşturur - ConversationSummaryBufferMemory ile"""
    # Memory sistemi ile akış kararı - önceki konuşma bağlamı otomatik eklenir
    flow_prompt = PromptTemplate(
        input_variables=["input"],
        template="""Kullanıcının mesajını analiz et ve şu akışlardan birini seç:

ÖNEMLİ KURALLAR:
1. Eğer kullanıcı BİLGİ istiyorsa (hayvan bakımı, beslenme, barınma, sağlık, eğitim, bakım önerileri) → RAG
2. Eğer kullanıcı HAYVAN istiyorsa (köpek, kedi, tilki, ördek fotoğraf/bilgi) → ANIMAL  
3. Eğer kullanıcı SOHBET/DUYGU istiyorsa (merhaba, nasılsın, üzgünüm, mutluyum) → EMOTION
4. Eğer kullanıcı İSTATİSTİK/ÖZET istiyorsa ("kaç kez/defa", "istatistik", "özet", belirli duygu istatistiği, bugün/bugüne ait sayım) → STATS
5. Eğer kullanıcı hiçbir özelliği çağırmıyorsa (genel sorular, yardım, ne yapabilirsin) → HELP

Akışlar:
- ANIMAL: Köpek, kedi, tilki, ördek fotoğraf/bilgi isteği
- RAG: Kedi/Papağan/Tavşan bakımı, beslenme, barınma, sağlık, eğitim, bakım rutinleri
- EMOTION: Duygu analizi, sohbet, normal konuşma
- STATS: Duygu istatistikleri (today/all + isteğe bağlı duygu filtresi)
- HELP: Yardım, ne yapabilirsin, genel bilgi istekleri

Kullanıcı Mesajı: {input}

Sadece şu yanıtlardan birini ver: ANIMAL, RAG, EMOTION, STATS, HELP"""
    )
    
    def flow_processor(input_data):
        """Flow decision işleyicisi - Gemini ve OpenAI çıktılarını normalize eder"""
        result = (flow_prompt | llm).invoke(input_data)
        
        # Ham cevabı konsola yazdır
        print(f"[FLOW DEBUG] Ham result tipi: {type(result)}")
        print(f"[FLOW DEBUG] Ham result: {result}")
        
        # Gemini ve OpenAI çıktılarını normalize et
        if hasattr(result, 'content'):
            # LangChain response objesi
            text = result.content
            print(f"[FLOW DEBUG] Content: {text}")
        elif isinstance(result, str):
            # String çıktı
            text = result
            print(f"[FLOW DEBUG] String: {text}")
        else:
            # Diğer durumlar için string'e çevir
            text = str(result)
            print(f"[FLOW DEBUG] String'e çevriliyor: {text}")
        
        # FlowDecisionParser'ı kullan
        parser = FlowDecisionParser()
        parsed_result = parser.parse(text)
        print(f"[FLOW DEBUG] Parsed result: {parsed_result}")
        return parsed_result
    
    return flow_processor


def create_rag_chain():
    """RAG chain'i oluşturur - ConversationSummaryBufferMemory ile"""
    # Memory ile kullanırken sadece tek input variable kullan - chat_history otomatik eklenir
    # Context bilgisi prompt'a dahil edilir, memory sistemi konuşma geçmişini yönetir
    rag_prompt = PromptTemplate(
        input_variables=["input"],
        template="""Sen bir hayvan bakımı bilgi asistanısın. Verilen BAĞLAM (PDF parçaları) üzerinden
kullanıcının sorusunu YALNIZCA bağlama dayanarak yanıtla. Türkçe, kısa, net ve uygulanabilir yaz.

Kesin kurallar:
1) Doğrudan yanıt ver; bölüm/başlık/"git oku" tarzı yönlendirmeler yapma.
2) Bağlamdaki bilgileri özlü maddeler halinde veya kısa paragraflarla aktar.
3) Kaynak ve alıntı isimlerini yazma; sadece içerik ver.
4) Bağlam yeterli değilse bunu açıkça söyle: "Bağlamda yeterli bilgi yok."
5) JSON üretme; normal metin ver. Maksimum 5 cümle.

SORU VE BAĞLAM: {input}

YANIT:"""
    )
    
    def rag_processor(input_data):
        """RAG işleyicisi - Gemini ve OpenAI çıktılarını normalize eder"""
        result = (rag_prompt | llm).invoke(input_data)
        
        # Ham cevabı konsola yazdır
        print(f"[RAG DEBUG] Ham result tipi: {type(result)}")
        print(f"[RAG DEBUG] Ham result: {result}")
        
        # Gemini ve OpenAI çıktılarını normalize et
        if hasattr(result, 'content'):
            # LangChain response objesi
            print(f"[RAG DEBUG] Content: {result.content}")
            return result.content
        elif isinstance(result, str):
            # String çıktı
            print(f"[RAG DEBUG] String: {result}")
            return result
        else:
            # Diğer durumlar için string'e çevir
            print(f"[RAG DEBUG] String'e çevriliyor: {str(result)}")
            return str(result)
    
    return rag_processor


def create_animal_chain():
    """Animal chain'i oluşturur - API çağrısı yapar - ConversationSummaryBufferMemory ile"""
    def animal_processor(user_message: str) -> Dict[str, Any]:
        """Hayvan API'sini çağırır ve sonucu döndürür - memory sistemi ile timeout handling"""
        # Hayvan API'leri için timeout ve hata yönetimi
        # Memory sistemi ile konuşma geçmişi otomatik olarak yönetiliyor
        try:
            print("[ANIMAL CHAIN] Hayvan API'si çağrılıyor...")
            # OpenAI client oluştur - route_animals client bekliyor
            from openai import OpenAI
            client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
            animal_result = route_animals(user_message, client)
            
            if animal_result:
                animal = str(animal_result.get("animal", ""))
                out: Dict[str, Any] = {
                    "animal": animal,
                    "type": animal_result.get("type"),
                    "animal_emoji": _animal_emoji(animal),
                }
                if animal_result.get("type") == "image":
                    out["image_url"] = animal_result.get("image_url")
                    out["response"] = f"{_animal_emoji(animal)} {animal.capitalize()} fotoğrafı hazır."
                else:
                    out["response"] = animal_result.get("text", "")
                
                # Memory'ye animal yanıtını kaydet
                memory.save_context(
                    {"input": user_message},
                    {"output": out["response"]}
                )
                
                print(f"[ANIMAL CHAIN] Başarılı: {animal}")
                return out
            
            # Hayvan bulunamadı durumu için de memory'ye kaydet
            error_response = "Hayvan bulunamadı."
            memory.save_context(
                {"input": user_message},
                {"output": error_response}
            )
            print("[ANIMAL CHAIN] Hayvan bulunamadı")
            return {"response": error_response}
            
        except Exception as e:
            print(f"[ANIMAL CHAIN] Hata: {e}")
            # Timeout veya API hatası durumunda fallback yanıt
            error_response = "Hayvan API'si şu anda kullanılamıyor. Lütfen daha sonra tekrar deneyin."
            memory.save_context(
                {"input": user_message},
                {"output": error_response}
            )
            return {"response": error_response}
    
    return animal_processor


def create_emotion_chain():
    """Emotion chain'i oluşturur - ConversationSummaryBufferMemory ile"""
    def emotion_processor(user_message: str) -> Dict[str, Any]:
        """Duygu analizi yapar - memory sistemi ile"""
        # Emotion sistemi için OpenAI client oluşturma
        # Memory sistemi ile konuşma geçmişi otomatik olarak yönetiliyor
        global chatbot_instance
        if chatbot_instance is None:
            # Fallback mekanizması ile client oluştur
            try:
                from openai import OpenAI
                client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
                # Test çağrısı yap
                client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[{"role": "user", "content": "test"}],
                    max_tokens=1
                )
                chatbot_instance = EmotionChatbot(client)
                print("[EMOTION] OpenAI API kullanılıyor")
            except Exception:
                # OpenAI API key kullanılamıyor, Gemini kullan
                chatbot_instance = EmotionChatbot()  # client=None, Gemini kullanacak
                print("[EMOTION] Gemini API kullanılıyor")
        
        # Memory sistemi ile önceki konuşma geçmişi otomatik olarak yönetiliyor
        
        result = chatbot_instance.chat(user_message)
        
        # Memory'ye yeni konuşmayı kaydet
        memory.save_context(
            {"input": user_message},
            {"output": result.get("response", "")}
        )
        
        # Yeni emotion_system formatına uygun response döndür
        # Format: {"response": lora_response, "emoji": emoji, "mood": mood, "stats": stats}
        out = {
            "response": result.get("response", ""),
            "stats": result.get("stats", {}),
        }
        
        # Yeni format alanları ekle
        if "emoji" in result:
            out["emoji"] = result["emoji"]
        if "mood" in result:
            out["mood"] = result["mood"]
        
        return out
    
    return emotion_processor


def create_stats_chain():
    """Stats chain'i oluşturur - data/ dosyalarından hesaplar"""
    stats_system = StatisticSystem()

    def stats_processor(user_message: str) -> Dict[str, Any]:
        try:
            result = stats_system.answer(user_message)
            # Memory'ye kaydet
            memory.save_context({"input": user_message}, {"output": result.get("response", "")})
            return result
        except Exception as e:
            err = f"İstatistik sistemi hatası: {e}"
            memory.save_context({"input": user_message}, {"output": err})
            return {"response": err}

    return stats_processor

# =============================================================================
# CHAIN SYSTEM - Ana İşlem Zinciri
# =============================================================================

def create_main_processing_chain():
    """Ana işlem zinciri oluşturur"""
    
    # Alt chain'leri oluştur
    flow_decision_chain = create_flow_decision_chain()
    rag_chain = create_rag_chain()
    animal_processor = create_animal_chain()
    emotion_processor = create_emotion_chain()
    stats_processor = create_stats_chain()
    
    def process_message(user_message: str) -> Dict[str, Any]:
        """Ana mesaj işleme fonksiyonu - ConversationSummaryBufferMemory ile"""
        try:
            print("[CHAIN SYSTEM] AŞAMA 1: Akış kararı alınıyor...")
            
            # Memory sistemi aktif - ConversationSummaryBufferMemory ile konuşma geçmişi yönetiliyor
            
            # AŞAMA 1: Akış kararı
            flow_decision = flow_decision_chain({"input": user_message})
            print(f"[CHAIN SYSTEM] Akış kararı: {flow_decision}")
            
            # AŞAMA 2: Seçilen akışa göre işleme
            if flow_decision == "RAG":
                print("[CHAIN SYSTEM] AŞAMA 2: RAG akışı çalışıyor...")
                rag_result = _process_rag_flow(user_message, rag_chain)
                if rag_result is None:
                    print("[CHAIN SYSTEM] RAG sonucu None, HELP akışına yönlendiriliyor...")
                    help_result = _process_help_flow(user_message)
                    help_result["flow_type"] = "HELP"
                    return help_result
                rag_result["flow_type"] = "RAG"
                return rag_result
            elif flow_decision == "ANIMAL":
                print("[CHAIN SYSTEM] AŞAMA 2: Animal akışı çalışıyor...")
                animal_result = animal_processor(user_message)
                animal_result["flow_type"] = "ANIMAL"
                return animal_result
            elif flow_decision == "EMOTION":
                print("[CHAIN SYSTEM] AŞAMA 2: Emotion akışı çalışıyor...")
                emotion_result = emotion_processor(user_message)
                emotion_result["flow_type"] = "EMOTION"
                return emotion_result
            elif flow_decision == "STATS":
                print("[CHAIN SYSTEM] AŞAMA 2: Stats akışı çalışıyor...")
                stats_result = stats_processor(user_message)
                stats_result["flow_type"] = "STATS"
                return stats_result
            elif flow_decision == "HELP":
                print("[CHAIN SYSTEM] AŞAMA 2: Help akışı çalışıyor...")
                result = _process_help_flow(user_message)
                result["flow_type"] = "HELP"
                print(f"[CHAIN SYSTEM] Help result: {result}")
                return result
            else:
                print("[CHAIN SYSTEM] Fallback: Help akışı çalışıyor...")
                result = _process_help_flow(user_message)
                result["flow_type"] = "HELP"
                print(f"[CHAIN SYSTEM] Fallback result: {result}")
                return result
                
        except Exception as e:
            print(f"[CHAIN SYSTEM] Hata: {e}")
            return {"error": str(e)}
    
    return process_message


def _process_rag_flow(user_message: str, rag_chain) -> Dict[str, Any] | None:
    """RAG akışını işler - PDF'lerden bilgi çeker"""
    t = user_message.lower()
    
    # Heuristic: explicit source keywords (hayvan bakım)
    if ("kedi" in t or "cat" in t):
        source = "cat_care.pdf"
    elif ("papağan" in t or "parrot" in t or "kuş" in t):
        source = "parrot_care.pdf"
    elif ("tavşan" in t or "rabbit" in t):
        source = "rabbit_care.pdf"
    else:
        # LLM RAG seçtiyse anahtar kelime kontrolü yapmadan genel retrieval dene
        chunks = rag_service.retrieve_top(user_message, top_k=6)
        if not chunks:
            print("[RAG] RAG'de ilgili bilgi bulunamadı")
            return None
        context = "\n\n".join([c.get("text", "") for c in chunks])
        sources = list({(c.get("metadata", {}) or {}).get("source", "?") for c in chunks})
        
        # RAG chain ile işle - context'i prompt'a dahil et
        combined_input = f"BAĞLAM:\n{context}\n\nSORU: {user_message}"
        result = rag_chain({"input": combined_input})
        
        # Memory'ye RAG yanıtını kaydet
        memory.save_context(
            {"input": user_message},
            {"output": result if isinstance(result, str) else str(result)}
        )
        
        # Pick first known source for UI hint
        lit = None
        for s in sources:
            if s in RAG_SOURCES:
                lit = s
                break
        ui = RAG_SOURCES.get(lit or "", None)
        return {
            "rag": True,
            "response": result if isinstance(result, str) else str(result),
            "rag_source": ui.get("id") if ui else None,
            "rag_emoji": ui.get("emoji") if ui else None,
        }

    # Source-filtered retrieval
    chunks = rag_service.retrieve_by_source(user_message, source_filename=source, top_k=6)
    if not chunks:
        return None
    context = "\n\n".join([c.get("text", "") for c in chunks])
    
    # RAG chain ile işle - context'i prompt'a dahil et
    combined_input = f"BAĞLAM:\n{context}\n\nSORU: {user_message}"
    result = rag_chain({"input": combined_input})
    
    # Memory'ye RAG yanıtını kaydet
    memory.save_context(
        {"input": user_message},
        {"output": result if isinstance(result, str) else str(result)}
    )
    
    ui = RAG_SOURCES.get(source)
    return {
        "rag": True,
        "response": result if isinstance(result, str) else str(result),
        "rag_source": ui.get("id"),
        "rag_emoji": ui.get("emoji"),
    }


def _process_help_flow(user_message: str) -> Dict[str, Any]:
    """Help akışını işler - kullanıcıya yönlendirici mesaj verir"""
    help_message = """🤖 Merhaba! Ben akıllı bir chatbot'um ve size şu özelliklerle yardımcı olabilirim:

📚 **BİLGİ SİSTEMİ (RAG)**: 
• Kedi / Papağan / Tavşan bakımı (beslenme, barınma, sağlık, eğitim)
• "Kedi yavrusu nasıl beslenir?", "Papağan kafes bakımı nasıl yapılır?", "Tavşan tırnak kesimi nasıl yapılır?"

🐶 **HAYVAN SİSTEMİ**:
• Köpek, kedi, tilki, ördek fotoğraf ve bilgileri
• "köpek fotoğrafı ver", "kedi bilgisi ver" gibi istekler

💭 **DUYGU ANALİZİ**:
• Duygularınızı analiz eder ve size uygun yanıtlar verir
• "Bugün çok mutluyum", "Üzgün hissediyorum" gibi mesajlar

🎯 **KULLANIM**: Ekranda gördüğünüz kutucukları kullanarak veya yukarıdaki örnekler gibi mesajlar göndererek bu chatbot'u kullanabilirsiniz!"""
    
    # Memory'ye help yanıtını kaydet
    memory.save_context(
        {"input": user_message},
        {"output": help_message}
    )
    
    return {
        "help": True,
        "response": help_message
    }


# Ana chain'i oluştur
main_chain = create_main_processing_chain()


# =============================================================================
# FASTAPI ENDPOINTS
# =============================================================================

@app.get("/", response_class=HTMLResponse)
def index() -> HTMLResponse:
    """Ana sayfa HTML'ini döndürür"""
    template_path = Path(__file__).parent / "templates" / "index.html"
    try:
        html = template_path.read_text(encoding="utf-8")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"HTML yüklenemedi: {e}")
    return HTMLResponse(content=html)


@app.post("/chat")
def chat(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Ana chat endpoint'i - CHAIN SYSTEM ile akış yönlendirmesi yapar"""
    user_message = str(payload.get("message", "")).strip()
    
    # Güvenlik kontrolleri
    if not user_message:
        return {"error": "Mesaj boş olamaz"}
    
    # Mesaj uzunluk kontrolü
    if not _validate_message_length(user_message):
        return {"error": f"Mesaj çok uzun. Maksimum {MAX_MESSAGE_LENGTH} karakter olabilir."}
    
    # Input sanitization
    user_message = _sanitize_input(user_message)
    if user_message == "[Güvenlik nedeniyle mesaj filtrelendi]":
        return {"error": "Güvenlik nedeniyle mesaj filtrelendi"}
    
    # Token kontrolü
    estimated_tokens = _estimate_tokens(user_message)
    # 200+ token ise önce özetlemeyi dene (kaba tahmin üzerinden)
    user_message = _summarize_text_if_needed(user_message, estimated_tokens, token_threshold=200)
    # Özet sonrası yeniden tahmini token sayısı al (sert limit için paylaşımcı davranış)
    estimated_tokens = _estimate_tokens(user_message)
    if estimated_tokens > MAX_TOKENS_PER_REQUEST:
        return {"error": f"Çok fazla token. Maksimum {MAX_TOKENS_PER_REQUEST} token olabilir."}

    try:
        # CHAIN SYSTEM ile mesaj işleme
        print("[CHAIN SYSTEM] Mesaj işleniyor...")
        result = main_chain(user_message)
        
        # Result'u kontrol et ve hata varsa düzelt
        if isinstance(result, dict) and "error" in result:
            print(f"[CHAIN SYSTEM] Hata tespit edildi: {result['error']}")
            return {"error": result["error"]}
        
        # Result'un geçerli olduğundan emin ol
        if not isinstance(result, dict):
            print(f"[CHAIN SYSTEM] Geçersiz result tipi: {type(result)}")
            return {"error": "Geçersiz response formatı"}
            
        print(f"[CHAIN SYSTEM] Başarılı response: {result}")
        return result

    except HTTPException as e:
        print(f"[CHAIN SYSTEM] HTTPException: {e.detail}")
        return {"error": e.detail}
    except Exception as e:
        print(f"[CHAIN SYSTEM] Exception: {str(e)}")
        return {"error": f"Sunucu hatası: {str(e)}"}


# Çalıştırma:
# uvicorn api_web_chatbot:app --host 0.0.0.0 --port 8000 --reload

if __name__ == "__main__":
    """Script doğrudan çalıştırıldığında Uvicorn ile sunucuyu başlatır.
    - Host: 0.0.0.0
    - Port: 8000
    - Reload: True (geliştirme için otomatik yeniden yükleme)
    """
    try:
        # Uvicorn'u sadece ihtiyaç olduğunda import et (dinamik import)
        import uvicorn  # type: ignore
        # Modül:app şeklinde string kullanmak, reload modunda sağlıklı yeniden yükleme sağlar
        uvicorn.run("api_web_chatbot:app", host="0.0.0.0", port=8000, reload=True)
    except Exception as e:
        # Çalışma zamanında oluşabilecek hataları kullanıcıya bildir
        print(f"[SERVER] Uvicorn başlatma hatası: {e}")