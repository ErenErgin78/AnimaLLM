/**
 * Matrix Rain Animasyonu
 * Arka planda akan karakter animasyonu
 */

// Matrix animasyonu için gerekli değişkenler
let matrixCtx = null;
let matrixCanvas = null;
let matrixColumns = 0;
let matrixDrops = [];
let matrixFontSize = 16;
let matrixInterval = 60; // milisaniye cinsinden güncelleme aralığı
let matrixLastTs = 0;
let matrixEnabled = true; // Matrix efektinin açık/kapalı durumu

// Matrix'te görünecek karakterler
const matrixChars = '01ABCDEFGHIJKLMNOPQRSTUVWXYZあいうえおｱｲｳｴｵ+-*/<>#$%&';

/**
 * Matrix animasyonunu başlatır
 */
function setupMatrix() {
    matrixCanvas = document.getElementById('matrix-canvas');
    if (!matrixCanvas) return;
    
    matrixCtx = matrixCanvas.getContext('2d');
    resizeMatrix();
    requestAnimationFrame(drawMatrix);
}

/**
 * Canvas boyutunu ayarlar ve kolon sayısını hesaplar
 */
function resizeMatrix() {
    if (!matrixCanvas || !matrixCtx) return;
    
    matrixCanvas.width = window.innerWidth;
    matrixCanvas.height = window.innerHeight;
    
    // Font boyutunu ekran genişliğine göre ayarla
    matrixFontSize = Math.max(12, Math.floor(window.innerWidth / 90));
    matrixCtx.font = `${matrixFontSize}px monospace`;
    
    // Kolon sayısını hesapla
    matrixColumns = Math.floor(matrixCanvas.width / matrixFontSize);
    
    // Her kolon için başlangıç pozisyonu belirle
    matrixDrops = Array(matrixColumns).fill(0).map(() => 
        Math.floor(Math.random() * matrixCanvas.height / matrixFontSize)
    );
}

/**
 * Matrix animasyonunu çizer
 */
function drawMatrix(ts) {
    if (!ts) ts = performance.now();
    if (matrixLastTs === 0) matrixLastTs = ts;
    
    const delta = ts - matrixLastTs;
    if (delta < matrixInterval) {
        requestAnimationFrame(drawMatrix);
        return;
    }
    
    matrixLastTs = ts;
    if (!matrixCtx || !matrixCanvas) return;
    if (!matrixEnabled) {
        // Kapalıysa canvas'ı temizle ve beklemeye devam et
        matrixCtx.clearRect(0, 0, matrixCanvas.width, matrixCanvas.height);
        requestAnimationFrame(drawMatrix);
        return;
    }
    
    // Arka plan için hafif fade efekti
    const bgColor = getComputedStyle(document.documentElement)
        .getPropertyValue('--bg').trim() || '#000000';
    matrixCtx.fillStyle = bgColor;
    matrixCtx.globalAlpha = 0.12;
    matrixCtx.fillRect(0, 0, matrixCanvas.width, matrixCanvas.height);
    matrixCtx.globalAlpha = 1;
    
    // Karakter rengini CSS'den al
    const color = getComputedStyle(document.documentElement)
        .getPropertyValue('--matrix-color').trim() || '#00ff88';
    matrixCtx.fillStyle = color;
    
    // Her kolon için karakter çiz
    for (let i = 0; i < matrixColumns; i++) {
        const char = matrixChars.charAt(Math.floor(Math.random() * matrixChars.length));
        const x = i * matrixFontSize;
        const y = matrixDrops[i] * matrixFontSize;
        
        matrixCtx.fillText(char, x, y);
        
        // Ekranın dışına çıktıysa rastgele yeniden başlat
        if (y > matrixCanvas.height && Math.random() > 0.99) {
            matrixDrops[i] = 0;
        }
        
        matrixDrops[i]++;
    }
    
    requestAnimationFrame(drawMatrix);
}

/**
 * Matrix efektini aç/kapat
 */
function toggleMatrix() {
    try {
        matrixEnabled = !matrixEnabled;
        if (matrixCanvas) {
            // Görünümü de güncelle (performans için)
            matrixCanvas.style.display = matrixEnabled ? '' : 'none';
        }
    } catch (e) {
        // Hata olsa da sessizce devam et
    }
}

