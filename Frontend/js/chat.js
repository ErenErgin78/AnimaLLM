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
 * Streaming mesajı gösterir ve günceller
 * @param {string} content - Mesaj içeriği
 * @param {HTMLElement} messageDiv - Mesaj div elementi
 */
function updateStreamingMessage(content, messageDiv) {
    if (messageDiv) {
        const pre = messageDiv.querySelector('pre');
        if (pre) {
            pre.textContent = content;
        } else {
            messageDiv.innerHTML = '<pre>' + escapeHtml(content) + '</pre>';
        }
        const chatBox = document.getElementById('chat-box');
        if (chatBox) {
            chatBox.scrollTop = chatBox.scrollHeight;
        }
    }
}

/**
 * Backend'e mesaj gönderir ve yanıtı işler (streaming desteği ile)
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
        console.log('[CHAT] Mesaj gönderiliyor:', message);
        
        // Token'ı al (varsa)
        const token = localStorage.getItem('access_token');
        const headers = { 'Content-Type': 'application/json' };
        if (token) {
            headers['Authorization'] = `Bearer ${token}`;
        }
        
        // Aktif conversation ID'sini al (varsa)
        const conversationId = window.currentConversationId || null;
        
        // Streaming modunu aktif et (RAG için)
        const useStreaming = true; // Her zaman streaming kullan
        
        let resp;
        try {
            const url = `/chat?stream=${useStreaming}`;
            resp = await fetch(url, {
                method: 'POST',
                headers: headers,
                body: JSON.stringify({ 
                    message,
                    conversation_id: conversationId,
                    stream: useStreaming
                })
            });
        } catch (fetchError) {
            if (fetchError.name === 'AbortError') {
                throw new Error('İstek zaman aşımına uğradı');
            }
            throw fetchError;
        }
        
        console.log('[CHAT] Response alındı, status:', resp.status);
        
        if (!resp.ok) {
            const errorText = await resp.text();
            console.error('[CHAT] HTTP hatası:', resp.status, errorText);
            throw new Error(`HTTP ${resp.status}: ${errorText}`);
        }
        
        // Content-Type kontrolü - streaming mi normal mi?
        const contentType = resp.headers.get('content-type') || '';
        const isStreaming = contentType.includes('text/event-stream');
        
        if (isStreaming) {
            // Streaming modu
            console.log('[CHAT] Streaming modu aktif');
            await handleStreamingResponse(resp);
            return;
        }
        
        // Normal mod (streaming değil)
        const data = await resp.json();
        console.log('[CHAT] Response data:', data);
        
        // Conversation ID'sini sakla (yeni conversation oluşturulduysa veya mevcut conversation kullanıldıysa)
        if (data.conversation_id) {
            window.currentConversationId = data.conversation_id;
        }
        
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
        console.error('[CHAT] Hata oluştu:', e);
        removeLoadingMessage();
        const errorMsg = e.message || 'Bilinmeyen hata';
        addMessage('Bağlantı hatası: ' + errorMsg, false);
        setFaceFromText('😵');
        disableInput(false);
    }
}

/**
 * Streaming response'u işler
 * @param {Response} resp - Fetch response objesi
 */
async function handleStreamingResponse(resp) {
    const reader = resp.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    let streamingMessageDiv = null;
    let fullContent = '';
    let metadata = null;
    
    removeLoadingMessage();
    
    try {
        while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            
            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split('\n');
            buffer = lines.pop() || ''; // Son satır tamamlanmamış olabilir
            
            for (const line of lines) {
                if (line.startsWith('data: ')) {
                    try {
                        const jsonStr = line.slice(6); // "data: " kısmını çıkar
                        const data = JSON.parse(jsonStr);
                        
                        if (data.type === 'metadata') {
                            // Metadata alındı - RAG bilgileri
                            metadata = data;
                            console.log('[CHAT] Streaming metadata:', metadata);
                            
                            // Loading mesajını kaldır ve streaming mesajı oluştur
                            if (!streamingMessageDiv) {
                                const chatBox = document.getElementById('chat-box');
                                streamingMessageDiv = document.createElement('div');
                                streamingMessageDiv.className = 'message bot';
                                streamingMessageDiv.innerHTML = '<pre></pre>';
                                chatBox.appendChild(streamingMessageDiv);
                            }
                            
                            // RAG glow'u ayarla
                            if (metadata.rag_source && metadata.rag_emoji) {
                                setActivePdfGlow(metadata.rag_source, metadata.rag_emoji);
                            }
                        } else if (data.type === 'chunk') {
                            // Chunk alındı - içeriği ekle
                            const chunk = data.content || '';
                            fullContent += chunk;
                            
                            // Streaming mesajını güncelle
                            if (!streamingMessageDiv) {
                                const chatBox = document.getElementById('chat-box');
                                streamingMessageDiv = document.createElement('div');
                                streamingMessageDiv.className = 'message bot';
                                streamingMessageDiv.innerHTML = '<pre></pre>';
                                chatBox.appendChild(streamingMessageDiv);
                            }
                            
                            updateStreamingMessage(fullContent, streamingMessageDiv);
                        } else if (data.type === 'done') {
                            // Streaming tamamlandı
                            console.log('[CHAT] Streaming tamamlandı');
                            if (data.conversation_id) {
                                window.currentConversationId = data.conversation_id;
                            }
                            disableInput(false);
                            return;
                        } else if (data.type === 'error' || data.error) {
                            // Hata durumu
                            const errorMsg = data.error || 'Bilinmeyen hata';
                            console.error('[CHAT] Streaming hatası:', errorMsg);
                            if (streamingMessageDiv) {
                                streamingMessageDiv.remove();
                            }
                            addMessage('Hata: ' + errorMsg, false);
                            setFaceFromText('😵');
                            disableInput(false);
                            return;
                        }
                    } catch (parseError) {
                        console.error('[CHAT] JSON parse hatası:', parseError, 'Line:', line);
                    }
                }
            }
        }
        
        // Streaming tamamlandı ama done mesajı gelmediyse
        if (streamingMessageDiv && fullContent) {
            console.log('[CHAT] Streaming tamamlandı (buffer sonu)');
            disableInput(false);
        } else {
            // Hiçbir içerik gelmediyse hata göster
            if (streamingMessageDiv) {
                streamingMessageDiv.remove();
            }
            addMessage('Yanıt alınamadı', false);
            disableInput(false);
        }
    } catch (streamError) {
        console.error('[CHAT] Streaming işleme hatası:', streamError);
        if (streamingMessageDiv) {
            streamingMessageDiv.remove();
        }
        addMessage('Streaming hatası: ' + streamError.message, false);
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

