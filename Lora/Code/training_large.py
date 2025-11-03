"""LoRA Fine-Tuning Scripti - BERT Turkish modelini final.txt veya final.json ile LoRA ile fine-tune eder"""

import sys
import json
import random
import os
import time
from pathlib import Path
from datetime import datetime
import torch
from transformers import AutoTokenizer, AutoModelForCausalLM, TrainingArguments, Trainer, DataCollatorForLanguageModeling
from peft import LoraConfig, get_peft_model, TaskType
from datasets import Dataset
import numpy as np

# Tekrarlanabilirlik için global seed değeri
DEFAULT_SEED = 42

os.environ["HF_HUB_ENABLE_HF_TRANSFER"] = "1"

def set_global_seed(seed: int = DEFAULT_SEED):
    """Tekrarlanabilirlik için tüm rastgelelik kaynaklarını kilitle.
    - Python random, NumPy ve PyTorch (CPU/GPU) seed ataması yapılır
    - CUDA/CuDNN deterministik mod etkinleştirilir (varsa)
    Not: Deterministik mod bazı operasyonları yavaşlatabilir ama tutarlılık sağlar
    """
    try:
        # Python random
        random.seed(seed)
        # NumPy
        np.random.seed(seed)
        # PyTorch CPU
        torch.manual_seed(seed)
        # PyTorch CUDA (mevcutsa tüm GPU'lar)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(seed)
            # Deterministik ve benchmark ayarları
            torch.backends.cudnn.deterministic = True
            torch.backends.cudnn.benchmark = False
    except Exception as e:
        # Seed ataması başarısız olursa süreci durdurma, ancak uyarı ver
        print(f"[SEED] Uyarı: Seed ayarlanırken hata oluştu: {e}")

# Dinamik dosya yolları - Script'in bulunduğu klasöre göre otomatik ayarlanır
SCRIPT_DIR = Path(__file__).parent.resolve()
PROJECT_ROOT = SCRIPT_DIR.parent.parent.resolve()
DATA_DIR = PROJECT_ROOT / "Lora" / "Data"
MODEL_DIR = PROJECT_ROOT / "Lora" / "Model"

# Klasörleri oluştur (yoksa)
DATA_DIR.mkdir(parents=True, exist_ok=True)
MODEL_DIR.mkdir(parents=True, exist_ok=True)

# Dosya yolları - JSON öncelikli, yoksa TXT kullanılır
TRAIN_DATA_FILE = DATA_DIR / "final.json"  # JSON formatı kullanılıyor
if not (DATA_DIR / "final.json").exists():
    TRAIN_DATA_FILE = DATA_DIR / "final.txt"  # JSON yoksa TXT'ye geri dön
OUTPUT_MODEL_DIR = MODEL_DIR / "lora-turkish-gpt2-medium"
REPORT_FILE = DATA_DIR / "training_report.txt"


