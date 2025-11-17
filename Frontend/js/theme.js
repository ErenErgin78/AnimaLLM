/**
 * Tema Sistemi
 * Dark/Light tema yönetimi
 */

/**
 * Logoyu tema değişikliğine göre günceller
 */
function updateLogoForTheme() {
    const logo = document.getElementById('main-logo');
    if (!logo) return;
    
    const root = document.documentElement;
    const isDark = root.classList.contains('dark');
    
    // Dark tema (siyah arka plan) -> Light logo
    // Light tema (beyaz arka plan) -> Dark logo
    if (isDark) {
        logo.src = '/static/img/Logo_Light.png';
    } else {
        logo.src = '/static/img/Logo_Dark.png';
    }
}

/**
 * Tema uygular
 * @param {string} theme - 'dark' veya 'light'
 */
function applyTheme(theme) {
    const root = document.documentElement;
    if (theme === 'dark') {
        root.classList.add('dark');
    } else {
        root.classList.remove('dark');
    }
    localStorage.setItem('theme', theme);
    updateLogoForTheme();
}

/**
 * Matrix canvas'ını temizler (tema değişikliği için)
 */
function clearMatrixCanvas() {
    try {
        // Matrix canvas'ını hemen temizle (yeni renklerle başlamak için)
        if (typeof matrixCanvas !== 'undefined' && matrixCanvas && typeof matrixCtx !== 'undefined' && matrixCtx) {
            matrixCtx.clearRect(0, 0, matrixCanvas.width, matrixCanvas.height);
        }
    } catch (e) {
        // Hata olsa da sessizce devam et
    }
}

/**
 * Tema değiştirir
 */
function toggleTheme() {
    const root = document.documentElement;
    const body = document.body;
    const isDark = root.classList.contains('dark');
    
    // Tema geçişinde tüm animasyonları geçici olarak devre dışı bırak
    // no-anim sınıfını önce ekle (animasyonları kapat)
    root.classList.add('no-anim');
    body.classList.add('no-anim');
    
    // Matrix canvas'ını hemen temizle (yeni renklerle başlamak için)
    clearMatrixCanvas();
    
    // Tema değişikliğini hemen yap (animasyonsuz)
    applyTheme(isDark ? 'light' : 'dark');
    
    // Matrix canvas'ını bir kez daha temizle (tema değişikliğinden sonra)
    clearMatrixCanvas();
    
    // Tema değişikliği tamamlandıktan sonra no-anim sınıfını kaldır
    // requestAnimationFrame ile bir sonraki frame'de kaldır
    requestAnimationFrame(() => {
        requestAnimationFrame(() => {
            root.classList.remove('no-anim');
            body.classList.remove('no-anim');
        });
    });
}

