/**
 * Conversation (Sohbet Oturumu) Sistemi
 * ChatGPT tarzı conversation yönetimi
 */

let chatHistoryPanelOpen = false;
let currentConversationId = null; // Aktif conversation ID'si

/**
 * Sohbet geçmişi panelini aç/kapa
 */
function toggleChatHistory() {
    const panel = document.getElementById('chat-history-panel');
    if (!panel) return;
    
    chatHistoryPanelOpen = !chatHistoryPanelOpen;
    
    if (chatHistoryPanelOpen) {
        // Panel'i göster - hidden class'ını kaldır
        panel.classList.remove('hidden');
        loadConversations();
    } else {
        // Panel'i gizle - hidden class'ını ekle
        panel.classList.add('hidden');
    }
}

/**
 * Conversation listesini yükle
 */
async function loadConversations() {
    const content = document.getElementById('chat-history-content');
    if (!content) return;
    
    const token = localStorage.getItem('access_token');
    if (!token) {
        content.innerHTML = '<div class="chat-history-empty">Giriş yapmanız gerekiyor</div>';
        return;
    }
    
    // Token formatını kontrol et (JWT token'lar genellikle 3 bölümden oluşur: header.payload.signature)
    if (!token.includes('.')) {
        // Geçersiz token formatı
        localStorage.removeItem('access_token');
        localStorage.removeItem('user');
        content.innerHTML = '<div class="chat-history-empty">Geçersiz oturum. Lütfen tekrar giriş yapın.</div>';
        if (typeof checkUserStatus === 'function') {
            checkUserStatus();
        }
        return;
    }
    
    // Loading göster
    content.innerHTML = '<div class="chat-history-loading">Yükleniyor...</div>';
    
    try {
        const response = await fetch('/auth/conversations?limit=50&offset=0', {
            method: 'GET',
            headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json'
            }
        });
        
        if (!response.ok) {
            // 401 Unauthorized - token geçersiz veya süresi dolmuş
            if (response.status === 401) {
                // Token'ı temizle
                localStorage.removeItem('access_token');
                localStorage.removeItem('user');
                content.innerHTML = '<div class="chat-history-empty">Oturum süresi dolmuş. Lütfen tekrar giriş yapın.</div>';
                // Kullanıcı durumunu güncelle
                if (typeof checkUserStatus === 'function') {
                    checkUserStatus();
                }
                return;
            }
            throw new Error(`HTTP ${response.status}`);
        }
        
        const data = await response.json();
        
        if (!data.items || data.items.length === 0) {
            content.innerHTML = '<div class="chat-history-empty">Henüz sohbet oturumu yok</div>';
            return;
        }
        
        // Conversation listesini göster
        let html = '';
        data.items.forEach(conv => {
            const date = new Date(conv.updated_at);
            const dateStr = date.toLocaleString('tr-TR', {
                year: 'numeric',
                month: '2-digit',
                day: '2-digit',
                hour: '2-digit',
                minute: '2-digit'
            });
            
            // Aktif conversation'ı vurgula
            const activeClass = currentConversationId === conv.id ? 'active' : '';
            
            html += `
                <div class="conversation-item ${activeClass}" onclick="loadConversationMessages(${conv.id})">
                    <div class="conversation-title">${escapeHtml(conv.title)}</div>
                    <div class="conversation-date">${dateStr}</div>
                    <button class="conversation-delete" onclick="event.stopPropagation(); deleteConversation(${conv.id})">🗑️</button>
                </div>
            `;
        });
        
        content.innerHTML = html;
        
    } catch (error) {
        console.error('[HISTORY] Conversation listesi yükleme hatası:', error);
        content.innerHTML = '<div class="chat-history-empty">Conversation listesi yüklenemedi</div>';
    }
}

/**
 * Conversation'daki mesajları yükle ve chat-box'a ekle
 */
async function loadConversationMessages(conversationId) {
    const token = localStorage.getItem('access_token');
    if (!token) return;
    
    try {
        const response = await fetch(`/auth/conversations/${conversationId}/messages`, {
            method: 'GET',
            headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json'
            }
        });
        
        if (!response.ok) {
            // 401 Unauthorized - token geçersiz veya süresi dolmuş
            if (response.status === 401) {
                localStorage.removeItem('access_token');
                localStorage.removeItem('user');
                if (typeof checkUserStatus === 'function') {
                    checkUserStatus();
                }
                alert('Oturum süresi dolmuş. Lütfen tekrar giriş yapın.');
                return;
            }
            throw new Error(`HTTP ${response.status}`);
        }
        
        const data = await response.json();
        
        // Chat-box'ı temizle
        const chatBox = document.getElementById('chat-box');
        if (chatBox) {
            chatBox.innerHTML = '';
        }
        
        // Mesajları chat-box'a ekle
        if (data.messages && data.messages.length > 0) {
            data.messages.forEach(msg => {
                // Kullanıcı mesajı
                addMessage(msg.user_message, true);
                // Bot yanıtı
                addMessage(msg.bot_response, false);
            });
        }
        
        // Aktif conversation ID'sini güncelle (hem local hem global)
        currentConversationId = conversationId;
        window.currentConversationId = conversationId;
        
        // Conversation listesini yeniden yükle (aktif conversation'ı vurgulamak için)
        loadConversations();
        
        // Panel'i kapat
        toggleChatHistory();
        
    } catch (error) {
        console.error('[HISTORY] Mesajlar yükleme hatası:', error);
        alert('Mesajlar yüklenemedi');
    }
}

