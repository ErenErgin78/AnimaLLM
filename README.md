# Kairu LLM Eğitimi - Kapsamlı Chatbot Projesi

Bu proje, **Kairu LLM eğitiminin tüm haftalarını** birleştiren kapsamlı bir chatbot sistemidir. Her hafta öğrenilen konular, gerçek bir projede uygulanarak pekiştirilmiştir.

- **GitHub**: [ErenErgin78/Openai-Emotion-Animals-Chatbot](https://github.com/ErenErgin78/Openai-Emotion-Animals-Chatbot)

## 🎓 Eğitim Süreci ve Proje Gelişimi

### 📚 **1. Hafta: LLM Temelleri**
- **Öğrenilen Konular**: LLM modellerine genel giriş, model türleri ve özellikleri
- **Projede Uygulama**: OpenAI API entegrasyonu ve temel LLM çağrıları
- **Kod Yapısı**: `OpenAI` istemcisi oluşturma ve sistem mesajları

### 🎯 **2. Hafta: Prompt Engineering**
- **Öğrenilen Konular**: Etkili prompt yazma teknikleri, sistem mesajları
- **Projede Uygulama**: Base prompt ayarları ve 7 farklı public API entegrasyonu
- **Kod Yapısı**: `animal_system.py` - Hayvan API'leri ve function calling
- **Özellikler**: 
  - Köpek/kedi/tilki/ördek fotoğraf ve bilgi API'leri
  - OpenAI function calling ile akıllı yönlendirme
  - Görsel efektler ve animasyonlar

### 🔧 **3. Hafta: Model Optimizasyonu ve Summarizer Entegrasyonu**
- **Öğrenilen Konular**: AutoTokenizer & AutoModel, GPT/BERT/T5 karşılaştırması, CPU/GPU performans
- **Summarizer Modeli (T5-small)**: Kullanıcı mesajları 200+ token olduğunda otomatik olarak özetleyerek AI'ya gönderilir, böylece token maliyetleri ve işlem süreleri optimize edilir
- **Projeye Etkisi**: Uzun mesajlar özetlenerek hem API maliyetleri düşürülür hem de sistem performansı artırılır. Summarizer çalıştığında konsola kısaltılmış metin yazdırılır

### 🧠 **4. Hafta: RAG Sistemleri**
- **Öğrenilen Konular**: Retrieval-Augmented Generation, vektör veritabanları, embedding
- **Projede Uygulama**: ChromaDB ile PDF tabanlı bilgi sistemi
- **Kod Yapısı**: `rag_service.py` - RAG servisi
- **Özellikler**:
  - PDF'lerden bilgi çekme (Python, Anayasa, Clean Architecture)
  - ChromaDB vektör veritabanı
  - Asenkron model yükleme
  - Akıllı kaynak belirleme

### ⚡ **5. Hafta: LangChain ve Memory Yönetimi**
- **Öğrenilen Konular**: Chain yapıları, Memory yönetimi, Tool integration, Agent'lar
- **Projede Uygulama**: LangChain entegrasyonu ve ConversationSummaryBufferMemory
- **Kod Yapısı**: Chain-based mimari ve hibrit memory sistemi
- **Özellikler**:
  - **LangChain Framework**: Tüm sistem chain yapısı ile yönetilir
  - **ConversationSummaryBufferMemory**: Uzun konuşmaları özetler, son mesajları hatırlar
  - **Akış Yönlendirme Chain'i**: LLM ile otomatik akış seçimi
  - **Modüler Chain'ler**: Her sistem ayrı chain olarak çalışır

### 🎯 **6. Hafta: Fine Tuning ve LORA**
- **Öğrenilen Konular**: PEFT/LoRA,  adapter tabanlı fine-tuning, inference optimizasyonu
- **Veri Üretimi (Gemini)**: Gemini API ile otomatik loop kurularak ≈12.5k Türkçe diyalog ve duygu örneği üretildi (sentetik dataset)
- **Model Eğitimi**: `ytu-ce-cosmos/turkish-gpt2-large` tabanlı LoRA adapter eğitildi (r=16, alpha=32, dropout=0.05)
- **Eğitim Detayları**: 5 epoch, batch size 2, gradient accumulation 16 (effective batch 32), bf16; RTX 4060 (CUDA 12.1). train_loss ≈ 2.01; ≈12.5k diyalog (train 11,240 / val 1,249)
- **Entegrasyon**: LoRA adapter, mevcut duygu sistemine entegre edildi ve frontend tek duygu/tek emoji akışına göre uyumlandı
- **Çalışma Akışı**:
  1) LoRA modelinden sadece kullanıcı mesajına göre yanıt üretilir
  2) Üretilen yanıt ve kullanıcı mesajı LLM'e (Gemini/GPT) gönderilir; LLM sadece 1 duygu döndürür
  3) Duyguya karşılık `data/mood_emojis.json` içinden rastgele bir yüz emojisi seçilir ve arayüzde gösterilir
  


