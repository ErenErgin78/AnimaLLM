"""Ana Chatbot Sistemi - LangChain chain yapısı ile sistem koordinasyonu"""

import os
import re
import html
import asyncio
import json
import time
import warnings
import logging
import traceback
from typing import Any, Dict
from pathlib import Path

from fastapi import FastAPI, HTTPException, Header, Query
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from langchain_openai import OpenAI
from langchain.prompts import PromptTemplate
from langchain.schema import BaseOutputParser
from langchain_google_genai import ChatGoogleGenerativeAI

import google.generativeai as genai
import torch
from transformers import pipeline
from openai import OpenAI as OpenAIClient

from Tools.emotion_system import EmotionChatbot
from Tools.statistic_system import StatisticSystem
from Tools.animal_system import route_animals, _animal_emoji
from Tools.rag_service import rag_service

from Auth.routes import router as auth_router
from Auth.database import init_db, get_db
from Auth.auth_service import verify_token
from Auth.conversation_service import (
    create_conversation, get_conversation_by_id,
    add_message_to_conversation, update_conversation_title
)
from Auth.models import User, Conversation, ChatHistory
from sqlalchemy import func
from datetime import datetime
from pydantic import BaseModel

import uvicorn

load_dotenv()

app = FastAPI(title="CHAIN SYSTEM - Akıllı Chatbot Sistemi", version="3.0.0")

# CORS middleware ekle - n8n ve diğer external client'lar için
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Production'da spesifik domain'ler belirtilmeli
    allow_credentials=True,
    allow_methods=["*"],  # Tüm HTTP method'larına izin ver (GET, POST, OPTIONS, vb.)
    allow_headers=["*"],  # Tüm header'lara izin ver
)

app.include_router(auth_router)

try:
    init_db()
except Exception as e:
    print(f"[MAIN ERROR] Veritabanı başlatma hatası: {e}")

def get_llm():
    """LLM instance oluşturur - OpenAI veya Gemini"""
    warnings.filterwarnings("ignore")
    os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
    os.environ['GRPC_VERBOSITY'] = 'ERROR'
    logging.getLogger("transformers").setLevel(logging.ERROR)
    logging.getLogger("google").setLevel(logging.ERROR)
    logging.getLogger("google.api_core").setLevel(logging.ERROR)
    logging.getLogger("absl").setLevel(logging.ERROR)
    
    try:
        test_llm = OpenAI(temperature=0.1, max_tokens=1000, request_timeout=15)
        test_llm.invoke("test")
        print("[LLM] OpenAI API kullanılıyor")
        return test_llm
    except Exception:
        print("[LLM] OpenAI API key kullanılamıyor")
        try:
            api_key = os.getenv("GEMINI_API_KEY")
            if not api_key:
                raise Exception("GEMINI_API_KEY bulunamadı")
            genai.configure(api_key=api_key)
            
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

chatbot_instance: EmotionChatbot | None = None

def save_message_to_conversation(
    user_id: int | None,
    conversation_id: int | None,
    user_message: str,
    bot_response: str,
    flow_type: str | None = None
) -> int | None:
    """Mesajı conversation'a kaydeder"""
    if user_id is None:
        return None
    
    try:
        db = next(get_db())
        try:
            if conversation_id is None:
                title = user_message[:50].strip()
                if not title:
                    title = "Yeni Sohbet"
                
                new_conversation = create_conversation(
                    db=db,
                    user_id=user_id,
                    title=title
                )
                conversation_id = new_conversation.id
                print(f"[CONVERSATION] Yeni conversation oluşturuldu: conversation_id={conversation_id}, title='{title}'")
            else:
                existing_conv = get_conversation_by_id(db, conversation_id, user_id)
                if not existing_conv:
                    title = user_message[:50].strip()
                    if not title:
                        title = "Yeni Sohbet"
                    new_conversation = create_conversation(
                        db=db,
                        user_id=user_id,
                        title=title
                    )
                    conversation_id = new_conversation.id
                    print(f"[CONVERSATION] Conversation bulunamadı, yeni oluşturuldu: conversation_id={conversation_id}")
            
            add_message_to_conversation(
                db=db,
                conversation_id=conversation_id,
                user_id=user_id,
                user_message=user_message,
                bot_response=bot_response,
                flow_type=flow_type
            )
            print(f"[CONVERSATION] Mesaj eklendi: conversation_id={conversation_id}, flow_type={flow_type}")
            
            return conversation_id
        finally:
            db.close()
    except Exception as e:
        print(f"[CONVERSATION ERROR] Mesaj kaydedilemedi: {e}")
        return None


def get_current_user_id_optional(authorization: str | None = None) -> int | None:
    """JWT token'dan kullanıcı ID'sini alır"""
    if not authorization:
        return None
    
    try:
        if not authorization.startswith("Bearer "):
            return None
        
        token = authorization.replace("Bearer ", "").strip()
        if not token:
            return None
        
        payload = verify_token(token)
        if payload is None:
            return None
        
        user_id_str = payload.get("sub")
        if user_id_str is None:
            return None
        
        try:
            return int(user_id_str)
        except (ValueError, TypeError):
            return None
    except Exception:
        return None

_summarizer_pipeline = None

def _get_device_id() -> int:
    """GPU/CPU cihaz ID'sini döndürür"""
    try:
        return 0 if getattr(torch, "cuda", None) and torch.cuda.is_available() else -1
    except Exception:
        return -1


