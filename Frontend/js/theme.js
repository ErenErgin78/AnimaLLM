/**
 * Tema Sistemi
 * Dark/Light tema yönetimi
 */

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
}

/**
 * Tema değiştirir
 */
function toggleTheme() {
    const root = document.documentElement;
    const isDark = root.classList.contains('dark');
    // Tema geçişinde tüm animasyonları geçici olarak devre dışı bırak
    try {
        root.classList.add('no-anim');
        applyTheme(isDark ? 'light' : 'dark');
        // Bir sonraki frame'de no-anim sınıfını kaldır
        setTimeout(() => root.classList.remove('no-anim'), 0);
    } catch (_) {
        applyTheme(isDark ? 'light' : 'dark');
    }
}

