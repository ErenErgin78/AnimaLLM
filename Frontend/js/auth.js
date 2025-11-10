/**
 * Auth Sayfaları JavaScript
 * Register ve Login sayfaları için fonksiyonlar
 */

/**
 * Şifre görünürlüğünü açıp kapatır
 */
function togglePasswordVisibility(inputId) {
    const input = document.getElementById(inputId);
    if (!input) return;
    
    const toggleBtn = input.parentElement.querySelector('.password-toggle');
    if (!toggleBtn) return;
    
    const eyeIcon = toggleBtn.querySelector('.eye-icon');
    if (!eyeIcon) return;
    
    // Mevcut path elementini bul veya oluştur
    let pathElement = eyeIcon.querySelector('path');
    if (!pathElement) {
        pathElement = document.createElementNS('http://www.w3.org/2000/svg', 'path');
        eyeIcon.appendChild(pathElement);
    }
    
    if (input.type === 'password') {
        input.type = 'text';
        // Göz kapalı ikonu (çizgili)
        pathElement.setAttribute('d', 'M12 7c2.76 0 5 2.24 5 5 0 .65-.13 1.26-.36 1.83l2.92 2.92c1.51-1.26 2.7-2.89 3.43-4.75-1.73-4.39-6-7.5-11-7.5-1.4 0-2.74.25-3.98.7l2.16 2.16C10.74 7.13 11.35 7 12 7zM2 4.27l2.28 2.28.46.46C3.08 8.3 1.78 10.02 1 12c1.73 4.39 6 7.5 11 7.5 1.55 0 3.03-.3 4.38-.84l.42.42L19.73 22 21 20.73 3.27 3 2 4.27zM7.53 9.8l1.55 1.55c-.05.21-.08.43-.08.65 0 1.66 1.34 3 3 3 .22 0 .44-.03.65-.08l1.55 1.55c-.67.33-1.41.53-2.2.53-2.76 0-5-2.24-5-5 0-.79.2-1.53.53-2.2zm4.31-.78l3.15 3.15.02-.16c0-1.66-1.34-3-3-3l-.17.01z');
        toggleBtn.setAttribute('aria-label', 'Şifreyi gizle');
    } else {
        input.type = 'password';
        // Göz açık ikonu
        pathElement.setAttribute('d', 'M12 4.5C7 4.5 2.73 7.61 1 12c1.73 4.39 6 7.5 11 7.5s9.27-3.11 11-7.5c-1.73-4.39-6-7.5-11-7.5zM12 17c-2.76 0-5-2.24-5-5s2.24-5 5-5 5 2.24 5 5-2.24 5-5 5zm0-8c-1.66 0-3 1.34-3 3s1.34 3 3 3 3-1.34 3-3-1.34-3-3-3z');
        toggleBtn.setAttribute('aria-label', 'Şifreyi göster');
    }
}

/**
 * Hata mesajı gösterir
 */
function showError(elementId, message) {
    const errorElement = document.getElementById(elementId);
    if (errorElement) {
        errorElement.textContent = message;
    }
}

/**
 * Kayıt formu hata mesajlarını temizler
 */
function clearRegisterErrors() {
    const usernameError = document.getElementById('username-error');
    const nameError = document.getElementById('name-error');
    const emailError = document.getElementById('email-error');
    const passwordError = document.getElementById('password-error');
    const confirmPasswordError = document.getElementById('confirm-password-error');
    const registerError = document.getElementById('register-error');
    const registerSuccess = document.getElementById('register-success');
    
    if (usernameError) usernameError.textContent = '';
    if (nameError) nameError.textContent = '';
    if (emailError) emailError.textContent = '';
    if (passwordError) passwordError.textContent = '';
    if (confirmPasswordError) confirmPasswordError.textContent = '';
    if (registerError) registerError.textContent = '';
    if (registerSuccess) registerSuccess.textContent = '';
}

/**
 * Giriş formu hata mesajlarını temizler
 */
function clearLoginErrors() {
    const emailError = document.getElementById('email-error');
    const passwordError = document.getElementById('password-error');
    const loginError = document.getElementById('login-error');
    const loginSuccess = document.getElementById('login-success');
    
    if (emailError) emailError.textContent = '';
    if (passwordError) passwordError.textContent = '';
    if (loginError) loginError.textContent = '';
    if (loginSuccess) loginSuccess.textContent = '';
}