def _get_summarizer():
    """T5-small summarization pipeline'ını döndürür"""
    global _summarizer_pipeline
    if _summarizer_pipeline is not None:
        return _summarizer_pipeline
    try:
        device_id = _get_device_id()
        _summarizer_pipeline = pipeline(
            "summarization",
            model="t5-small",
            device=device_id,
        )
        return _summarizer_pipeline
    except Exception as e:
        print(f"[SUMMARIZER] Yükleme hatası: {e}")
        return None


def _summarize_text_if_needed(text: str, estimated_tokens: int, token_threshold: int = 200) -> str:
    """Token eşiğini aşan metni kısaltır"""
    try:
        if estimated_tokens <= token_threshold:
            return text

        summarizer = _get_summarizer()
        if summarizer is None:
            return text

        prefixed = "summarize: " + text

        try:
            input_len = len(summarizer.tokenizer(prefixed)["input_ids"])
        except Exception:
            input_len = max(60, len(prefixed) // 4)

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

        if not summary:
            return text

        print(f"[SUMMARIZER] Kısaltılmış metin: {summary}")
        return summary
    except Exception as e:
        print(f"[SUMMARIZER] Çalışma hatası: {e}")
        return text

rag_service.preload_model_async()

if chatbot_instance is None:
    chatbot_instance = EmotionChatbot()
chatbot_instance.preload_lora_model_async()

MAX_MESSAGE_LENGTH = 2000
MAX_TOKENS_PER_REQUEST = 1000
DANGEROUS_PATTERNS = [
    r'<script[^>]*>.*?</script>',
    r'javascript:',
    r'data:text/html',
    r'vbscript:',
    r'on\w+\s*=',
    r'<iframe[^>]*>',
    r'<object[^>]*>',
    r'<embed[^>]*>',
    r'<link[^>]*>',
    r'<meta[^>]*>',
]

RAG_SOURCES = {
    "cat_care.pdf": {"id": "pdf-python", "emoji": "🐱", "alias": "cat"},
    "parrot_care.pdf": {"id": "pdf-anayasa", "emoji": "🦜", "alias": "parrot"},
    "rabbit_care.pdf": {"id": "pdf-clean", "emoji": "🐰", "alias": "rabbit"},
}

STATIC_DIR = Path(__file__).parent / "Frontend"
try:
    STATIC_DIR.mkdir(parents=True, exist_ok=True)
except Exception:
    pass
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


class FlowDecisionParser(BaseOutputParser):
    """LLM çıktısını akış kararına çevirir"""
    
    def parse(self, text: str) -> str:
        """LLM çıktısını parse eder"""
        text = text.strip().upper()
        valid_flows = ["ANIMAL", "RAG", "EMOTION", "STATS", "HELP"]
        
        for flow in valid_flows:
            if flow in text:
                return flow
        
        return "HELP"


def _sanitize_input(text: str) -> str:
    """Input sanitization"""
    if not text:
        return ""
    
    text = html.escape(text, quote=True)
    
    for pattern in DANGEROUS_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            print(f"[SECURITY] Tehlikeli pattern tespit edildi: {pattern}")
            return "[Güvenlik nedeniyle mesaj filtrelendi]"
    
    text = re.sub(r'\s+', ' ', text).strip()
    
    return text


def _validate_message_length(text: str) -> bool:
    """Mesaj uzunluğunu kontrol eder"""
    return len(text) <= MAX_MESSAGE_LENGTH


def _estimate_tokens(text: str) -> int:
    """Token sayısını tahmin eder"""
    return len(text) // 4


def create_flow_decision_chain():
    """Akış kararı chain'i oluşturur"""
    flow_prompt = PromptTemplate(
        input_variables=["input"],
        template="""Kullanıcının mesajını analiz et ve şu akışlardan birini seç: ANIMAL, RAG, EMOTION, STATS, HELP.

        ÖNEMLİ KURALLAR (ÖNCELİK SIRASI):
        1. Eğer kullanıcı HAYVAN BİLGİSİ/FOTOĞRAFI istiyorsa (kedi bilgisi, köpek bilgisi, kedi fotoğrafı, köpek fotoğrafı, tilki fotoğrafı, ördek fotoğrafı) → MUTLAKA ANIMAL
        2. Eğer mesajda "PDF", "bağlam", "bakım", "hastalık", "sağlık", "beslenme", "barınma", "eğitim" veya hayvan bakımı ile ilgili detaylı bilgi sorusu varsa → RAG
        3. Eğer kullanıcı HAYVAN BAKIMI hakkında bilgi istiyorsa (Kedi/Papağan/Tavşan bakımı, beslenme, barınma, sağlık, hastalıklar, eğitim, bakım önerileri) → RAG
        4. Eğer kullanıcı SOHBET/DUYGU istiyorsa (merhaba, nasılsın, üzgünüm, mutluyum) → EMOTION
        5. Eğer kullanıcı İSTATİSTİK/ÖZET istiyorsa ("kaç kez/defa", "istatistik", "özet", belirli duygu istatistiği, bugün/bugüne ait sayım) → STATS
        6. Eğer kullanıcı hiçbir özelliği çağırmıyorsa (genel sorular, yardım, ne yapabilirsin) → HELP

        Akışlar:
        - ANIMAL: Köpek, kedi, tilki, ördek fotoğrafı veya bilgisi isteği (örnek: "kedi bilgisi", "köpek fotoğrafı", "kedi fotoğrafı ver")
        - RAG: Kedi/Papağan/Tavşan bakımı, beslenme, barınma, sağlık, hastalıklar, eğitim, bakım rutinleri, PDF bağlamı (örnek: "kedi bakımı nasıl yapılır", "papağan hastalıkları")
        - EMOTION: Duygu analizi, sohbet, normal konuşma
        - STATS: Duygu istatistikleri (today/all + isteğe bağlı duygu filtresi)
        - HELP: Yardım, ne yapabilirsin, genel bilgi istekleri

        ÖRNEKLER:
        - "Bana bir köpek fotoğrafı ver" → ANIMAL
        - "Bana bir kedi bilgisi ver" → ANIMAL
        - "kedi bakımı nasıl yapılır" → RAG
        - "papağan hastalıkları" → RAG

        Kullanıcı Mesajı: {input}

        Sadece şu yanıtlardan birini ver: ANIMAL, RAG, EMOTION, STATS, HELP"""
    )
    
    async def flow_processor(input_data):
        """Flow decision işleyicisi"""
        try:
            print(f"[FLOW DEBUG] Input data: {input_data}")
            print(f"[FLOW DEBUG] LLM çağrısı başlatılıyor (async)...")
            
            try:
                chain = flow_prompt | llm
                result = await asyncio.wait_for(
                    chain.ainvoke(input_data),
                    timeout=30.0
                )
            except asyncio.TimeoutError:
                print("[FLOW ERROR] LLM çağrısı timeout oldu (30 saniye)")
                return "HELP"
            except Exception as e:
                print(f"[FLOW ERROR] LLM çağrısı hatası: {e}")
                return "HELP"
            
            if result is None:
                print("[FLOW ERROR] LLM çağrısı None döndü")
                return "HELP"
            
            print(f"[FLOW DEBUG] Ham result tipi: {type(result)}")
            print(f"[FLOW DEBUG] Ham result: {result}")
            
            if hasattr(result, 'content'):
                text = result.content
                print(f"[FLOW DEBUG] Content: {text}")
            elif isinstance(result, str):
                text = result
                print(f"[FLOW DEBUG] String: {text}")
            else:
                text = str(result)
                print(f"[FLOW DEBUG] String'e çevriliyor: {text}")
            
            parser = FlowDecisionParser()
            parsed_result = parser.parse(text)
            print(f"[FLOW DEBUG] Parsed result: {parsed_result}")
            return parsed_result
            
        except Exception as e:
            print(f"[FLOW ERROR] Beklenmeyen hata: {e}")
            traceback.print_exc()
            return "HELP"
    
    return flow_processor


def create_rag_chain():
    """RAG chain'i oluşturur"""
    rag_prompt = PromptTemplate(
        input_variables=["input"],
        template="""Sen bir hayvan bakımı bilgi asistanısın. Verilen kullanıcı mesajını kullanarak kullanıcının sorusunu yanıtla. 
        Türkçe, kısa, net ve uygulanabilir yaz.
        Rag sistemini kullan, bilgileri bul ve kullanıcıya ver. Normal text formatında ve en fazla 5 cümle olsun.
        Rag sistemini her zaman kullanman zorunlu.
        Kullanıcı Mesajı: {input}"""
    )
    
    async def rag_processor(input_data, stream: bool = False):
        """RAG işleyicisi"""
        try:       
            if stream:
                print(f"[RAG DEBUG] Streaming modu aktif, LLM çağrısı başlatılıyor (async)...")
                
                try:
                    api_key = os.getenv("GEMINI_API_KEY")
                    if api_key:
                        genai.configure(api_key=api_key)
                        model = genai.GenerativeModel('gemini-2.5-flash')
                        
                        formatted_prompt = rag_prompt.format(**input_data)
                        
                        async def generate_stream():
                            try:
                                response = model.generate_content(
                                    formatted_prompt,
                                    stream=True
                                )
                                
                                chunk_count = 0
                                for chunk in response:
                                    try:
                                        # Response'un geçerli olup olmadığını kontrol et
                                        if hasattr(chunk, 'candidates') and chunk.candidates:
                                            candidate = chunk.candidates[0]
                                            
                                            # finish_reason kontrolü - güvenlik ve diğer engellemeler
                                            finish_reason = None
                                            if hasattr(candidate, 'finish_reason'):
                                                finish_reason = candidate.finish_reason
                                            
                                            # finish_reason değeri kontrolü (int veya enum olabilir)
                                            if finish_reason is not None:
                                                finish_reason_val = finish_reason
                                                # Enum ise değerini al
                                                if hasattr(finish_reason, 'value'):
                                                    finish_reason_val = finish_reason.value
                                                elif hasattr(finish_reason, 'name'):
                                                    finish_reason_name = finish_reason.name
                                                    # MAX_TOKENS, vb. kontrolü
                                                    if finish_reason_val != 0:  # 0 = UNSPECIFIED
                                                        print(f"[RAG WARNING] finish_reason: {finish_reason_name or finish_reason_val}")
                                            
                                            # Text içeriğini güvenli şekilde oku - parts kontrolü
                                            if hasattr(candidate, 'content') and candidate.content:
                                                if hasattr(candidate.content, 'parts') and candidate.content.parts:
                                                    for part in candidate.content.parts:
                                                        if hasattr(part, 'text') and part.text:
                                                            chunk_count += 1
                                                            yield part.text
                                                # Eğer parts yoksa ama text direkt varsa
                                                elif hasattr(candidate.content, 'text') and candidate.content.text:
                                                    chunk_count += 1
                                                    yield candidate.content.text
                                        elif hasattr(chunk, 'text') and chunk.text:
                                            # Direkt text varsa kullan
                                            chunk_count += 1
                                            yield chunk.text
                                    except AttributeError as ae:
                                        # response.text quick accessor hatası - parts kontrolü yapıldı
                                        print(f"[RAG WARNING] Chunk attribute hatası: {ae}")
                                        continue
                                    except Exception as chunk_error:
                                        print(f"[RAG WARNING] Chunk işleme hatası: {chunk_error}")
                                        continue
                                    
                                    await asyncio.sleep(0)
                                
                                if chunk_count == 0:
                                    print("[RAG ERROR] Hiçbir chunk içeriği alınamadı")
                                    return
                                    
                            except Exception as e:
                                print(f"[RAG ERROR] Streaming hatası: {e}")
                                traceback.print_exc()
                                return
                        
                        return generate_stream()
                except Exception as e:
                    print(f"[RAG ERROR] Gemini streaming hatası: {e}")
                    pass
            
            print(f"[RAG DEBUG] Normal mod, LLM çağrısı başlatılıyor (async)...")
            
            try:
                chain = rag_prompt | llm
                result = await asyncio.wait_for(
                    chain.ainvoke(input_data),
                    timeout=30.0
                )
            except asyncio.TimeoutError:
                print("[RAG ERROR] LLM çağrısı timeout oldu (30 saniye)")
                return "Üzgünüm, şu anda yanıt veremiyorum. Lütfen daha sonra tekrar deneyin."
            except Exception as e:
                print(f"[RAG ERROR] LLM çağrısı hatası: {e}")
                traceback.print_exc()
                return "Üzgünüm, şu anda yanıt veremiyorum. Lütfen daha sonra tekrar deneyin."
            
            if result is None:
                print("[RAG ERROR] LLM çağrısı None döndü")
                return "Üzgünüm, şu anda yanıt veremiyorum. Lütfen daha sonra tekrar deneyin."
            
            print(f"[RAG DEBUG] Ham result tipi: {type(result)}")
            print(f"[RAG DEBUG] Ham result: {result}")
            
            if hasattr(result, 'content'):
                print(f"[RAG DEBUG] Content: {result.content}")
                return result.content
            elif isinstance(result, str):
                print(f"[RAG DEBUG] String: {result}")
                return result
            else:
                print(f"[RAG DEBUG] String'e çevriliyor: {str(result)}")
                return str(result)
                
        except Exception as e:
            print(f"[RAG ERROR] Beklenmeyen hata: {e}")
            traceback.print_exc()
            return "Üzgünüm, şu anda yanıt veremiyorum. Lütfen daha sonra tekrar deneyin."
    
    return rag_processor


def create_animal_chain():
    """Animal chain'i oluşturur"""
    def animal_processor(user_message: str, user_id: int | None = None) -> Dict[str, Any]:
        """Hayvan API'sini çağırır"""
        try:
            print("[ANIMAL CHAIN] Hayvan API'si çağrılıyor...")
            client = OpenAIClient(api_key=os.getenv("OPENAI_API_KEY"))
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
                
                print(f"[ANIMAL CHAIN] Başarılı: {animal}")
                return out
            
            error_response = "Hayvan bulunamadı."
            print("[ANIMAL CHAIN] Hayvan bulunamadı")
            return {"response": error_response}
            
        except Exception as e:
            print(f"[ANIMAL CHAIN] Hata: {e}")
            error_response = "Hayvan API'si şu anda kullanılamıyor. Lütfen daha sonra tekrar deneyin."
            return {"response": error_response}
    
    return animal_processor


def create_emotion_chain():
    """Emotion chain'i oluşturur"""
    def emotion_processor(user_message: str, user_id: int | None = None) -> Dict[str, Any]:
        """Duygu analizi yapar"""
        global chatbot_instance
        if chatbot_instance is None:
            try:
                client = OpenAIClient(api_key=os.getenv("OPENAI_API_KEY"))
                client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[{"role": "user", "content": "test"}],
                    max_tokens=1
                )
                chatbot_instance = EmotionChatbot(client)
                print("[EMOTION] OpenAI API kullanılıyor")
            except Exception:
                chatbot_instance = EmotionChatbot()
                print("[EMOTION] Gemini API kullanılıyor")
        
        result = chatbot_instance.chat(user_message, user_id)
        
        out = {
            "response": result.get("response", ""),
            "stats": result.get("stats", {}),
        }
        
        if "emoji" in result:
            out["emoji"] = result["emoji"]
        if "mood" in result:
            out["mood"] = result["mood"]
        
        return out
    
    return emotion_processor