/**
 * Yeni sohbet başlat
 */
function startNewConversation() {
    // Chat-box'ı temizle
    const chatBox = document.getElementById('chat-box');
    if (chatBox) {
        chatBox.innerHTML = '';
    }
    
    // Aktif conversation ID'sini sıfırla (hem local hem global)
    currentConversationId = null;
    window.currentConversationId = null;
    
    // Input'a odaklan
    const input = document.getElementById('user-input');
    if (input) {
        input.focus();
    }
}

/**
 * Conversation'ı sil
 */
async function deleteConversation(conversationId) {
    if (!confirm('Bu sohbet oturumunu silmek istediğinize emin misiniz? Tüm mesajlar silinecek.')) {
        return;
    }
    
    const token = localStorage.getItem('access_token');
    if (!token) return;
    
    try {
        const response = await fetch(`/auth/conversations/${conversationId}`, {
            method: 'DELETE',
            headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json'
            }
        });
        
        if (!response.ok) {
            // 401 Unauthorized - token geçersiz veya süresi dolmuş
            if (response.status === 401) {
                localStorage.removeItem('access_token');
                localStorage.removeItem('user');
                if (typeof checkUserStatus === 'function') {
                    checkUserStatus();
                }
                alert('Oturum süresi dolmuş. Lütfen tekrar giriş yapın.');
                return;
            }
            throw new Error(`HTTP ${response.status}`);
        }
        
        // Eğer silinen conversation aktif conversation ise, yeni sohbet başlat
        if (currentConversationId === conversationId) {
            startNewConversation();
        }
        
        // Conversation listesini yeniden yükle
        loadConversations();
        
    } catch (error) {
        console.error('[HISTORY] Conversation silme hatası:', error);
        alert('Conversation silinemedi');
    }
}

/**
 * Tüm conversation'ları temizle
 */
async function clearChatHistory() {
    if (!confirm('Tüm sohbet oturumlarını silmek istediğinize emin misiniz? Bu işlem geri alınamaz.')) {
        return;
    }
    
    const token = localStorage.getItem('access_token');
    if (!token) return;
    
    try {
        // Tüm conversation'ları getir
        const listResponse = await fetch('/auth/conversations?limit=100&offset=0', {
            method: 'GET',
            headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json'
            }
        });
        
        if (!listResponse.ok) {
            // 401 Unauthorized - token geçersiz veya süresi dolmuş
            if (listResponse.status === 401) {
                localStorage.removeItem('access_token');
                localStorage.removeItem('user');
                if (typeof checkUserStatus === 'function') {
                    checkUserStatus();
                }
                alert('Oturum süresi dolmuş. Lütfen tekrar giriş yapın.');
                return;
            }
            throw new Error(`HTTP ${listResponse.status}`);
        }
        
        const listData = await listResponse.json();
        
        // Her conversation'ı sil
        for (const conv of listData.items || []) {
            const deleteResponse = await fetch(`/auth/conversations/${conv.id}`, {
                method: 'DELETE',
                headers: {
                    'Authorization': `Bearer ${token}`,
                    'Content-Type': 'application/json'
                }
            });
            
            // 401 hatası durumunda döngüyü durdur
            if (deleteResponse.status === 401) {
                localStorage.removeItem('access_token');
                localStorage.removeItem('user');
                if (typeof checkUserStatus === 'function') {
                    checkUserStatus();
                }
                alert('Oturum süresi dolmuş. Lütfen tekrar giriş yapın.');
                return;
            }
        }
        
        // Yeni sohbet başlat
        startNewConversation();
        
        // Conversation listesini yeniden yükle
        loadConversations();
        
    } catch (error) {
        console.error('[HISTORY] Tüm conversation\'ları silme hatası:', error);
        alert('Conversation\'lar temizlenemedi');
    }
}

/**
 * Kullanıcı durumunu kontrol et ve geçmiş butonunu göster/gizle
 */
function updateHistoryButtonVisibility() {
    const token = localStorage.getItem('access_token');
    const historyBtn = document.getElementById('history-toggle-btn');
    const newChatBtn = document.getElementById('new-chat-btn');
    
    if (historyBtn) {
        if (token) {
            historyBtn.style.display = 'inline-block';
        } else {
            historyBtn.style.display = 'none';
            // Panel açıksa kapat
            if (chatHistoryPanelOpen) {
                toggleChatHistory();
            }
            // Aktif conversation'ı sıfırla
            currentConversationId = null;
        }
    }
    
    if (newChatBtn) {
        if (token) {
            newChatBtn.style.display = 'inline-block';
        } else {
            newChatBtn.style.display = 'none';
        }
    }
}

// Sayfa yüklendiğinde butonu güncelle
window.addEventListener('load', () => {
    updateHistoryButtonVisibility();
});

window.addEventListener('DOMContentLoaded', () => {
    updateHistoryButtonVisibility();
});

// checkUserStatus fonksiyonunu override et (eğer tanımlıysa)
// Bu, sayfa yüklendikten sonra çalışacak
setTimeout(() => {
    if (typeof checkUserStatus === 'function') {
        const originalCheckUserStatus = checkUserStatus;
        window.checkUserStatus = function() {
            originalCheckUserStatus();
            updateHistoryButtonVisibility();
        };
    }
}, 100);
