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
    const isDark = document.documentElement.classList.contains('dark');
    applyTheme(isDark ? 'light' : 'dark');
}