---

## 🏗️ Proje Mimarisi

### 🎯 **Dört Ana Akış Sistemi**
1. **🧠 RAG Sistemi**: PDF'lerden bilgi çekme ve akıllı yanıt üretimi
2. **🐶 Hayvan Sistemi**: 7 farklı API ile hayvan fotoğraf ve bilgi servisi
3. **💭 Duygu Analizi**: 10 duygu tespiti ve iki aşamalı yanıt sistemi
4. **📊 İstatistik Sistemi**: Duygu verilerini analiz eden ayrı akış

### 🧠 **Memory Yönetimi**
- **ConversationSummaryBufferMemory**: Hibrit yaklaşım
- **Token Kontrolü**: 200 token limit ile maliyet optimizasyonu
- **Global Memory**: Tüm chain'ler aynı memory instance'ını paylaşır
- **Context Preservation**: Önceki konuşmaların bağlamı korunuyor

---

## 🚀 Özellikler

### 🧠 **RAG Sistemi**
- PDF'lerden bilgi çekme (Python, Anayasa, Clean Architecture)
- ChromaDB vektör veritabanı
- Asenkron model yükleme
- 5 cümle sınırlı yanıtlar

### 🐶 **Hayvan Sistemi**
- 7 farklı API entegrasyonu
- Gerçek hayvan fotoğrafları ve bilgileri
- OpenAI function calling
- Görsel efektler ve animasyonlar

### 💭 **Duygu Analizi (LoRA Entegre)**
- LoRA tabanlı kişiselleştirilmiş yanıt üretimi (Turkish GPT-2 Medium + LoRA)
- LLM (Gemini/GPT) ile tek duygu tespiti (JSON formatında: {"ruh_hali": "..."})
- `data/mood_emojis.json` üzerinden duyguya göre yüz emojisi seçimi
- Kalıcı veri depolama (konuşma geçmişi ve zaman damgalı duygu kayıtları)

### 📊 **İstatistik Sistemi**
- Duygu verilerini analiz eder
- Bugün/tüm zamanlar filtreleme
- Belirli duygu istatistikleri
- data/ klasöründen otomatik veri okuma

### 📝 **Summarizer Modeli (T5-small)**
- 200+ token olan uzun mesajları otomatik özetler
- Token maliyetlerini optimize eder
- API işlem sürelerini kısaltır
- Konsola özet çıktısı loglar

### 🎨 **Gelişmiş UI/UX**
- Sürüklenebilir düğümler ve halat animasyonları
- Matrix arkaplan efekti
- Lightbox resim görüntüleme
- Açık/koyu tema desteği
- Node hiyerarşisi (büyük-küçük node sistemi)

---

## 🛠️ Kurulum ve Çalıştırma

### 1. Gereksinimler
- Python 3.8+
- OpenAI API anahtarı
- 4GB+ RAM (RAG modeli için)

