"""
RAG Servisi: Yerel PDF'leri ChromaDB ile vektörleştirir ve sorgular.

Görevler:
- PDFs/ altındaki PDF dosyalarını okuyup metne çevirir
- Metni parçalara (chunk) böler ve ChromaDB'ye ekler (kalıcı .chroma/ dizini)
- Sorgu için en iyi eşleşen parçaları döndürür (genel veya kaynak bazlı)
"""

import os
import re
import html
from pathlib import Path
from typing import List, Dict, Any, Optional

import os
# chromadb import edilmeden ÖNCE telemetriyi kapat
os.environ.setdefault("ANONYMIZED_TELEMETRY", "False")
os.environ.setdefault("CHROMA_TELEMETRY_IMPL", "noop")
os.environ.setdefault("POSTHOG_DISABLED", "true")

# posthog capture imza hatalarını önlemek için pre-import monkey patch
try:
    import posthog
    def _noop_capture(*args, **kwargs):
        return None
    try:
        if hasattr(posthog, "capture"):
            posthog.capture = _noop_capture
    except Exception:
        pass
    try:
        if hasattr(posthog, "Posthog") and hasattr(posthog.Posthog, "capture"):
            posthog.Posthog.capture = _noop_capture
    except Exception:
        pass
    try:
        if hasattr(posthog, "Client") and hasattr(posthog.Client, "capture"):
            posthog.Client.capture = _noop_capture
    except Exception:
        pass
except Exception:
    pass

import chromadb
from chromadb.utils import embedding_functions
try:
    from chromadb.config import Settings
except Exception:
    Settings = None

try:
    # PDF'den text çıkar
    from pypdf import PdfReader
except Exception:  
    try:
        from PyPDF2 import PdfReader 
    except Exception:
        PdfReader = None  

# Güvenlik sabitleri
MAX_RAG_QUERY_LENGTH = 1000
DANGEROUS_RAG_PATTERNS = [
    r'<script[^>]*>.*?</script>',
    r'javascript:',
    r'data:text/html',
    r'vbscript:',
    r'on\w+\s*=',
    r'<iframe[^>]*>',
    r'<object[^>]*>',
    r'<embed[^>]*>',
]

ROOT_DIR = Path(__file__).parent
PDFS_DIR = ROOT_DIR / "PDFs"
CHROMA_DIR = ROOT_DIR / ".chroma"
COLLECTION_NAME = "project_pdfs"