def create_stats_chain():
    """Stats chain'i oluşturur"""
    stats_system = StatisticSystem()

    def stats_processor(user_message: str, user_id: int | None = None) -> Dict[str, Any]:
        try:
            result = stats_system.answer(user_message, user_id)
            return result
        except Exception as e:
            err = f"İstatistik sistemi hatası: {e}"
            return {"response": err}

    return stats_processor

def create_main_processing_chain():
    """Ana işlem zinciri oluşturur"""
    
    flow_decision_chain = create_flow_decision_chain()
    rag_chain = create_rag_chain()
    animal_processor = create_animal_chain()
    emotion_processor = create_emotion_chain()
    stats_processor = create_stats_chain()
    
    async def process_message(user_message: str, user_id: int | None = None, **kwargs) -> Dict[str, Any]:
        """Ana mesaj işleme fonksiyonu"""
        try:
            print("[CHAIN SYSTEM] AŞAMA 1: Akış kararı alınıyor (async)...")
            
            flow_decision = await flow_decision_chain({"input": user_message})
            print(f"[CHAIN SYSTEM] Akış kararı: {flow_decision}")
            
            result = None
            if flow_decision == "RAG":
                print("[CHAIN SYSTEM] AŞAMA 2: RAG akışı çalışıyor (async)...")
                stream = kwargs.get("stream", False)
                rag_result = await _process_rag_flow(user_message, rag_chain, stream=stream)
                if rag_result is None:
                    print("[CHAIN SYSTEM] RAG sonucu None, HELP akışına yönlendiriliyor...")
                    help_result = _process_help_flow(user_message)
                    help_result["flow_type"] = "HELP"
                    result = help_result
                else:
                    if stream and (hasattr(rag_result, '__aiter__') or (hasattr(rag_result, '__iter__') and not isinstance(rag_result, dict))):
                        return rag_result
                    if isinstance(rag_result, dict):
                        rag_result["flow_type"] = "RAG"
                        result = rag_result
                    else:
                        result = {"response": str(rag_result), "flow_type": "RAG"}
            elif flow_decision == "ANIMAL":
                print("[CHAIN SYSTEM] AŞAMA 2: Animal akışı çalışıyor...")
                animal_result = animal_processor(user_message, user_id)
                animal_result["flow_type"] = "ANIMAL"
                result = animal_result
            elif flow_decision == "EMOTION":
                print("[CHAIN SYSTEM] AŞAMA 2: Emotion akışı çalışıyor...")
                emotion_result = emotion_processor(user_message, user_id)
                emotion_result["flow_type"] = "EMOTION"
                result = emotion_result
            elif flow_decision == "STATS":
                print("[CHAIN SYSTEM] AŞAMA 2: Stats akışı çalışıyor...")
                stats_result = stats_processor(user_message, user_id)
                stats_result["flow_type"] = "STATS"
                result = stats_result
            elif flow_decision == "HELP":
                print("[CHAIN SYSTEM] AŞAMA 2: Help akışı çalışıyor...")
                help_result = _process_help_flow(user_message)
                help_result["flow_type"] = "HELP"
                result = help_result
            else:
                print("[CHAIN SYSTEM] Fallback: Help akışı çalışıyor...")
                help_result = _process_help_flow(user_message)
                help_result["flow_type"] = "HELP"
                result = help_result
            
            return result
                
        except Exception as e:
            print(f"[CHAIN SYSTEM] Hata: {e}")
            return {"error": str(e)}
    
    return process_message


