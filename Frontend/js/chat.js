/**
 * Chat Sistemi
 * Mesaj gönderme, alma ve görüntüleme
 */

/**
 * Chat kutusuna mesaj ekler
 * @param {string} content - Mesaj içeriği
 * @param {boolean} isUser - Kullanıcı mesajı mı?
 */
function addMessage(content, isUser) {
    const chatBox = document.getElementById('chat-box');
    const messageDiv = document.createElement('div');
    messageDiv.className = 'message ' + (isUser ? 'user' : 'bot');
    messageDiv.innerHTML = '<pre>' + escapeHtml(content) + '</pre>';
    chatBox.appendChild(messageDiv);
    chatBox.scrollTop = chatBox.scrollHeight;
}

/**
 * Loading mesajı ekler
 * @param {string} message - Mesaj metni
 */
function addLoadingMessage(message) {
    const defaultMessage = message || 'Model düşünüyor...';
    const chatBox = document.getElementById('chat-box');
    const messageDiv = document.createElement('div');
    messageDiv.className = 'message bot loading';
    messageDiv.id = 'loading-message';
    messageDiv.textContent = defaultMessage;
    chatBox.appendChild(messageDiv);
    chatBox.scrollTop = chatBox.scrollHeight;
}

/**
 * Loading mesajını günceller
 * @param {string} message - Yeni mesaj metni
 */
function updateLoadingMessage(message) {
    const loadingMsg = document.getElementById('loading-message');
    if (loadingMsg) {
        loadingMsg.textContent = message;
    }
}

/**
 * Loading mesajını kaldırır
 */
function removeLoadingMessage() {
    const loadingMsg = document.getElementById('loading-message');
    if (loadingMsg) loadingMsg.remove();
}

/**
 * Input alanını etkin/devre dışı yapar
 * @param {boolean} disabled - Devre dışı mı?
 */
function disableInput(disabled) {
    const input = document.getElementById('user-input');
    const btn = document.getElementById('send-btn');
    if (input) input.disabled = disabled;
    if (btn) btn.disabled = disabled;
}

/**
 * RAG yanıtını işler
 * @param {object} data - Backend'den gelen veri
 */
function handleRagResponse(data) {
    const response = data.response || 'Tamam.';
    addMessage(response, false);
}

/**
 * Backend'e mesaj gönderir ve yanıtı işler
 */
async function sendMessage() {
    const input = document.getElementById('user-input');
    const message = input.value.trim();
    if (!message) return;
    
    // Kullanıcı mesajını göster
    addMessage(message, true);
    input.value = '';
    
    // Loading durumu
    addLoadingMessage();
    setFaceFromText('🤔');
    disableInput(true);
    
    try {
        // Backend'e istek gönder
        const resp = await fetch('/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message })
        });
        
        if (!resp.ok) {
            throw new Error(`HTTP ${resp.status}`);
        }
        
        const data = await resp.json();
        
        // İstatistik sayacını güncelle
        if (data.stats) {
            const reqCountEl = document.getElementById('req-count');
            if (reqCountEl) {
                reqCountEl.textContent = data.stats.requests || 0;
            }
        }
        
        // Flow type'a göre loading mesajını güncelle
        if (data.flow_type) {
            const flowMessages = {
                "RAG": "RAG çağırılıyor...",
                "ANIMAL": "Hayvan API sistemi çağırılıyor...",
                "EMOTION": "Duygu analizi yapılıyor...",
                "STATS": "İstatistikler hesaplanıyor...",
                "HELP": "Yardım hazırlanıyor..."
            };
            const flowMessage = flowMessages[data.flow_type] || 'İşleniyor...';
            updateLoadingMessage(flowMessage);
            setTimeout(() => removeLoadingMessage(), 300);
        } else {
            removeLoadingMessage();
        }
        
        // Hata kontrolü
        if (data.error) {
            addMessage('Hata: ' + data.error, false);
            disableInput(false);
            return;
        }
        
        // ANIMAL response branch
        if (data && data.animal) {
            if (data.animal_emoji) {
                const faceNode = document.getElementById('face-emoji');
                if (faceNode) {
                    faceNode.classList.add('anim');
                    setTimeout(() => {
                        faceNode.textContent = data.animal_emoji;
                        faceNode.classList.remove('anim');
                        fitFaceEmoji();
                    }, 150);
                }
            }
            
            if (data.type === 'image' && data.image_url) {
                addMessage(data.response || 'Görsel hazır.', false);
                const chatBox = document.getElementById('chat-box');
                const imgWrap = document.createElement('div');
                imgWrap.className = 'message bot';
                
                const img = document.createElement('img');
                img.src = data.image_url;
                img.alt = data.animal + ' image';
                img.style.maxWidth = '100%';
                img.style.borderRadius = '0.375rem'; /* 6px */
                img.style.cursor = 'zoom-in';
                img.addEventListener('click', () => openLightbox(data.image_url));
                
                imgWrap.appendChild(img);
                chatBox.appendChild(imgWrap);
                chatBox.scrollTop = chatBox.scrollHeight;
                
                setActiveFunctionGlow(data.animal, data.type);
                disableInput(false);
                return;
            } else {
                addMessage(data.response || 'Tamam.', false);
                setActiveFunctionGlow(data.animal, data.type);
                disableInput(false);
                return;
            }
        }
        
        // RAG (PDF) response branch
        if (data && (data.rag_source || data.rag_emoji)) {
            handleRagResponse(data);
            setActivePdfGlow(data.rag_source, data.rag_emoji);
            disableInput(false);
            return;
        }
        
        // Flow type'a göre yönlendirme
        if (data.flow_type) {
            switch (data.flow_type) {
                case "EMOTION":
                    setActivePlainGlow();
                    addMessage(data.response || '', false);
                    
                    const faceNode = document.getElementById('face-emoji');
                    if (faceNode) {
                        const emojiFromBackend = data.emoji;
                        if (emojiFromBackend && typeof emojiFromBackend === 'string' && emojiFromBackend.trim()) {
                            faceNode.classList.add('anim');
                            setTimeout(() => {
                                faceNode.textContent = emojiFromBackend.trim();
                                faceNode.classList.remove('anim');
                                fitFaceEmoji();
                            }, 150);
                        } else {
                            setFaceFromText('🙂');
                        }
                    }
                    disableInput(false);
                    return;
                
                case "STATS":
                    setActiveStatsGlow();
                    addMessage(data.response || '', false);
                    setFaceFromText(data.response || '');
                    disableInput(false);
                    return;
            }
        }
        
        // Varsayılan (PLAIN) yanıt
        setActivePlainGlow();
        addMessage(data.response || '', false);
        setFaceFromText(data.response || '');
        disableInput(false);
        
    } catch (e) {
        removeLoadingMessage();
        addMessage('Bağlantı hatası: ' + e.message, false);
        setFaceFromText('😵');
        disableInput(false);
    }
}

/**
 * Enter tuşu ile mesaj gönderme
 * @param {KeyboardEvent} event - Klavye olayı
 */
function handleKeyPress(event) {
    if (event.key === 'Enter') {
        sendMessage();
    }
}