class RagService:
    """RAG servisi - PDF'lerden bilgi çekme ve vektör arama"""
    def __init__(self) -> None:
        # ChromaDB persistent client ile vektör veritabanı yönetimi
        # Memory sistemi ana sistem tarafından ConversationSummaryBufferMemory ile yönetiliyor
        self._client: Optional[chromadb.Client] = None
        self._collection = None
        self._embedder = None
        self._model_loading = False
        self._model_loaded = False

    def _sanitize_rag_query(self, query: str) -> str:
        """RAG sorgusu için güvenli input sanitization"""
        if not query:
            return ""
        
        # HTML escape
        query = html.escape(query, quote=True)
        
        # Tehlikeli pattern'leri kontrol et
        for pattern in DANGEROUS_RAG_PATTERNS:
            if re.search(pattern, query, re.IGNORECASE):
                print(f"[SECURITY] RAG sisteminde tehlikeli pattern: {pattern}")
                return "[Güvenlik nedeniyle sorgu filtrelendi]"
        
        # Fazla boşlukları temizle
        query = re.sub(r'\s+', ' ', query).strip()
        
        return query

    def _validate_rag_query_length(self, query: str) -> bool:
        """RAG sorgu uzunluk kontrolü"""
        return len(query) <= MAX_RAG_QUERY_LENGTH

    def _init_client(self) -> None:
        """ChromaDB kalıcı istemci başlatır"""
        CHROMA_DIR.mkdir(parents=True, exist_ok=True)
        # Bazı ortamlarda konsol hatalarını önlemek için telemetriyi devre dışı bırak
        os.environ.setdefault("ANONYMIZED_TELEMETRY", "False")
        try:
            if Settings is not None:
                print("[RAG] Chroma PersistentClient başlatılıyor (telemetri kapalı)...")
                self._client = chromadb.PersistentClient(
                    path=str(CHROMA_DIR),
                    settings=Settings(anonymized_telemetry=False),
                )
                return
        except Exception:
            pass
        print("[RAG] Chroma PersistentClient başlatılıyor (varsayılan ayarlar)...")
        self._client = chromadb.PersistentClient(path=str(CHROMA_DIR))

    def _init_embedder(self) -> None:
        """Embedding modelini yükler"""
        # All-MiniLM-L6-v2: hafif ve yaygın
        print("[RAG] Embedding modeli yükleniyor: all-MiniLM-L6-v2")
        self._embedder = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name="all-MiniLM-L6-v2"
        )
        self._model_loaded = True

    def preload_model_async(self) -> None:
        """Asenkron olarak modeli önceden yükle (site başlatıldığında)"""
        if self._model_loading or self._model_loaded:
            return
        
        self._model_loading = True
        print("[RAG] Asenkron model yükleme başlatılıyor...")
        
        import threading
        def load_in_background():
            try:
                self._init_embedder()
                print("[RAG] Model asenkron olarak yüklendi ✅")
            except Exception as e:
                print(f"[RAG] Model yükleme hatası: {e}")
            finally:
                self._model_loading = False
        
        thread = threading.Thread(target=load_in_background, daemon=True)
        thread.start()

    def _get_collection(self):
        """ChromaDB koleksiyonunu alır veya oluşturur"""
        if self._client is None:
            self._init_client()
        if self._embedder is None:
            if self._model_loading:
                print("[RAG] Model hala yükleniyor, bekleniyor...")
                # Model yüklenene kadar bekle (maksimum 30 saniye)
                import time
                for _ in range(30):
                    if self._embedder is not None:
                        break
                    time.sleep(1)
            if self._embedder is None:
                print("[RAG] Model yüklenmedi, şimdi yükleniyor...")
                self._init_embedder()
        assert self._client is not None
        # Koleksiyon al/oluştur
        print(f"[RAG] Koleksiyon hazırlanıyor: {COLLECTION_NAME}")
        try:
            col = self._client.get_collection(name=COLLECTION_NAME)
        except Exception:
            col = self._client.create_collection(
                name=COLLECTION_NAME,
                metadata={"hnsw:space": "cosine"},
                embedding_function=self._embedder,
            )
        # Koleksiyon var ama embedder atanmamışsa ata
        try:
            col._embedding_function = self._embedder
        except Exception:
            pass
        return col

    def _read_pdf_text(self, path: Path) -> str:
        """PDF dosyasından metin çıkarır"""
        if PdfReader is None:
            return ""
        try:
            print(f"[RAG] PDF okunuyor: {path.name}")
            reader = PdfReader(str(path))
            parts: List[str] = []
            for page in getattr(reader, "pages", []):
                try:
                    txt = page.extract_text() or ""
                except Exception:
                    txt = ""
                if txt:
                    parts.append(txt)
            text = "\n".join(parts)
            print(f"[RAG] PDF metni birleştirildi: {path.name}, uzunluk={len(text)}")
            return text
        except Exception:
            return ""

    def _chunk_text(self, text: str, chunk_size: int = 900, chunk_overlap: int = 150) -> List[str]:
        """Metni parçalara böler"""
        text = (text or "").strip()
        if not text:
            return []
        print(f"[RAG] Metin chunk'lanıyor: size={chunk_size}, overlap={chunk_overlap}, uzunluk={len(text)}")
        chunks: List[str] = []
        start = 0
        n = len(text)
        while start < n:
            end = min(n, start + chunk_size)
            chunks.append(text[start:end])
            if end == n:
                break
            start = max(end - chunk_overlap, start + 1)
        print(f"[RAG] Chunk sayısı: {len(chunks)}")
        return chunks

    def ensure_index(self) -> Dict[str, Any]:
        """Koleksiyon boşsa PDF'leri indeksle (tekrarlanabilir)"""
        col = self._get_collection()
        count = 0
        try:
            count = col.count()
        except Exception:
            count = 0
        if count > 0:
            print(f"[RAG] Mevcut indeks bulundu. Toplam vektör: {count}")
            return {"status": "ok", "indexed": count, "message": "mevcut indeks"}

        PDFS_DIR.mkdir(parents=True, exist_ok=True)
        pdf_files = [p for p in PDFS_DIR.glob("*.pdf") if p.is_file()]
        print(f"[RAG] PDF dosyaları taranıyor: {len(pdf_files)} bulundu")
        docs: List[str] = []
        ids: List[str] = []
        metas: List[Dict[str, Any]] = []
        for pdf_path in pdf_files:
            text = self._read_pdf_text(pdf_path)
            chunks = self._chunk_text(text)
            base = pdf_path.name
            for i, ch in enumerate(chunks):
                docs.append(ch)
                ids.append(f"{base}::chunk_{i}")
                metas.append({"source": base, "type": "pdf", "chunk_index": i})
        if docs:
            print(f"[RAG] Chroma'ya eklenecek belge sayısı: {len(docs)}")
            # Batch size limitini aşmamak için küçük parçalara böl
            batch_size = 1000  # ChromaDB için güvenli batch size
            total_added = 0
            for i in range(0, len(docs), batch_size):
                batch_docs = docs[i:i + batch_size]
                batch_metas = metas[i:i + batch_size]
                batch_ids = ids[i:i + batch_size]
                print(f"[RAG] Batch {i//batch_size + 1}/{(len(docs)-1)//batch_size + 1}: {len(batch_docs)} belge")
                try:
                    col.add(documents=batch_docs, metadatas=batch_metas, ids=batch_ids)
                    total_added += len(batch_docs)
                except Exception as e:
                    print(f"[RAG] Batch ekleme hatası: {e}")
                    # Daha küçük batch ile dene
                    smaller_batch = 500
                    for j in range(0, len(batch_docs), smaller_batch):
                        mini_docs = batch_docs[j:j + smaller_batch]
                        mini_metas = batch_metas[j:j + smaller_batch]
                        mini_ids = batch_ids[j:j + smaller_batch]
                        try:
                            col.add(documents=mini_docs, metadatas=mini_metas, ids=mini_ids)
                            total_added += len(mini_docs)
                            print(f"[RAG] Mini batch başarılı: {len(mini_docs)} belge")
                        except Exception as e2:
                            print(f"[RAG] Mini batch de başarısız: {e2}")
            print(f"[RAG] Toplam {total_added} belge koleksiyona eklendi.")
        else:
            print("[RAG] Eklenecek belge bulunamadı (boş metin).")
        return {"status": "ok", "indexed": len(docs), "files": [p.name for p in pdf_files]}

    def retrieve_top(self, query: str, top_k: int = 4) -> List[Dict[str, Any]]:
        """Genel arama yapar"""
        # Güvenlik kontrolleri
        if not query:
            return []
        
        # Sorgu uzunluk kontrolü
        if not self._validate_rag_query_length(query):
            print(f"[SECURITY] RAG sorgusu çok uzun: {len(query)}")
            return []
        
        # Input sanitization
        query = self._sanitize_rag_query(query)
        if query == "[Güvenlik nedeniyle sorgu filtrelendi]":
            print("[SECURITY] RAG sorgusu güvenlik nedeniyle filtrelendi")
            return []
        
        print(f"[RAG] Genel arama: top_k={top_k}, sorgu='{query[:100]}'")
        col = self._get_collection()
        self.ensure_index()
        try:
            res = col.query(query_texts=[query], n_results=max(1, top_k))
        except Exception:
            print("[RAG] Genel aramada Chroma sorgu hatası.")
            return []
        out: List[Dict[str, Any]] = []
        ids = (res.get("ids") or [[]])[0]
        docs = (res.get("documents") or [[]])[0]
        metas = (res.get("metadatas") or [[]])[0]
        dists = (res.get("distances") or [[]])[0]
        for i in range(min(len(ids), len(docs))):
            out.append({
                "id": ids[i],
                "text": docs[i],
                "metadata": metas[i] if i < len(metas) else {},
                "score": dists[i] if i < len(dists) else None,
            })
        print(f"[RAG] Genel arama tamam: {len(out)} sonuç")
        return out

    def retrieve_by_source(self, query: str, source_filename: str, top_k: int = 4) -> List[Dict[str, Any]]:
        """Belirli kaynağa göre arama yapar"""
        # Güvenlik kontrolleri
        if not query:
            return []
        
        # Sorgu uzunluk kontrolü
        if not self._validate_rag_query_length(query):
            print(f"[SECURITY] RAG sorgusu çok uzun: {len(query)}")
            return []
        
        # Input sanitization
        query = self._sanitize_rag_query(query)
        if query == "[Güvenlik nedeniyle sorgu filtrelendi]":
            print("[SECURITY] RAG sorgusu güvenlik nedeniyle filtrelendi")
            return []
        
        print(f"[RAG] Kaynak bazlı arama: source='{source_filename}', top_k={top_k}")
        col = self._get_collection()
        self.ensure_index()
        try:
            res = col.query(
                query_texts=[query],
                n_results=max(1, top_k),
                where={"source": source_filename},
            )
        except Exception:
            print("[RAG] Kaynak bazlı aramada Chroma sorgu hatası.")
            return []
        out: List[Dict[str, Any]] = []
        ids = (res.get("ids") or [[]])[0]
        docs = (res.get("documents") or [[]])[0]
        metas = (res.get("metadatas") or [[]])[0]
        dists = (res.get("distances") or [[]])[0]
        for i in range(min(len(ids), len(docs))):
            out.append({
                "id": ids[i],
                "text": docs[i],
                "metadata": metas[i] if i < len(metas) else {},
                "score": dists[i] if i < len(dists) else None,
            })
        print(f"[RAG] Kaynak bazlı arama tamam: {len(out)} sonuç")
        return out


# Singleton instance for app usage
rag_service = RagService()