/**
 * Kayıt formu işleme
 */
async function handleRegister(event) {
    event.preventDefault();
    
    const username = document.getElementById('username').value.trim();
    const name = document.getElementById('name').value.trim();
    const email = document.getElementById('email').value.trim();
    const password = document.getElementById('password').value;
    const confirmPassword = document.getElementById('confirm-password').value;
    
    // Hata mesajlarını temizle
    clearRegisterErrors();
    
    // Kullanıcı adı kontrolü
    if (username.length < 3) {
        showError('username-error', 'Kullanıcı adı en az 3 karakter olmalıdır');
        return;
    }
    
    // Kullanıcı adı format kontrolü (sadece harf, rakam ve alt çizgi)
    if (!/^[a-zA-Z0-9_]+$/.test(username)) {
        showError('username-error', 'Kullanıcı adı sadece harf, rakam ve alt çizgi içerebilir');
        return;
    }
    
    // İsim kontrolü
    if (name.length < 2) {
        showError('name-error', 'İsim en az 2 karakter olmalıdır');
        return;
    }
    
    // Şifre eşleşme kontrolü
    if (password !== confirmPassword) {
        showError('confirm-password-error', 'Şifreler eşleşmiyor');
        return;
    }
    
    // Minimum şifre uzunluğu kontrolü
    if (password.length < 8) {
        showError('password-error', 'Şifre en az 8 karakter olmalıdır');
        return;
    }
    
    const registerBtn = document.getElementById('register-btn');
    if (!registerBtn) return;
    
    registerBtn.disabled = true;
    registerBtn.textContent = 'Kayıt yapılıyor...';
    
    try {
        const response = await fetch('/auth/register', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                username: username,
                name: name,
                email: email,
                password: password
            })
        });
        
        const data = await response.json();
        
        if (response.ok) {
            // Başarılı kayıt
            const successElement = document.getElementById('register-success');
            if (successElement) {
                successElement.textContent = 'Kayıt başarılı! Giriş sayfasına yönlendiriliyorsunuz...';
            }
            setTimeout(() => {
                window.location.href = '/login.html';
            }, 2000);
        } else {
            // Hata mesajı
            showError('register-error', data.detail || 'Kayıt işlemi başarısız');
        }
    } catch (error) {
        showError('register-error', 'Bağlantı hatası: ' + error.message);
    } finally {
        if (registerBtn) {
            registerBtn.disabled = false;
            registerBtn.textContent = 'Kayıt Ol';
        }
    }
}

/**
 * Giriş formu işleme
 */
async function handleLogin(event) {
    event.preventDefault();
    
    const email = document.getElementById('email').value.trim();
    const password = document.getElementById('password').value;
    
    // Hata mesajlarını temizle
    clearLoginErrors();
    
    const loginBtn = document.getElementById('login-btn');
    if (!loginBtn) return;
    
    loginBtn.disabled = true;
    loginBtn.textContent = 'Giriş yapılıyor...';
    
    try {
        const response = await fetch('/auth/login', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                email: email,
                password: password
            })
        });
        
        const data = await response.json();
        
        if (response.ok) {
            // Başarılı giriş - token'ı localStorage'a kaydet
            localStorage.setItem('access_token', data.access_token);
            localStorage.setItem('user', JSON.stringify(data.user));
            
            const successElement = document.getElementById('login-success');
            if (successElement) {
                successElement.textContent = 'Giriş başarılı! Yönlendiriliyorsunuz...';
            }
            
            // Ana sayfaya yönlendir
            setTimeout(() => {
                window.location.href = '/';
            }, 1000);
        } else {
            // Hata mesajı
            showError('login-error', data.detail || 'Giriş işlemi başarısız');
        }
    } catch (error) {
        showError('login-error', 'Bağlantı hatası: ' + error.message);
    } finally {
        if (loginBtn) {
            loginBtn.disabled = false;
            loginBtn.textContent = 'Giriş Yap';
        }
    }
}

/**
 * Login sayfası için token kontrolü
 */
function checkLoginToken() {
    const token = localStorage.getItem('access_token');
    if (token) {
        // Zaten giriş yapılmış, ana sayfaya yönlendir
        window.location.href = '/';
    }
}

// Login sayfası yüklendiğinde token kontrolü yap
if (document.getElementById('login-form')) {
    window.addEventListener('DOMContentLoaded', checkLoginToken);
}

