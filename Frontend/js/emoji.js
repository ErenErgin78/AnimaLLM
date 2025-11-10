/**
 * Emoji ve Yüz Gösterimi
 * Emoji çıkarma ve yüz container'ına yerleştirme
 */

/**
 * Metinden ilk emoji'yi çıkarır
 * @param {string} text - Metin
 * @returns {string|null} Emoji veya null
 */
function extractFirstEmoji(text) {
    try {
        const regex = /[\u{1F600}-\u{1F64F}\u{1F300}-\u{1F5FF}\u{1F680}-\u{1F6FF}\u{1F700}-\u{1F77F}\u{1F780}-\u{1F7FF}\u{1F800}-\u{1F8FF}\u{1F900}-\u{1F9FF}\u{1FA00}-\u{1FAFF}\u{2600}-\u{26FF}\u{2700}-\u{27BF}]/u;
        const match = text.match(regex);
        return match ? match[0] : null;
    } catch (e) {
        return null;
    }
}

/**
 * Metinden emoji çıkarıp yüz container'ına yerleştirir
 * @param {string} text - Metin
 */
function setFaceFromText(text) {
    const emoji = extractFirstEmoji(text) || '🙂';
    const node = document.getElementById('face-emoji');
    if (node) {
        node.classList.add('anim');
        setTimeout(() => {
            node.textContent = emoji;
            node.classList.remove('anim');
            fitFaceEmoji();
        }, 150);
    }
}

/**
 * Emoji boyutunu container'a sığdırır
 */
function fitFaceEmoji() {
    const container = document.querySelector('.face-container');
    const node = document.getElementById('face-emoji');
    if (!container || !node) return;
    
    const maxW = container.clientWidth - 1rem; /* 16px */
    const maxH = container.clientHeight - 1rem; /* 16px */
    let size = 6; /* 96px = 6rem */
    
    node.style.fontSize = size + 'rem';
    node.style.whiteSpace = 'nowrap';
    
    // Boyut kontrolü ve ayarlama
    for (let i = 0; i < 12; i++) {
        const w = node.scrollWidth;
        const h = node.scrollHeight;
        if (w <= maxW && h <= maxH) break;
        size = Math.max(1.5, size * 0.9); /* 24px = 1.5rem */
        node.style.fontSize = size + 'rem';
    }
}

