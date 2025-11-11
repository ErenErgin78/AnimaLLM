/**
 * Ana Uygulama Dosyası
 * Tüm modülleri başlatır ve event listener'ları ayarlar
 */

// Window resize event'leri
window.addEventListener('resize', () => {
    // Emoji boyutlandır (varsa)
    if (typeof fitFaceEmoji === 'function') {
        fitFaceEmoji();
    }
    
    // Matrix boyutlandır
    if (typeof resizeMatrix === 'function') {
        resizeMatrix();
    }
    
    const svg = document.getElementById('wires');
    if (svg) {
        svg.setAttribute('width', window.innerWidth);
        svg.setAttribute('height', window.innerHeight);
    }
    
    // Node pozisyonlarını sınırlar içinde tut (resize sırasında ekran dışına çıkmalarını önle)
    if (typeof constrainAllNodes === 'function') {
        constrainAllNodes();
    }
    
    // Rope sistemini güncelle (varsa)
    if (typeof recomputeRestLenAll === 'function') {
        recomputeRestLenAll();
    }
    if (typeof updateRopesImmediate === 'function') {
        updateRopesImmediate();
    }
});

// Scroll event (varsa)
if (typeof updateRopesImmediate === 'function') {
    window.addEventListener('scroll', updateRopesImmediate, { passive: true });
}

// Kullanıcı durumunu kontrol et ve butonları göster
function checkUserStatus() {
    const token = localStorage.getItem('access_token');
    const userStr = localStorage.getItem('user');
    const authButtons = document.getElementById('auth-buttons');
    const userInfo = document.getElementById('user-info');
    const userDisplay = document.getElementById('user-display');
    
    if (token && userStr) {
        try {
            const user = JSON.parse(userStr);
            // Giriş yapılmış
            if (authButtons) authButtons.style.display = 'none';
            if (userInfo) userInfo.style.display = 'flex';
            // Kullanıcı adı veya isim göster (varsa)
            if (userDisplay) {
                const displayName = user.name || user.username || user.email;
                userDisplay.textContent = displayName;
            }
        } catch (e) {
            // JSON parse hatası
            localStorage.removeItem('access_token');
            localStorage.removeItem('user');
            if (authButtons) authButtons.style.display = 'flex';
            if (userInfo) userInfo.style.display = 'none';
        }
    } else {
        // Giriş yapılmamış
        if (authButtons) authButtons.style.display = 'flex';
        if (userInfo) userInfo.style.display = 'none';
    }
}

// Çıkış yap
async function handleLogout() {
    const token = localStorage.getItem('access_token');
    
    try {
        if (token) {
            await fetch('/auth/logout', {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${token}`
                }
            });
        }
    } catch (e) {
        console.error('Logout error:', e);
    } finally {
        // Token'ı temizle
        localStorage.removeItem('access_token');
        localStorage.removeItem('user');
        // Sayfayı yenile
        window.location.reload();
    }
}

// Sayfa yüklendiğinde başlat
window.addEventListener('load', () => {
    // Tema yükle (varsa)
    if (typeof applyTheme === 'function') {
        const saved = localStorage.getItem('theme') || 
            (window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
        applyTheme(saved);
    }
    
    // Emoji boyutlandır (varsa)
    if (typeof fitFaceEmoji === 'function') {
        fitFaceEmoji();
    }
    
    // Matrix animasyonunu başlat (her zaman)
    if (typeof setupMatrix === 'function') {
        setupMatrix();
    }
    
    // Draggable node'ları başlat (varsa)
    if (typeof initDraggables === 'function') {
        initDraggables();
    }
    
    // Kullanıcı durumunu kontrol et (varsa)
    if (typeof checkUserStatus === 'function') {
        checkUserStatus();
    }
});

// Sayfa yüklendiğinde kullanıcı durumunu kontrol et
window.addEventListener('DOMContentLoaded', () => {
    // Kullanıcı durumunu kontrol et (varsa)
    if (typeof checkUserStatus === 'function') {
        checkUserStatus();
    }
    
    // Matrix'i erken başlat (canvas hazır olduğunda)
    if (typeof setupMatrix === 'function') {
        setupMatrix();
    }
});