def load_dataset_from_file(file_path: Path, limit: int = None) -> list:
    """
    Veri dosyasını (final.txt veya final.json) okur ve diyalog listesi döndürür.
    JSON formatı: [{"user": "...", "assistant": "..."}, ...]
    TXT formatı: Her satır "user: ... assistant: ..." formatında
    
    Args:
        file_path: Okunacak veri dosyası yolu
        limit: Eğer belirtilirse, sadece ilk N satırı alır (test modu için)
        
    Returns:
        list: Diyalog listesi (her öğe "user: ... assistant: ..." formatında)
    """
    if not file_path.exists():
        raise FileNotFoundError(f"Veri dosyası bulunamadı: {file_path}")
    
    conversations = []
    file_ext = file_path.suffix.lower()
    
    try:
        # JSON dosyası ise
        if file_ext == '.json':
            print(f"[LOAD] JSON dosyası okunuyor: {file_path}")
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # JSON array kontrolü
            if not isinstance(data, list):
                raise ValueError(f"JSON dosyası array formatında olmalı, alınan tip: {type(data)}")
            
            # Limit varsa sadece ilk N elemanı al (test modu için)
            if limit is not None and limit > 0:
                data = data[:limit]
                print(f"[LOAD] Test modu: JSON'dan sadece ilk {limit} satır alınıyor...")
            
            # Her JSON objesini "user: ... assistant: ..." formatına çevir
            for item in data:
                if isinstance(item, dict) and 'user' in item and 'assistant' in item:
                    formatted_line = f"user: {item['user']} assistant: {item['assistant']}"
                    conversations.append(formatted_line)
                else:
                    print(f"[WARNING] Geçersiz JSON objesi atlandı: {item}")
            
            print(f"[LOAD] JSON'dan {len(conversations)} diyalog okundu")
        
        # TXT dosyası ise (eski format)
        else:
            print(f"[LOAD] TXT dosyası okunuyor: {file_path}")
            total_lines = 0
            empty_lines = 0
            
            with open(file_path, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    # Limit varsa ve yeterli satır toplandıysa dur
                    if limit is not None and len(conversations) >= limit:
                        print(f"[LOAD] Test modu: TXT'den sadece ilk {limit} satır alınıyor...")
                        break
                    
                    total_lines += 1
                    line = line.strip()
                    # Boş satırları atla, dolu satırları listeye ekle
                    if line:
                        conversations.append(line)
                    else:
                        empty_lines += 1
            
            print(f"[LOAD] TXT'den {len(conversations)} diyalog okundu (Toplam satır: {total_lines}, Boş: {empty_lines})")
        
    except json.JSONDecodeError as e:
        raise Exception(f"JSON parse hatası: {e}")
    except Exception as e:
        raise Exception(f"Dosya okuma hatası: {e}")
    
    if len(conversations) == 0:
        raise ValueError(f"Dosyada geçerli diyalog bulunamadı: {file_path}")
    
    print(f"[LOAD] Toplam {len(conversations)} diyalog yüklendi")
    return conversations

def prepare_tokenized_dataset(tokenizer, conversations: list, max_length: int = 512, test_size: float = 0.05):
    """
    Konuşmaları tokenize eder ve train/validation split yapar.
    Padding='max_length' kullanarak tüm örnekleri sabit uzunlukta yapar.
    """
    def tokenize_function(examples):
        """
        Batch tokenization fonksiyonu - dinamik padding için padding'i DataCollator'a bırakıyoruz.
        DataCollator, batch içindeki en uzun örneğe göre padding yapacak (verimlilik için).
        Labels'ı DataCollator oluşturacak (DataCollatorForLanguageModeling mlm=False ile otomatik yapar).
        """
        # Sadece truncation yap, padding'i DataCollator'a bırak (dinamik padding için verimlilik artışı)
        # Labels'ı burada set etmeyelim, DataCollator otomatik oluşturacak (nesting sorununu önler)
        tokens = tokenizer(examples["text"], truncation=True, max_length=max_length)
        return tokens
    
    # Dataset oluştur ve train/validation split yap
    # Seed'i sabit 42 olarak ayarla (tekrarlanabilirlik için)
    random_seed = 42  # Sabit seed (tekrarlanabilirlik için)
    random.seed(random_seed)  # Python random modülünü seed'le
    dataset = Dataset.from_dict({"text": conversations})
    dataset = dataset.train_test_split(test_size=test_size, shuffle=True, seed=random_seed)
    train_dict, eval_dict = dataset["train"], dataset["test"]
    print(f"[DATASET] Train: {len(train_dict)}, Validation: {len(eval_dict)} ({test_size*100:.1f}%)")
    
    # Tokenization uygula - batched mode ile daha hızlı işleme
    train_tokenized = train_dict.map(tokenize_function, batched=True, remove_columns=train_dict.column_names)
    eval_tokenized = eval_dict.map(tokenize_function, batched=True, remove_columns=eval_dict.column_names)
    
    return train_tokenized, eval_tokenized

def setup_lora_model(model_name: str = "ytu-ce-cosmos/turkish-gpt2-large"):
    """
    LoRA konfigürasyonu ile model ve tokenizer hazırlar.
    Model tipine göre (BERT/GPT-2/DialoGPT) otomatik target_modules seçer.
    GPU varsa otomatik olarak GPU'ya yükler, yoksa CPU'da çalışır.
    DialoGPT conversational AI için tasarlandığından generation için idealdir.
    """
    print(f"[SETUP] Model yükleniyor: {model_name}")
    
    # Tokenizer yükleme
    try:
        tokenizer = AutoTokenizer.from_pretrained(model_name)
    except Exception as e:
        raise Exception(f"Tokenizer yüklenemedi: {model_name} - {e}")
    
    # Pad token yoksa ekle (BERT için gerekli olabilir)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token if hasattr(tokenizer, 'eos_token') and tokenizer.eos_token else tokenizer.add_special_tokens({'pad_token': '[PAD]'})
    
    # Model tipini belirle (BERT/GPT-2) ve GPU kontrolü yap
    is_bert = "bert" in model_name.lower()
    use_gpu = torch.cuda.is_available()
    
    # Model yükleme - GPU varsa float16, CPU'da float32 kullan
    try:
        model = AutoModelForCausalLM.from_pretrained(model_name, torch_dtype=torch.float16 if use_gpu else torch.float32)
        if use_gpu:
            model = model.cuda()  # GPU'ya taşı
            print(f"[SETUP] GPU: {torch.cuda.get_device_name(0)}, CUDA: {torch.version.cuda}, Memory: {torch.cuda.get_device_properties(0).total_memory / 1024**3:.2f} GB")
        else:
            print("[SETUP] CPU modunda (GPU bulunamadı - çok yavaş olacaktır)")
    except Exception as e:
        raise Exception(f"Model yüklenemedi: {e}")
    
    # LoRA konfigürasyonu - Model tipine göre target_modules seç
    # BERT için attention layer modülleri, GPT-2 için c_attn ve c_proj
    # Turkish GPT-2 Medium için optimize edilmiş parametreler
    target_modules = ["query", "key", "value", "dense"] if is_bert else ["c_attn", "c_proj"]
    lora_config = LoraConfig(task_type=TaskType.CAUSAL_LM, r=16, lora_alpha=32, lora_dropout=0.05, target_modules=target_modules, bias="none")
    
    # LoRA adapter'ı model'e ekle
    model = get_peft_model(model, lora_config)
    model.print_trainable_parameters()
    
    # Model adını kaydet (rapor için)
    if not hasattr(model, 'model_name'):
        model.model_name = model_name
    
    return model, tokenizer

def train_model(model, tokenizer, train_dataset, output_dir: Path, num_epochs: int = 3, batch_size: int = 2, gradient_accumulation_steps: int = 4, model_name: str = None, eval_dataset=None, eval_strategy: str = "epoch"):
    """
    LoRA ile model eğitimi yapar.
    Validation set varsa her epoch sonunda değerlendirme yapar ve en iyi modeli yükler.
    """
    print(f"[TRAIN] Eğitim başlıyor...")
    print(f"[TRAIN] Epoch sayısı: {num_epochs}")
    print(f"[TRAIN] Batch size: {batch_size}")
    print(f"[TRAIN] Dataset boyutu: {len(train_dataset)}")
    
    # Training arguments - RTX 4060 için bf16 kullan (fp16'dan daha iyi)
    # Learning rate LoRA için optimize edildi (2e-4 genelde LoRA için iyi çalışır)
    # Cosine scheduler ve warmup_ratio kullanılıyor
    training_args = TrainingArguments(
        output_dir=str(output_dir), 
        num_train_epochs=num_epochs, 
        per_device_train_batch_size=batch_size,
        gradient_accumulation_steps=gradient_accumulation_steps, 
        learning_rate=2e-4, 
        warmup_ratio=0.1,  # Warmup ratio kullanılıyor (warmup_steps yerine)
        logging_steps=20,  # Her 20 step'te log
        lr_scheduler_type="cosine",  # Cosine learning rate scheduler
        eval_strategy=eval_strategy, 
        save_strategy=eval_strategy,  # Her epoch sonunda kaydet
        load_best_model_at_end=(eval_dataset is not None),
        metric_for_best_model="eval_loss" if eval_dataset is not None else None, 
        greater_is_better=False if eval_dataset is not None else None,
        logging_dir=str(output_dir / "logs"), 
        report_to=None, 
        remove_unused_columns=False,
        fp16=False,  # bf16 kullanılıyor, fp16 kapatıldı
        bf16=torch.cuda.is_available(),  # RTX 4060 için bf16 True (fp16'dan daha iyi)
        dataloader_pin_memory=torch.cuda.is_available(),
        seed=DEFAULT_SEED  # Trainer içi rastgeleliği kilitle
    )
    
    # Data collator - CausalLM için mlm=False
    data_collator = DataCollatorForLanguageModeling(tokenizer=tokenizer, mlm=False, pad_to_multiple_of=None)
    trainer = Trainer(model=model, args=training_args, train_dataset=train_dataset, eval_dataset=eval_dataset, tokenizer=tokenizer, data_collator=data_collator)
    
    # Eğitim sürecini başlat
    train_start_time = datetime.now()
    print("[TRAIN] Eğitim süreci başlıyor...")
    train_result = trainer.train()
    train_end_time = datetime.now()
    train_duration = train_end_time - train_start_time
    
    # Modeli kaydet
    print(f"[TRAIN] Model kaydediliyor: {output_dir}")
    trainer.save_model(str(output_dir))
    tokenizer.save_pretrained(str(output_dir))
    print(f"[TRAIN] Eğitim tamamlandı! Süre: {train_duration}")
    
    # TrainResult objesi immutable olduğu için wrapper kullanarak custom attribute'lar ekle
    class TrainResultWrapper:
        """TrainResult'a custom attribute eklemek için wrapper (rapor için)"""
        def __init__(self, train_result, train_duration, train_start_time, train_end_time, model_name=None):
            self.train_result = train_result
            self.train_duration = train_duration
            self.train_start_time = train_start_time
            self.train_end_time = train_end_time
            self.model_name = model_name
            # TrainResult'un tüm özelliklerini proxy olarak erişilebilir yap
            for attr in dir(train_result):
                if not attr.startswith('_'):
                    try:
                        if not hasattr(self, attr):
                            setattr(self, attr, getattr(train_result, attr))
                    except:
                        pass
    
    actual_model_name = model_name if model_name else getattr(model, 'model_name', None)
    wrapped_result = TrainResultWrapper(train_result, train_duration, train_start_time, train_end_time, model_name=actual_model_name)
    
    return trainer, wrapped_result

def calculate_model_statistics(model):
    """
    Model istatistiklerini hesaplar (toplam, eğitilebilir, dondurulmuş parametreler).
    LoRA fine-tuning'de sadece adapter parametreleri eğitilir, base model dondurulmuştur.
    """
    total_params = sum(p.numel() for p in model.parameters())
    trainable_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
    frozen_params = total_params - trainable_params
    
    stats = {
        "total_parameters": total_params,
        "trainable_parameters": trainable_params,
        "frozen_parameters": frozen_params,
        "trainable_percentage": (trainable_params / total_params * 100) if total_params > 0 else 0,
    }
    
    return stats

def test_model(model, tokenizer, test_prompts: list, max_new_tokens: int = 50):
    """
    Eğitilmiş modeli test eder ve üretilen cevapları döndürür.
    Her prompt için text generation yapar ve sonuçları kaydeder.
    Kısa, doğal ve tutarlı cevaplar için optimize edilmiş parametreler kullanılır.
    """
    print("[TEST] Model test ediliyor...")
    results = []
    model.eval()  # Evaluation moduna geç
    
    for i, prompt in enumerate(test_prompts, 1):
        print(f"[TEST] Test {i}/{len(test_prompts)}: {prompt[:50]}...")
        try:
            # Prompt'u tokenize et - max_length'ı güvenli bir değerle sınırla
            # model_max_length çok büyük olabilir (ör. 10240), bu yüzden 512 ile sınırla
            model_max_len = getattr(tokenizer, 'model_max_length', 512)
            # Çok büyük değerleri sınırla (bazı modellerde 10240 gibi değerler olabilir)
            safe_max_length = min(512, model_max_len) if model_max_len < 10000 else 512
            
            encoded = tokenizer(
                prompt, 
                return_tensors="pt", 
                padding=True, 
                truncation=True, 
                max_length=safe_max_length  # Güvenli max_length kullan
            )
            input_ids = encoded.input_ids
            attention_mask = encoded.attention_mask
            
            # GPU'ya taşı (varsa)
            if torch.cuda.is_available():
                input_ids = input_ids.cuda()
                attention_mask = attention_mask.cuda()
            
            # Pad token ve EOS token ID'lerini güvenli şekilde belirle
            # None kontrolü yap ve varsayılan değerler kullan
            if tokenizer.pad_token_id is not None:
                pad_token_id = int(tokenizer.pad_token_id)
            elif tokenizer.eos_token_id is not None:
                pad_token_id = int(tokenizer.eos_token_id)
            else:
                pad_token_id = 0  # Son çare olarak 0 kullan
            
            if tokenizer.eos_token_id is not None:
                eos_token_id = int(tokenizer.eos_token_id)
            elif tokenizer.pad_token_id is not None:
                eos_token_id = int(tokenizer.pad_token_id)
            else:
                eos_token_id = pad_token_id  # Varsayılan olarak pad_token_id kullan
            
            # Text generation - iyileştirilmiş parametreler ile
            # min_length hesaplamasını düzelt (çok büyük olmasını önle)
            input_length = input_ids.shape[-1]
            min_length_value = input_length + 3  # Minimum 3 token yanıt garantisi
            # min_length'ın max_length'ı aşmamasını garantile
            max_possible_length = safe_max_length if safe_max_length < 10000 else 512
            min_length_value = min(min_length_value, max_possible_length)
            
            with torch.no_grad():
                # Tüm sayısal parametreleri int() ile sar (int too big to convert hatasını önlemek için)
                outputs = model.generate(
                    input_ids=input_ids,
                    attention_mask=attention_mask,  # Attention mask'i açıkça ver
                    max_new_tokens=int(max_new_tokens),  # int'e zorlama (numpy.int64 sorununu önler)
                    min_length=int(min_length_value),  # int'e zorlama
                    do_sample=True,  # Sampling kullan
                    repetition_penalty=float(1.2),  # Tekrarları hafifçe cezalandır
                    no_repeat_ngram_size=int(0),  # int'e zorlama
                    top_k=int(50),  # En olası 50 token arasından seçim (int'e zorlama)
                    top_p=float(0.95),  # Kümülatif olasılığı %95 olan tokenlerden seçim
                    temperature=float(0.8),  # Hafifçe yaratıcı ama tutarlı
                    pad_token_id=int(pad_token_id),  # int'e zorlama (güvenlik için)
                    eos_token_id=int(eos_token_id)  # int'e zorlama (güvenlik için)
                )
            
            # Sadece modelin ürettiği yanıtı al (prompt'u çıkar)
            response_ids = outputs[0][input_ids.shape[-1]:]
            generated_text = tokenizer.decode(outputs[0], skip_special_tokens=True)
            generated_response = tokenizer.decode(response_ids, skip_special_tokens=True)
            
            # EOS token'dan sonrasını temizle (varsa)
            if tokenizer.eos_token:
                generated_response = generated_response.split(tokenizer.eos_token)[0].strip()
            
            results.append({"prompt": prompt, "generated_text": generated_text, "response": generated_response})
        except Exception as e:
            print(f"[TEST] Hata (Test {i}): {e}")
            results.append({"prompt": prompt, "generated_text": f"[HATA: {str(e)}]", "response": f"[HATA: {str(e)}]"})
    
    return results

def create_training_report(model_stats: dict, train_result, dataset_info: dict, test_results: list, output_file: Path, batch_size: int = 4, grad_accum: int = 2, num_epochs: int = 4):
    """
    Detaylı eğitim raporu oluşturur.
    Model bilgileri, dataset istatistikleri, eğitim metrikleri ve test sonuçlarını içerir.
    """
    print(f"[REPORT] Rapor oluşturuluyor: {output_file}")
    
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            # Rapor başlığı ve tarih
            f.write("=" * 80 + "\nLoRA EĞİTİM RAPORU\n" + "=" * 80 + "\n\n")
            f.write(f"Oluşturulma Tarihi: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            
            # Model bilgileri
            actual_model_name = getattr(train_result, 'model_name', 'ytu-ce-cosmos/turkish-gpt2-medium') if hasattr(train_result, 'model_name') else 'ytu-ce-cosmos/turkish-gpt2-medium'
            f.write("=" * 80 + "\nMODEL BİLGİLERİ\n" + "=" * 80 + "\n")
            f.write(f"Base Model: {actual_model_name}\n")
            if 'bert' in str(actual_model_name).lower():
                f.write("Model Tipi: BERT Turkish (CausalLM wrapper ile generation için)\n")
                target_mods = "['query', 'key', 'value', 'dense'] (BERT)"
            elif 'turkish-gpt2' in str(actual_model_name).lower() or 'turkish' in str(actual_model_name).lower():
                f.write("Model Tipi: Turkish GPT-2 Medium (Türkçe için optimize edilmiş GPT-2)\n")
                target_mods = "['c_attn', 'c_proj'] (GPT-2)"
            elif 'dialogpt' in str(actual_model_name).lower():
                f.write("Model Tipi: DialoGPT Large (Conversational AI - GPT-2 tabanlı)\n")
                target_mods = "['c_attn', 'c_proj'] (GPT-2/DialoGPT)"
            else:
                f.write("Model Tipi: GPT-2\n")
                target_mods = "['c_attn', 'c_proj'] (GPT-2)"
            f.write("Fine-tuning Yöntemi: LoRA (Low-Rank Adaptation)\nLoRA Rank (r): 16\nLoRA Alpha: 32\nLoRA Dropout: 0.05\nLoRA Bias: none\n")
            f.write(f"Target Modules: {target_mods}\n\n")
            
            # Model istatistikleri (LoRA ile sadece adapter parametreleri eğitilir)
            f.write("=" * 80 + "\nMODEL İSTATİSTİKLERİ\n" + "=" * 80 + "\n")
            f.write(f"Toplam Parametre: {model_stats['total_parameters']:,}\nEğitilebilir Parametre: {model_stats['trainable_parameters']:,}\n")
            f.write(f"Dondurulmuş Parametre: {model_stats['frozen_parameters']:,}\nEğitilebilir Oran: {model_stats['trainable_percentage']:.2f}%\n\n")
            
            # Dataset bilgileri
            f.write("=" * 80 + "\nDATASET BİLGİLERİ\n" + "=" * 80 + "\n")
            f.write(f"Veri Dosyası: {dataset_info['file_path']}\nToplam Diyalog: {dataset_info['total_samples']:,}\n")
            f.write(f"Train Set: {dataset_info.get('train_samples', 'N/A'):,} örnek\n")
            f.write(f"Validation Set: {dataset_info.get('validation_samples', 'N/A'):,} örnek ({dataset_info.get('validation_ratio', 0)*100:.1f}%)\n")
            f.write(f"Ortalama Uzunluk: {dataset_info['avg_length']:.2f} karakter\nMin: {dataset_info['min_length']}, Max: {dataset_info['max_length']}\n\n")
            
            # Eğitim bilgileri (epoch, batch size, GPU kullanımı vb.)
            f.write("=" * 80 + "\nEĞİTİM BİLGİLERİ\n" + "=" * 80 + "\n")
            if hasattr(train_result, 'train_start_time'):
                f.write(f"Başlangıç: {train_result.train_start_time.strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"Bitiş: {train_result.train_end_time.strftime('%Y-%m-%d %H:%M:%S')}\nToplam Süre: {train_result.train_duration}\n\n")
            f.write(f"Epoch Sayısı: {num_epochs}\nBatch Size: {batch_size}\nGradient Accumulation Steps: {grad_accum}\n")
            f.write(f"Effective Batch Size: {batch_size * grad_accum}\nLearning Rate: 2e-4\n")
            f.write(f"LR Scheduler: cosine\nWarmup Ratio: 0.1\n")
            f.write(f"GPU Kullanımı: {'Evet' if torch.cuda.is_available() else 'Hayır (CPU modunda)'}\n")
            if torch.cuda.is_available():
                f.write(f"Mixed Precision: bf16 (RTX 4060 için optimize edilmiş)\n")
            if torch.cuda.is_available():
                f.write(f"GPU: {torch.cuda.get_device_name(0)}\nCUDA Version: {torch.version.cuda}\n")
                f.write(f"GPU Memory: {torch.cuda.get_device_properties(0).total_memory / 1024**3:.2f} GB\n")
            else:
                f.write("Uyarı: CPU modunda eğitim GPU'dan çok daha yavaş olacaktır!\n")
            f.write("\n")
            
            # Eğitim metrikleri (train loss, validation loss vb.)
            f.write("=" * 80 + "\nEĞİTİM METRİKLERİ\n" + "=" * 80 + "\n")
            if hasattr(train_result, 'metrics'):
                train_metrics = {k: v for k, v in train_result.metrics.items() if not k.startswith('eval_')}
                if train_metrics:
                    f.write("Train Metrikleri:\n")
                    for key, value in train_metrics.items():
                        f.write(f"  {key}: {value:.6f}\n" if isinstance(value, float) else f"  {key}: {value}\n")
                    f.write("\n")
                eval_metrics = {k: v for k, v in train_result.metrics.items() if k.startswith('eval_')}
                if eval_metrics:
                    f.write("Validation Metrikleri:\n")
                    for key, value in eval_metrics.items():
                        display_key = key.replace('eval_', '')
                        f.write(f"  {display_key}: {value:.6f}\n" if isinstance(value, float) else f"  {display_key}: {value}\n")
                    f.write("\n")
                    if 'eval_loss' in eval_metrics:
                        f.write(f"En İyi Validation Loss: {eval_metrics['eval_loss']:.6f}\n")
                        f.write("(En düşük validation loss'a sahip model otomatik olarak yüklendi)\n")
            f.write("\n")
            
            if hasattr(train_result, 'log_history'):
                f.write("=" * 80 + "\nLOSS GEÇMİŞİ (Örnekler)\n" + "=" * 80 + "\n")
                loss_entries = [log for log in train_result.log_history if 'loss' in log]
                if loss_entries:
                    for i, entry in enumerate(loss_entries[:10], 1):
                        f.write(f"Step {entry.get('step', 'N/A')}: Loss = {entry.get('loss', 'N/A'):.6f}\n")
                    if len(loss_entries) > 10:
                        f.write(f"... (toplam {len(loss_entries)} loss kaydı)\n")
                f.write("\n")
            
            f.write("=" * 80 + "\nTEST SONUÇLARI\n" + "=" * 80 + f"\nTest Örnek Sayısı: {len(test_results)}\n\n")
            for i, result in enumerate(test_results, 1):
                f.write(f"\n--- TEST {i} ---\nPrompt: {result['prompt']}\n\nTam Çıktı:\n{result['generated_text']}\n\nSadece Yanıt:\n{result['response']}\n" + "-" * 80 + "\n")
            
            model_name_for_note = train_result.model_name if hasattr(train_result, 'model_name') else 'ytu-ce-cosmos/turkish-gpt2-medium'
            f.write("\n" + "=" * 80 + "\nKAYIT BİLGİLERİ\n" + "=" * 80 + f"\nModel Klasörü: {OUTPUT_MODEL_DIR}\nRapor Dosyası: {output_file}\n\n")
            f.write("=" * 80 + "\nNOTLAR\n" + "=" * 80 + "\n")
            f.write("- Model LoRA adapter ağırlıklarını içerir\n")
            f.write(f"- Base model ({model_name_for_note}) ayrıca indirilmelidir\n")
            f.write("- Inference için base model + LoRA adapter birlikte kullanılmalıdır\n")
            f.write("- Model dosyaları: adapter_config.json, adapter_model.bin\n")
            if 'turkish-gpt2' in str(model_name_for_note).lower() or 'turkish' in str(model_name_for_note).lower():
                f.write("- Turkish GPT-2 Medium Türkçe için özel olarak eğitilmiş modeldir, generation için idealdir\n")
                f.write("- RTX 4060 için bf16 mixed precision kullanılmıştır\n")
            elif 'bert' in str(model_name_for_note).lower():
                f.write("- BERT Turkish Türkçe için optimize edilmiş, CausalLM wrapper ile generation için kullanılıyor\n")
            elif 'dialogpt' in str(model_name_for_note).lower():
                f.write("- DialoGPT Large conversational AI için tasarlanmış, generation için idealdir\n")
            else:
                f.write("- GPT-2 modeli kullanılmıştır\n")
            f.write("\n" + "=" * 80 + "\nRAPOR SONU\n" + "=" * 80 + "\n")
        
        print(f"[REPORT] Rapor başarıyla kaydedildi: {output_file}")
        
    except Exception as e:
        print(f"[REPORT] Rapor kaydetme hatası: {e}")
        raise

def main():
    """
    Ana eğitim fonksiyonu - Tüm eğitim sürecini yönetir.
    Veri yükleme, model kurulumu, eğitim, test ve rapor oluşturma adımlarını sırayla çalıştırır.
    
    Komut satırı parametreleri:
    - python training.py test true  -> Test modu (sadece 500 satır alır)
    """
    # Komut satırı parametrelerini oku
    test_mode = False
    if len(sys.argv) >= 3:
        if sys.argv[1].lower() == "test" and sys.argv[2].lower() == "true":
            test_mode = True
            print("[MODE] Test modu aktif: JSON'dan sadece 500 satır alınacak")
    
    print("=" * 80)
    print("LoRA EĞİTİM SÜRECİ BAŞLIYOR")
    if test_mode:
        print("TEST MODU AKTİF (500 satır)")
    print("=" * 80)
    print()
    
    try:
        # Tekrarlanabilirlik için global seed'i erken safhada kilitle
        # Trainer, PyTorch ve veri karıştırma süreçleri aynı seed ile çalışacak
        set_global_seed(DEFAULT_SEED)
        print("[STEP 1] Veri dosyası okunuyor...")
        # Test modu aktifse sadece 500 satır al
        limit = 500 if test_mode else None
        conversations = load_dataset_from_file(TRAIN_DATA_FILE, limit=limit)
        print(f"[STEP 1] Toplam {len(conversations)} diyalog yüklendi")
        
        # Dataset istatistikleri hesapla
        lengths = [len(conv) for conv in conversations]
        dataset_info = {"file_path": str(TRAIN_DATA_FILE), "total_samples": len(conversations), "avg_length": np.mean(lengths), "min_length": min(lengths), "max_length": max(lengths)}
        print(f"[STEP 1] Ortalama uzunluk: {dataset_info['avg_length']:.2f} karakter")
        
        # Adım 2: Model ve tokenizer kurulumu
        print("\n[STEP 2] Model ve tokenizer kurulumu...")
        model, tokenizer = setup_lora_model()
        used_model_name = getattr(model, 'model_name', 'ytu-ce-cosmos/turkish-gpt2-medium')
        # Model istatistiklerini hesapla
        model_stats = calculate_model_statistics(model)
        print(f"[STEP 2] Eğitilebilir parametre: {model_stats['trainable_parameters']:,} ({model_stats['trainable_percentage']:.2f}%)")
        
        # Adım 3: Dataset tokenization ve train/validation split
        print("\n[STEP 3] Dataset tokenization ve train/validation split...")
        train_dataset, eval_dataset = prepare_tokenized_dataset(tokenizer, conversations, max_length=512, test_size=0.1)
        print(f"[STEP 3] Train: {len(train_dataset)}, Validation: {len(eval_dataset)}")
        
        # Dataset bilgilerini güncelle
        dataset_info["train_samples"] = len(train_dataset)
        dataset_info["validation_samples"] = len(eval_dataset)
        dataset_info["validation_ratio"] = 0.1
        
        # Adım 4: Model eğitimi
        print("\n[STEP 4] Model eğitimi...")
        dataset_size = len(train_dataset)
        print(f"[STEP 4] Train: {dataset_size:,}, Validation: {len(eval_dataset):,} örnek")
        
        # GPU/CPU'ya göre batch size ayarla (Turkish GPT-2 Medium için optimize edilmiş)
        if torch.cuda.is_available():
            batch_size, grad_accum = 1, 32  # 8GB VRAM'de large model için BATCH=1 ZORUNLUDUR (effective: 32)
            print(f"[STEP 4] GPU modunda - Batch: {batch_size}, Grad accum: {grad_accum}, Effective: {batch_size * grad_accum}")
        else:
            batch_size, grad_accum = 2, 8  # CPU'da batch size 2 (effective: 16)
            print(f"[STEP 4] CPU modunda - Batch: {batch_size}, Effective: {batch_size * grad_accum}")
        
        num_epochs = 5  # Sabit 5 epoch kullanılıyor
        print(f"[STEP 4] Dataset ({dataset_size}) - {num_epochs} epoch")
        
        # Eğitimi başlat
        trainer, train_result = train_model(model=model, tokenizer=tokenizer, train_dataset=train_dataset, output_dir=OUTPUT_MODEL_DIR, num_epochs=num_epochs, batch_size=batch_size, gradient_accumulation_steps=grad_accum, model_name=used_model_name, eval_dataset=eval_dataset, eval_strategy="epoch")
        
        # Adım 5: Model test et
        print("\n[STEP 5] Model test ediliyor...")
        test_prompts = ["user: Bugün çok mutluyum! assistant:", "user: İş yerinde sorun yaşıyorum. assistant:", "user: Yeni bir hobi edindim. assistant:", "user: Çok yorgunum. assistant:", "user: Harika bir haber aldım! assistant:"]
        test_results = test_model(model, tokenizer, test_prompts, max_new_tokens=50)
        
        # Adım 6: Eğitim raporu oluştur
        print("\n[STEP 6] Eğitim raporu oluşturuluyor...")
        create_training_report(model_stats=model_stats, train_result=train_result, dataset_info=dataset_info, test_results=test_results, output_file=REPORT_FILE, batch_size=batch_size, grad_accum=grad_accum, num_epochs=num_epochs)
        
        print("\n" + "=" * 80)
        print("EĞİTİM SÜRECİ TAMAMLANDI!")
        print("=" * 80)
        print(f"Model kaydedildi: {OUTPUT_MODEL_DIR}")
        print(f"Rapor kaydedildi: {REPORT_FILE}")
        print("=" * 80)
        
    except Exception as e:
        print(f"\n[ERROR] Hata oluştu: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

