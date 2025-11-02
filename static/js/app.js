/**
 * Ana Uygulama Dosyası
 * Tüm modülleri başlatır ve event listener'ları ayarlar
 */

// Window resize event'leri
window.addEventListener('resize', () => {
    fitFaceEmoji();
    resizeMatrix();
    
    const svg = document.getElementById('wires');
    if (svg) {
        svg.setAttribute('width', window.innerWidth);
        svg.setAttribute('height', window.innerHeight);
    }
    recomputeRestLenAll();
    updateRopesImmediate();
});

window.addEventListener('scroll', updateRopesImmediate, { passive: true });

// Sayfa yüklendiğinde başlat
window.addEventListener('load', () => {
    // Tema yükle
    const saved = localStorage.getItem('theme') || 
        (window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
    applyTheme(saved);
    
    // Emoji boyutlandır
    fitFaceEmoji();
    
    // Matrix animasyonunu başlat
    setupMatrix();
    
    // Draggable node'ları başlat
    initDraggables();
});

