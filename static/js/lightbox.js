/**
 * Lightbox (Görsel Gösterim)
 * Tam ekran görsel gösterimi
 */

/**
 * Lightbox'ı açar ve görseli gösterir
 * @param {string} url - Görsel URL'i
 */
function openLightbox(url) {
    const lb = document.getElementById('lightbox');
    const lbImg = document.getElementById('lightbox-img');
    const dl = document.getElementById('lightbox-download');
    
    if (!lb || !lbImg || !dl) return;
    
    lbImg.src = url;
    dl.href = url;
    const filename = url.split('/').pop() || 'image.jpg';
    dl.setAttribute('download', filename);
    lb.classList.add('open');
}

/**
 * Lightbox'ı kapatır
 */
function closeLightbox() {
    const lb = document.getElementById('lightbox');
    if (lb) lb.classList.remove('open');
}

// ESC tuşu ile lightbox'ı kapat
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') closeLightbox();
});