async def _process_rag_flow(user_message: str, rag_chain, stream: bool = False):
    """RAG akışını işler"""
    t = user_message.lower()
    
    if ("kedi" in t or "cat" in t):
        source = "cat_care.pdf"
    elif ("papağan" in t or "parrot" in t or "kuş" in t):
        source = "parrot_care.pdf"
    elif ("tavşan" in t or "rabbit" in t):
        source = "rabbit_care.pdf"
    else:
        chunks = rag_service.retrieve_top(user_message, top_k=6)
        if not chunks:
            print("[RAG] RAG'de ilgili bilgi bulunamadı")
            return None
        
        context_parts = [c.get("text", "").strip() for c in chunks if c.get("text", "").strip()]
        context = "\n\n".join(context_parts)
        
        if not context or len(context.strip()) < 50:
            print(f"[RAG WARNING] Context çok kısa veya boş: {len(context)} karakter, chunks: {len(chunks)}")
            print(f"[RAG DEBUG] İlk chunk örneği: {chunks[0] if chunks else 'YOK'}")
        
        print(f"[RAG DEBUG] Context uzunluğu: {len(context)} karakter")
        sources = list({(c.get("metadata", {}) or {}).get("source", "?") for c in chunks})
        
        combined_input = f"BAĞLAM:\n{context}\n\nSORU: {user_message}"
        result = await rag_chain({"input": combined_input}, stream=stream)
        
        if stream and hasattr(result, '__aiter__'):
            lit = None
            for s in sources:
                if s in RAG_SOURCES:
                    lit = s
                    break
            ui = RAG_SOURCES.get(lit or "", None)
            
            async def stream_wrapper():
                metadata = {
                    "type": "metadata",
                    "rag": True,
                    "rag_source": ui.get("id") if ui else None,
                    "rag_emoji": ui.get("emoji") if ui else None,
                }
                yield f"data: {json.dumps(metadata, ensure_ascii=False)}\n\n"
                
                async for chunk in result:
                    if chunk:
                        data = {
                            "type": "chunk",
                            "content": chunk
                        }
                        yield f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
            
            return stream_wrapper()
        elif stream and hasattr(result, '__iter__') and not isinstance(result, str):
            lit = None
            for s in sources:
                if s in RAG_SOURCES:
                    lit = s
                    break
            ui = RAG_SOURCES.get(lit or "", None)
            
            def stream_wrapper():
                metadata = {
                    "type": "metadata",
                    "rag": True,
                    "rag_source": ui.get("id") if ui else None,
                    "rag_emoji": ui.get("emoji") if ui else None,
                }
                yield f"data: {json.dumps(metadata, ensure_ascii=False)}\n\n"
                
                for chunk in result:
                    if chunk:
                        data = {
                            "type": "chunk",
                            "content": chunk
                        }
                        yield f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
            
            return stream_wrapper()
        
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

    chunks = rag_service.retrieve_by_source(user_message, source_filename=source, top_k=6)
    if not chunks:
        return None
    
    context_parts = [c.get("text", "").strip() for c in chunks if c.get("text", "").strip()]
    context = "\n\n".join(context_parts)
    
    if not context or len(context.strip()) < 50:
        print(f"[RAG WARNING] Context çok kısa veya boş: {len(context)} karakter, chunks: {len(chunks)}")
        print(f"[RAG DEBUG] İlk chunk örneği: {chunks[0] if chunks else 'YOK'}")
    
    combined_input = f"BAĞLAM:\n{context}\n\nSORU: {user_message}"
    print(f"[RAG DEBUG] Context uzunluğu: {len(context)} karakter")
    result = await rag_chain({"input": combined_input}, stream=stream)
    
    if stream and hasattr(result, '__aiter__'):
        ui = RAG_SOURCES.get(source)
        
        async def stream_wrapper():
            metadata = {
                "type": "metadata",
                "rag": True,
                "rag_source": ui.get("id") if ui else None,
                "rag_emoji": ui.get("emoji") if ui else None,
            }
            yield f"data: {json.dumps(metadata, ensure_ascii=False)}\n\n"
            
            async for chunk in result:
                if chunk:
                    data = {
                        "type": "chunk",
                        "content": chunk
                    }
                    yield f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
        
        return stream_wrapper()
    elif stream and hasattr(result, '__iter__') and not isinstance(result, str):
        ui = RAG_SOURCES.get(source)
        
        def stream_wrapper():
            metadata = {
                "type": "metadata",
                "rag": True,
                "rag_source": ui.get("id") if ui else None,
                "rag_emoji": ui.get("emoji") if ui else None,
            }
            yield f"data: {json.dumps(metadata, ensure_ascii=False)}\n\n"
            
            for chunk in result:
                if chunk:
                    data = {
                        "type": "chunk",
                        "content": chunk
                    }
                    yield f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
        
        return stream_wrapper()
    
    ui = RAG_SOURCES.get(source)
    return {
        "rag": True,
        "response": result if isinstance(result, str) else str(result),
        "rag_source": ui.get("id"),
        "rag_emoji": ui.get("emoji"),
    }