### 2. Kurulum
```bash
# Bağımlılıkları yükle
pip install -r requirements.txt
```

### 3. API Anahtarı
`.env` dosyasını oluşturun:
```
OPENAI_API_KEY=sk-your-api-key-here
```

### 4. PDF Dosyaları
`PDFs/` klasörüne PDF dosyalarınızı yerleştirin:
- `cat_care.pdf`
- `parrot_care.pdf` 
- `rabbit_care.pdf`

### 5. Çalıştırma
```bash
# Sunucuyu başlat
uvicorn api_web_chatbot:app --host 0.0.0.0 --port 8000 --reload
ya da
python api.web_chatbot.py
```

### 6. Kullanım
Tarayıcınızda: `http://localhost:8000/`

---

## 🎯 Kullanım Örnekleri

### RAG Sistemi
- **"Kedi yavrusu nasıl beslenir?"** → 🐱 `PDFs/cat_care.pdf`
- **"Papağan kafes bakımı nasıl olmalı?"** → 🦜 `PDFs/parrot_care.pdf`
- **"Tavşan tırnak kesimi nasıl yapılır?"** → 🐰 `PDFs/rabbit_care.pdf`

### Hayvan Sistemi
- **"köpek fotoğrafı ver"** → 🐶 Köpek fotoğrafı + düğüm parlaması
- **"kedi bilgisi ver"** → 🐱 Kedi bilgisi + halat animasyonu
- **"tilki fotoğrafı ver"** → 🦊 Tilki fotoğrafı + ışın efekti

### Duygu Sistemi
- **"bugün köpeğim öldü :("** → Üzgün emoji + container yeşil glow
- **"merhaba nasılsın?"** → Mutlu emoji + sohbet

### İstatistik Sistemi
- **"Bugün kaç kere mutlu oldum?"** → Bugünkü mutluluk sayısı
- **"En çok hangi duyguyu yaşadım?"** → Tüm zamanlar duygu özeti
- **"Üzgün duygu istatistikleri"** → Sadece üzgün duygu analizi

---

## 🔧 Teknik Detaylar

### RAG Sistemi
- **Embedding Model**: all-MiniLM-L6-v2
- **Vector Database**: ChromaDB (persistent)
- **Text Chunking**: 900 karakter, 150 overlap
- **Batch Processing**: 1000'lik parçalara bölünür

### Hayvan Sistemi
- **API'ler**: random.dog, thecatapi.com, randomfox.ca, random-d.uk
- **Fonksiyon Çağırma**: OpenAI function calling
- **Fallback**: Anahtar kelime tabanlı yönlendirme

### Duygu Sistemi
- **LoRA Eğitim**: `ytu-ce-cosmos/turkish-gpt2-large` üstünde LoRA (r=16, alpha=32, dropout=0.05). Dataset ≈12.5k sentetik diyalog (rapor: 12,489; train 11,240 / val 1,249; ort. uzunluk 99.09 karakter)
- **Eğitim Parametreleri**: 5 epoch, batch size 2, gradient accumulation 16 (effective 32), learning rate 2e-4, scheduler cosine, warmup 0.1, bf16; RTX 4060 (CUDA 12.1); train_loss ≈ 2.01
- **Model Çıktısı**: LoRA adapter `Lora/Model/main` klasöründe (adapter_config.json, adapter_model.bin)
- **Inference**: LoRA adapter, uygulama başında asenkron yüklenir; yanıt üretirken yalnızca kullanıcı mesajı kullanılır
- **Duygu Analizi**: LoRA yanıtı + kullanıcı mesajı LLM'e verilip tek duygu JSON olarak istenir
- **Emoji Eşleme**: `data/mood_emojis.json` içinden duyguya göre yüz emojisi seçilir (yüz içermeyen emojiler filtrelenir)
- **Güvenlik/Temizlik**: Prompt sızıntısı/önekler temizlenir, maksimum 1 emoji kuralı uygulanır

