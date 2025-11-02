/**
 * Yardımcı Fonksiyonlar
 * HTML injection'a karşı güvenlik ve diğer yardımcı fonksiyonlar
 */

/**
 * HTML injection'a karşı güvenlik için escape yapar
 * @param {string} text - Metin
 * @returns {string} Escape edilmiş metin
 */
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