def _process_help_flow(user_message: str) -> Dict[str, Any]:
    """Help akışını işler"""
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
    
    return {
        "help": True,
        "response": help_message
    }


main_chain = create_main_processing_chain()

def _load_html_template(filename: str) -> str:
    """HTML template dosyasını yükler"""
    template_path = Path(__file__).parent / "Frontend" / "html" / filename
    try:
        html = template_path.read_text(encoding="utf-8")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"HTML yüklenemedi: {e}")
    try:
        version = str(int(time.time()))

        def _add_version(m):
            prefix, path, suffix = m.group(1), m.group(2), m.group(3)
            if '?' in path:
                return f"{prefix}{path}{suffix}"
            return f"{prefix}{path}?v={version}{suffix}"

        html = re.sub(r"((?:href|src)=[\"'])((?:/static/)[^\"'<>]+)([\"'])", _add_version, html, flags=re.IGNORECASE)
    except Exception:
        pass
    return html


@app.get("/", response_class=HTMLResponse)
def index() -> HTMLResponse:
    """Ana sayfa HTML'ini döndürür"""
    html = _load_html_template("index.html")
    return HTMLResponse(content=html)


@app.get("/register.html", response_class=HTMLResponse)
def register_page() -> HTMLResponse:
    """Kayıt sayfası HTML'ini döndürür"""
    html = _load_html_template("register.html")
    return HTMLResponse(content=html)