### İstatistik Sistemi
- **Veri Kaynağı**: data/chat_history.txt ve mood_counter.txt
- **Filtreleme**: Bugün/tüm zamanlar + isteğe bağlı duygu
- **Analiz**: Regex ile mesaj ayrıştırma
- **Bağımsız Akış**: Ayrı sistem olarak çalışır

### Frontend
- **Vanilla JS**: Framework yok
- **CSS Grid/Flexbox**: Modern layout
- **Canvas API**: Matrix efekti
- **SVG**: Halat animasyonları

---

## 🏗️ Modüler Mimari

### Dosya Yapısı
```
├── main.py                 # FastAPI ana uygulama (LangChain koordinatörü)
├── Tools/                  # Backend modülleri (modüler)
│   ├── animal_system.py    # Hayvan API sistemi
│   ├── emotion_system.py   # Duygu sistemi (LoRA + LLM)
│   ├── rag_service.py      # RAG servisi
│   └── statistic_system.py # İstatistik sistemi
├── Frontend/               # Tüm frontend varlıkları
│   ├── html/index.html     # Web sayfası (UI)
│   ├── css/                # Stil dosyaları (themes.css, base.css, nodes.css ...)
│   └── js/                 # JS modülleri (app.js, nodes.js, chat.js ...)
├── data/                   # Kalıcı veriler (proje kökü)
│   ├── mood_emojis.json    # Duygu emojileri
│   ├── chat_history.txt    # Konuşma geçmişi kayıtları
│   └── mood_counter.txt    # Zaman damgalı duygu kayıtları
└── PDFs/                   # RAG için PDF kaynakları
    ├── cat_care.pdf        # Kedi bakımı
    ├── parrot_care.pdf     # Papağan bakımı
    └── rabbit_care.pdf     # Tavşan bakımı
└── Lora/
    ├── Code/               # LoRA eğitim/güncelleme betikleri (opsiyonel)
    ├── Data/               # LoRA eğitim verileri (örn. final.json)
    └── Model/
        └── main/           # Adapter + tokenizer (adapter_model.safetensors, adapter_config.json, tokenizer.json)
```

Önemli notlar:
- LoRA: `Lora/Model/main/` altında adapter dosyaları bulunur ve `Tools/emotion_system.py` tarafından proje kökünden yüklenir.
- Static servis: `main.py` HTML'i `Frontend/html/index.html`'den, CSS/JS'yi `Frontend/` altından `/static/...` yolu ile sunar ve otomatik cache-busting uygular.

---

## 🔒 Güvenlik Önlemleri

### Input Sanitization
- **HTML Escape**: Tüm kullanıcı girdileri HTML escape edilir
- **Tehlikeli Pattern Kontrolü**: Script injection, XSS, iframe injection vb. saldırıları önler
- **Regex Filtreleme**: JavaScript, VBScript, data URL'leri ve event handler'ları engeller

### Mesaj Uzunluk Sınırları
- **Ana Sistem**: 2000 karakter maksimum
- **Duygu Sistemi**: 1000 karakter maksimum  
- **Hayvan Sistemi**: 500 karakter maksimum
- **RAG Sistemi**: 1000 karakter maksimum

---

## 🎨 UI/UX Özellikleri

### Görsel Efektler
- **Yeşil Glow**: Duygu sistemi çalıştığında container kenarı
- **Düğüm Parlaması**: Aktif hayvan fonksiyonunda
- **Işın Animasyonu**: Düğümden chat kutusuna
- **Emoji Değişimi**: Yüz alanında dinamik emoji
- **Matrix Efekti**: Arka plan animasyonu

### Node Hiyerarşisi
- **Büyük Node'ler**: RAG, API, PLAIN
- **Küçük Node'ler**: Başlangıçta kapalı; tıklayınca açılır
- **Tek Hat**: Büyük node ile chat arasında tek ip
- **Renkli Parlama**: RAG=sarı, API=mavi, PLAIN=yeşil

---