@app.get("/login.html", response_class=HTMLResponse)
def login_page() -> HTMLResponse:
    """Giriş sayfası HTML'ini döndürür"""
    html = _load_html_template("login.html")
    return HTMLResponse(content=html)


@app.post("/chat")
async def chat(
    payload: Dict[str, Any],
    authorization: str | None = Header(None, alias="Authorization"),
    stream: bool = Query(False, description="Streaming modunu etkinleştir")
):
    """Ana chat endpoint'i"""
    user_message = str(payload.get("message", "")).strip()
    
    stream_enabled = stream or payload.get("stream", False)
    
    conversation_id = payload.get("conversation_id")
    if conversation_id is not None:
        try:
            conversation_id = int(conversation_id)
        except (ValueError, TypeError):
            conversation_id = None
    
    user_id = get_current_user_id_optional(authorization)
    
    if not user_message:
        if stream_enabled:
            def error_stream():
                yield f"data: {json.dumps({'error': 'Mesaj boş olamaz'}, ensure_ascii=False)}\n\n"
            return StreamingResponse(error_stream(), media_type="text/event-stream")
        return {"error": "Mesaj boş olamaz"}
    
    if not _validate_message_length(user_message):
        error_msg = f"Mesaj çok uzun. Maksimum {MAX_MESSAGE_LENGTH} karakter olabilir."
        if stream_enabled:
            def error_stream():
                yield f"data: {json.dumps({'error': error_msg}, ensure_ascii=False)}\n\n"
            return StreamingResponse(error_stream(), media_type="text/event-stream")
        return {"error": error_msg}
    
    user_message = _sanitize_input(user_message)
    if user_message == "[Güvenlik nedeniyle mesaj filtrelendi]":
        error_msg = "Güvenlik nedeniyle mesaj filtrelendi"
        if stream_enabled:
            def error_stream():
                yield f"data: {json.dumps({'error': error_msg}, ensure_ascii=False)}\n\n"
            return StreamingResponse(error_stream(), media_type="text/event-stream")
        return {"error": error_msg}
    
    estimated_tokens = _estimate_tokens(user_message)
    user_message = _summarize_text_if_needed(user_message, estimated_tokens, token_threshold=200)
    estimated_tokens = _estimate_tokens(user_message)
    if estimated_tokens > MAX_TOKENS_PER_REQUEST:
        error_msg = f"Çok fazla token. Maksimum {MAX_TOKENS_PER_REQUEST} token olabilir."
        if stream_enabled:
            def error_stream():
                yield f"data: {json.dumps({'error': error_msg}, ensure_ascii=False)}\n\n"
            return StreamingResponse(error_stream(), media_type="text/event-stream")
        return {"error": error_msg}

    try:
        print(f"[CHAIN SYSTEM] Mesaj işleniyor (async)... Kullanıcı mesajı: {user_message[:100]}..., stream={stream_enabled}")
        result = await main_chain(user_message, user_id, stream=stream_enabled)
        
        if stream_enabled and hasattr(result, '__aiter__'):
            async def streaming_wrapper():
                full_response = ""
                try:
                    async for chunk_data in result:
                        if chunk_data:
                            yield chunk_data
                            try:
                                if chunk_data.startswith("data: "):
                                    json_str = chunk_data[6:]
                                    data = json.loads(json_str)
                                    if data.get("type") == "chunk":
                                        full_response += data.get("content", "")
                            except Exception:
                                pass
                    
                    if user_id and full_response:
                        try:
                            saved_conversation_id = save_message_to_conversation(
                                user_id=user_id,
                                conversation_id=conversation_id,
                                user_message=user_message,
                                bot_response=full_response,
                                flow_type="RAG"
                            )
                            if saved_conversation_id:
                                final_data = {
                                    "type": "done",
                                    "conversation_id": saved_conversation_id
                                }
                                yield f"data: {json.dumps(final_data, ensure_ascii=False)}\n\n"
                        except Exception as e:
                            print(f"[CHAIN SYSTEM] Conversation kayıt hatası: {e}")
                except Exception as e:
                    print(f"[CHAIN SYSTEM] Streaming hatası: {e}")
                    error_data = {
                        "type": "error",
                        "error": str(e)
                    }
                    yield f"data: {json.dumps(error_data, ensure_ascii=False)}\n\n"
            
            return StreamingResponse(streaming_wrapper(), media_type="text/event-stream")
        elif stream_enabled and hasattr(result, '__iter__') and not isinstance(result, dict):
            def streaming_wrapper():
                full_response = ""
                try:
                    for chunk_data in result:
                        if chunk_data:
                            yield chunk_data
                            try:
                                if chunk_data.startswith("data: "):
                                    json_str = chunk_data[6:]
                                    data = json.loads(json_str)
                                    if data.get("type") == "chunk":
                                        full_response += data.get("content", "")
                            except Exception:
                                pass
                    
                    if user_id and full_response:
                        try:
                            saved_conversation_id = save_message_to_conversation(
                                user_id=user_id,
                                conversation_id=conversation_id,
                                user_message=user_message,
                                bot_response=full_response,
                                flow_type="RAG"
                            )
                            if saved_conversation_id:
                                final_data = {
                                    "type": "done",
                                    "conversation_id": saved_conversation_id
                                }
                                yield f"data: {json.dumps(final_data, ensure_ascii=False)}\n\n"
                        except Exception as e:
                            print(f"[CHAIN SYSTEM] Conversation kayıt hatası: {e}")
                except Exception as e:
                    print(f"[CHAIN SYSTEM] Streaming hatası: {e}")
                    error_data = {
                        "type": "error",
                        "error": str(e)
                    }
                    yield f"data: {json.dumps(error_data, ensure_ascii=False)}\n\n"
            
            return StreamingResponse(streaming_wrapper(), media_type="text/event-stream")
        
        if isinstance(result, dict) and "error" in result:
            print(f"[CHAIN SYSTEM] Hata tespit edildi: {result['error']}")
            return {"error": result["error"]}
        
        if not isinstance(result, dict):
            print(f"[CHAIN SYSTEM] Geçersiz result tipi: {type(result)}")
            return {"error": "Geçersiz response formatı"}
            
        print(f"[CHAIN SYSTEM] Başarılı response: {result}")
        
        if user_id and "error" not in result:
            bot_response = result.get("response", "")
            flow_type = result.get("flow_type")
            saved_conversation_id = save_message_to_conversation(
                user_id=user_id,
                conversation_id=conversation_id,
                user_message=user_message,
                bot_response=bot_response,
                flow_type=flow_type
            )
            if saved_conversation_id:
                result["conversation_id"] = saved_conversation_id
        
        return result

    except HTTPException as e:
        print(f"[CHAIN SYSTEM] HTTPException: {e.detail}")
        traceback.print_exc()
        if stream_enabled:
            def error_stream():
                yield f"data: {json.dumps({'error': e.detail}, ensure_ascii=False)}\n\n"
            return StreamingResponse(error_stream(), media_type="text/event-stream")
        return {"error": e.detail}
    except Exception as e:
        print(f"[CHAIN SYSTEM] Exception: {str(e)}")
        traceback.print_exc()
        error_msg = f"Sunucu hatası: {str(e)}"
        if stream_enabled:
            def error_stream():
                yield f"data: {json.dumps({'error': error_msg}, ensure_ascii=False)}\n\n"
            return StreamingResponse(error_stream(), media_type="text/event-stream")
        return {"error": error_msg}


# Admin Report Endpoint için Pydantic model
class ReportPasswordRequest(BaseModel):
    """Admin rapor şifre isteği modeli"""
    password: str


@app.post("/admin/report")
async def admin_report(request: ReportPasswordRequest):
    """
    Admin rapor endpoint'i - sistem istatistiklerini döndürür
    .env dosyasındaki REPORT_PASSWORD ile korunur
    """
    try:
        # Şifre kontrolü - .env'den REPORT_PASSWORD oku
        report_password = os.getenv("REPORT_PASSWORD")
        if not report_password:
            raise HTTPException(
                status_code=500,
                detail="REPORT_PASSWORD .env dosyasında tanımlı değil"
            )
        
        # Şifre doğrulama
        if request.password != report_password:
            raise HTTPException(
                status_code=401,
                detail="Geçersiz şifre"
            )
        
        # Veritabanı bağlantısı
        db = next(get_db())
        try:
            # Bugünün başlangıcı (00:00:00)
            today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            
            # Bugünkü yeni kullanıcı sayısı
            new_users_today = db.query(func.count(User.id))\
                .filter(User.created_at >= today_start)\
                .scalar() or 0
            
            # Toplam kullanıcı sayısı
            total_users = db.query(func.count(User.id)).scalar() or 0
            
            # Toplam conversation sayısı
            total_conversations = db.query(func.count(Conversation.id)).scalar() or 0
            
            # Toplam mesaj sayısı
            total_messages = db.query(func.count(ChatHistory.id)).scalar() or 0
            
            # Tool istatistikleri (flow_type bazlı)
            tool_stats_query = db.query(
                ChatHistory.flow_type,
                func.count(ChatHistory.id).label('count')
            ).group_by(ChatHistory.flow_type).all()
            
            # Tool istatistiklerini dictionary'ye çevir
            tool_stats = {}
            for flow_type, count in tool_stats_query:
                tool_name = flow_type if flow_type else "UNKNOWN"
                tool_stats[tool_name] = int(count)
            
            # Ortalama sohbet uzunluğu (conversation başına ortalama mesaj sayısı)
            avg_conversation_length = 0.0
            if total_conversations > 0:
                avg_conversation_length = round(total_messages / total_conversations, 2)
            
            # Kullanıcı başına ortalama mesaj sayısı
            avg_messages_per_user = 0.0
            if total_users > 0:
                avg_messages_per_user = round(total_messages / total_users, 2)
            
            # Kullanıcı başına ortalama token uzunluğu hesapla
            # Token sayısı yaklaşık olarak karakter sayısının 1/4'ü olarak tahmin edilir
            avg_tokens_per_user = 0.0
            if total_users > 0:
                # Tüm mesajların toplam karakter sayısını hesapla
                all_messages = db.query(
                    func.length(ChatHistory.user_message) + func.length(ChatHistory.bot_response)
                ).all()
                
                total_characters = sum(length[0] for length in all_messages if length[0] is not None)
                # Token sayısı = karakter sayısı / 4
                total_tokens = total_characters / 4
                avg_tokens_per_user = round(total_tokens / total_users, 2)
            
            # Raporu oluştur
            report = {
                "date": datetime.now().isoformat(),
                "new_users_today": int(new_users_today),
                "total_users": int(total_users),
                "total_conversations": int(total_conversations),
                "total_messages": int(total_messages),
                "rag_usage_count": int(tool_stats.get("RAG", 0)),
                "animal_usage_count": int(tool_stats.get("ANIMAL", 0)),
                "emotion_usage_count": int(tool_stats.get("EMOTION", 0)),
                "stats_usage_count": int(tool_stats.get("STATS", 0)),
                "help_usage_count": int(tool_stats.get("HELP", 0)),
                "unknown_usage_count": int(tool_stats.get("UNKNOWN", 0)),
                "average_conversation_length": avg_conversation_length,
                "average_messages_per_user": avg_messages_per_user,
                "average_tokens_per_user": avg_tokens_per_user
            }
            
            return report
            
        finally:
            db.close()
            
    except HTTPException:
        # HTTPException'ı tekrar fırlat
        raise
    except Exception as e:
        print(f"[ADMIN REPORT ERROR] Rapor oluşturma hatası: {e}")
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Rapor oluşturulamadı: {str(e)}"
        )


if __name__ == "__main__":
    try:
        uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
    except Exception as e:
        print(f"[SERVER] Uvicorn başlatma hatası: {e}")