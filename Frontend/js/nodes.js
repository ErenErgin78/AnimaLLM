/**
 * Node Sistemi (Draggable Nodes & Wires)
 * Sürüklenebilir node'lar, wire bağlantıları ve fizik simülasyonu
 */

// Global işaretler
window.__nodesInitialized = window.__nodesInitialized || false;
window.__workspaceStateLoaded = window.__workspaceStateLoaded || false;
window.__workspaceStateLoading = window.__workspaceStateLoading || false;

// Draggable node'ların konfigürasyonu
const DRAGGABLES = [
    // Parent hub'lar
    { id: 'fn-parent-rag', side: 'left', top: 520, left: 260 },
    { id: 'fn-parent-api', side: 'right', top: 520, right: 260 },
    { id: 'fn-parent-plain', side: 'left', top: 140, left: 260, prompt: 'Yeni bir hobi edindim.' },
    { id: 'fn-parent-stats', side: 'right', top: 140, right: 260, prompt: 'bugün kaç kere mutluluk tetikledin?' },
    
    // API child node'ları (sağ tarafta)
    { id: 'fn-dog_photo', side: 'right', prompt: 'Bana bir köpek fotoğrafı ver', top: 100, right: 32 },
    { id: 'fn-dog_facts', side: 'right', prompt: 'Bana bir köpek bilgisi ver', top: 200, right: 32 },
    { id: 'fn-cat_photo', side: 'right', prompt: 'Bana bir kedi fotoğrafı ver', top: 300, right: 32 },
    { id: 'fn-cat_facts', side: 'right', prompt: 'Bana bir kedi bilgisi ver', top: 400, right: 32 },
    { id: 'fn-fox_photo', side: 'right', prompt: 'Bana bir tilki fotoğrafı ver', top: 500, right: 32 },
    { id: 'fn-duck_photo', side: 'right', prompt: 'Bana bir ördek fotoğrafı ver', top: 600, right: 32 },
    
    // RAG PDF node'ları (sol tarafta)
    { id: 'fn-pdf-python', side: 'left', prompt: 'Kedi bakımı PDF bağlamıyla: Kediler nerede barınmalı?', top: 140, left: 32 },
    { id: 'fn-pdf-anayasa', side: 'left', prompt: 'Papağan bakımı PDF bağlamıyla: Papağan yaygın hastalıkları nelerdir?', top: 200, left: 32 },
    { id: 'fn-pdf-clean', side: 'left', prompt: 'Tavşan bakımı PDF bağlamıyla: Tavşan nasıl beslenmeli?', top: 260, left: 32 },
];

// Child → Parent ilişki haritası
const GROUP_PARENT = {
    // API children → parent-api
    'dog_photo': 'parent-api',
    'dog_facts': 'parent-api',
    'cat_photo': 'parent-api',
    'cat_facts': 'parent-api',
    'fox_photo': 'parent-api',
    'duck_photo': 'parent-api',
    
    // RAG children → parent-rag
    'pdf-python': 'parent-rag',
    'pdf-anayasa': 'parent-rag',
    'pdf-clean': 'parent-rag',
};

// Grup durumları (açık/kapalı)
const GROUPS = {
    'parent-api': { open: false, children: ['dog_photo','dog_facts','cat_photo','cat_facts','fox_photo','duck_photo'] },
    'parent-rag': { open: false, children: ['pdf-python','pdf-anayasa','pdf-clean'] },
    'parent-plain': { open: false, children: [] },
    'parent-stats': { open: false, children: [] },
};

// Halat (rope) sistem parametreleri
const ROPES = {}; // key → { points:[{x,y,vx,vy}], pathEl, side, restLen }
const SEGMENTS = 12; // Halat segment sayısı (daha pürüzsüz görünüm)
const DAMPING = 0.988; // Sürtünme katsayısı
const CONSTRAINT_ITERS = 3; // Fizik simülasyon iterasyon sayısı
// Flower modu (parent kablolar gizli, child'lar geniş açıyla açılır)
window.__flowerMode = window.__flowerMode || false;

/**
 * Tüm glow efektlerini temizler
 */
function clearGlow() {
    // Node glow'larını temizle
    document.querySelectorAll('.func-node.active, .func-node.active-rag, .func-node.active-api, .func-node.active-plain, .func-node.active-stats').forEach(n => {
        n.classList.remove('active','active-rag','active-api','active-plain','active-stats');
    });
    
    // Wire glow'larını temizle
    document.querySelectorAll('.wire.glow, .wire.glow-rag, .wire.glow-api, .wire.glow-plain, .wire.glow-stats').forEach(n => {
        n.classList.remove('glow','glow-rag','glow-api','glow-plain','glow-stats');
        n.classList.remove('hidden');
    });
    
    // Container glow'larını temizle
    const container = document.querySelector('.container');
    const faceContainer = document.querySelector('.face-container');
    if (container) container.classList.remove('glow-green', 'glow-api', 'glow-rag', 'glow-plain', 'glow-stats');
    if (faceContainer) faceContainer.classList.remove('glow-api', 'glow-rag', 'glow-plain', 'glow-stats');
}

/**
 * API fonksiyonu için glow efekti (mavi)
 * @param {string} animal - Hayvan adı
 * @param {string} type - 'image' veya 'facts'
 */
function setActiveFunctionGlow(animal, type) {
    clearGlow();
    if (!animal) return;
    
    // Child node ve wire glow
    const id = `${animal}_${type === 'image' ? 'photo' : 'facts'}`;
    const node = document.getElementById('fn-' + id);
    const wire = document.getElementById('wire-' + id);
    if (node) node.classList.add('active-api');
    if (wire) wire.classList.add('glow-api');
    
    // Parent node glow
    const parent = document.getElementById('fn-parent-api');
    if (parent) parent.classList.add('active-api');
    
    // Parent wire glow
    const parentWire = document.getElementById('wire-parent-api');
    if (parentWire) {
        parentWire.classList.add('glow-api');
        if (!window.__flowerMode) {
            parentWire.style.display = '';
            parentWire.style.opacity = '1';
        }
    }
    
    // Grup açma kontrolü
    if (!GROUPS['parent-api'].open) {
        setCollapsedState('parent-api', true);
    }
    
    // Face-container glow (API için mavi)
    const faceContainer = document.querySelector('.face-container');
    if (faceContainer) faceContainer.classList.add('glow-api');
    
    updateRopesImmediate();
}

/**
 * PDF/RAG fonksiyonu için glow efekti (sarı)
 * @param {string} pdfId - PDF ID
 * @param {string} emoji - Emoji
 */
function setActivePdfGlow(pdfId, emoji) {
    clearGlow();
    if (!pdfId) return;
    
    // Child node ve wire glow
    const node = document.getElementById('fn-' + pdfId);
    const wire = document.getElementById('wire-' + pdfId);
    if (node) node.classList.add('active-rag');
    if (wire) wire.classList.add('glow-rag');
    
    // Parent node glow
    const parent = document.getElementById('fn-parent-rag');
    if (parent) parent.classList.add('active-rag');
    
    // Parent wire glow
    const parentWire = document.getElementById('wire-parent-rag');
    if (parentWire) {
        parentWire.classList.add('glow-rag');
        if (!window.__flowerMode) {
            parentWire.style.display = '';
            parentWire.style.opacity = '1';
        }
    }
    
    // Grup açma kontrolü
    if (!GROUPS['parent-rag'].open) {
        setCollapsedState('parent-rag', true);
    }
    
    // Emoji ayarlama
    if (emoji) {
        const face = document.getElementById('face-emoji');
        if (face) {
            face.classList.add('anim');
            setTimeout(() => {
                face.textContent = emoji;
                face.classList.remove('anim');
                fitFaceEmoji();
            }, 150);
        }
    }
    
    // Face-container glow (RAG için sarı)
    const faceContainer = document.querySelector('.face-container');
    if (faceContainer) faceContainer.classList.add('glow-rag');
    
    updateRopesImmediate();
}

/**
 * PLAIN fonksiyonu için glow efekti (yeşil)
 */
function setActivePlainGlow() {
    clearGlow();
    
    const parent = document.getElementById('fn-parent-plain');
    if (parent) parent.classList.add('active-plain');
    
    const parentWire = document.getElementById('wire-parent-plain');
    if (parentWire) {
        parentWire.classList.add('glow-plain');
        if (!window.__flowerMode) {
            parentWire.style.display = '';
            parentWire.style.opacity = '1';
        }
    }
    
    if (!GROUPS['parent-plain'].open) {
        setCollapsedState('parent-plain', true);
    }
    
    // Face-container glow (PLAIN için yeşil)
    const faceContainer = document.querySelector('.face-container');
    if (faceContainer) faceContainer.classList.add('glow-plain');
    
    updateRopesImmediate();
}

/**
 * STATS fonksiyonu için glow efekti (mor)
 */
function setActiveStatsGlow() {
    clearGlow();
    
    const parent = document.getElementById('fn-parent-stats');
    if (parent) parent.classList.add('active-stats');
    
    const parentWire = document.getElementById('wire-parent-stats');
    if (parentWire) {
        parentWire.classList.add('glow-stats');
        if (!window.__flowerMode) {
            parentWire.style.display = '';
            parentWire.style.opacity = '1';
        }
    }
    
    // Face-container glow (STATS için mor)
    const faceContainer = document.querySelector('.face-container');
    if (faceContainer) faceContainer.classList.add('glow-stats');
    
    if (!GROUPS['parent-stats']) {
        GROUPS['parent-stats'] = { open: false, children: [] };
    }
    if (!GROUPS['parent-stats'].open) {
        setCollapsedState('parent-stats', true);
    }
    
    updateRopesImmediate();
}

/**
 * Hızlı prompt ile input'a metin yazar
 * @param {string} text - Prompt metni
 */
function quickPrompt(text) {
    const input = document.getElementById('user-input');
    if (!input || input.disabled) return;
    input.value = text;
    input.focus();
}

/**
 * Grup açma/kapama durumunu ayarlar
 * @param {string} groupKey - Grup anahtarı
 * @param {boolean} open - Açık mı?
 */
function setCollapsedState(groupKey, open) {
    const g = GROUPS[groupKey];
    if (!g) return;
    
    g.open = !!open;
    const parentEl = document.getElementById('fn-' + groupKey);
    
    // Child node'ları aç/kapat
    g.children.forEach((childKey, idx) => {
        const el = document.getElementById('fn-' + childKey);
        const rope = document.getElementById('wire-' + childKey);
        if (!el) return;
        
        if (open) {
            el.classList.remove('collapsed');
            if (rope) rope.classList.remove('hidden');
            
            // Parent etrafında yayılım
            try {
                const pr = parentEl.getBoundingClientRect();
                const count = Math.max(1, g.children.length);
                const parentCenterX = pr.left + pr.width / 2;
                const parentCenterY = pr.top + pr.height / 2;
                
                if (window.__flowerMode) {
                    // Çiçek modu: tam dairesel yayılım
                    const angleStep = (count === 1) ? 0 : ((Math.PI * 2) / count);
                    const startAngle = -Math.PI / 2; // üstten başla
                    const angle = startAngle + idx * angleStep;
                    const radius = 130; // tüm child'lar için sabit yarıçap (eşit uzaklık)
                    const targetLeft = parentCenterX + Math.cos(angle) * radius - el.offsetWidth / 2;
                    const targetTop = parentCenterY + Math.sin(angle) * radius - el.offsetHeight / 2;
                    el.style.left = Math.max(8, Math.min(window.innerWidth - el.offsetWidth - 8, targetLeft)) + 'px';
                    el.style.right = 'auto';
                    el.style.top = Math.max(80, Math.min(window.innerHeight - el.offsetHeight - 8, targetTop)) + 'px';
                } else {
                    // Normal: tarafına göre yarım yayılım
                    const isRight = (el.dataset.side === 'right');
                    const span = 120; // daha geniş yayılım, çakışma azaltılır
                    const base = isRight ? (-span/2) : (180 + -span/2);
                    const angleStep = (count === 1) ? 0 : (span / (count - 1));
                    const angle = (base + idx * angleStep) * Math.PI / 180;
                    const radius = 160 + (idx % 2) * 16; // biraz daha uzak yarıçap
                    const targetLeft = parentCenterX + Math.cos(angle) * radius - el.offsetWidth / 2;
                    const targetTop = parentCenterY + Math.sin(angle) * radius - el.offsetHeight / 2;
                    el.style.left = Math.max(8, Math.min(window.innerWidth - el.offsetWidth - 8, targetLeft)) + 'px';
                    el.style.right = 'auto';
                    el.style.top = Math.max(80, Math.min(window.innerHeight - el.offsetHeight - 8, targetTop)) + 'px';
                }
            } catch (_) {}
        } else {
            // Parent merkezine taşı ve gizle
            try {
                const pr = parentEl.getBoundingClientRect();
                const targetLeft = pr.left + pr.width / 2 - el.offsetWidth / 2;
                const targetTop = pr.top + pr.height / 2 - el.offsetHeight / 2;
                el.style.left = targetLeft + 'px';
                el.style.right = 'auto';
                el.style.top = targetTop + 'px';
            } catch (_) {}
            el.classList.add('collapsed');
            if (rope) rope.classList.add('hidden');
        }
    });
    
    updateRopesImmediate();
}

/**
 * Draggable node'ları başlatır
 */
function initDraggables() {
    DRAGGABLES.forEach(cfg => {
        const el = document.getElementById(cfg.id);
        if (!el) return;
        
        // Pozisyon ayarlama
        if (cfg.left !== undefined) el.style.left = cfg.left + 'px';
        if (cfg.right !== undefined) el.style.right = cfg.right + 'px';
        el.style.top = cfg.top + 'px';
        el.dataset.side = cfg.side;
        
        // Prompt click handler
        if (cfg.prompt) {
            el.addEventListener('click', () => quickPrompt(cfg.prompt));
        }
        
        // Parent hub click handler (toggle grup)
        if (cfg.id === 'fn-parent-api') {
            el.addEventListener('click', () => {
                if (el.dataset.dragMoved !== 'true') {
                    setCollapsedState('parent-api', !GROUPS['parent-api'].open);
                }
            });
        }
        if (cfg.id === 'fn-parent-rag') {
            el.addEventListener('click', () => {
                if (el.dataset.dragMoved !== 'true') {
                    setCollapsedState('parent-rag', !GROUPS['parent-rag'].open);
                }
            });
        }
        if (cfg.id === 'fn-parent-plain') {
            el.addEventListener('click', () => {
                if (el.dataset.dragMoved !== 'true') {
                    setCollapsedState('parent-plain', !GROUPS['parent-plain'].open);
                }
            });
        }
        if (cfg.id === 'fn-parent-stats') {
            el.addEventListener('click', () => {
                if (el.dataset.dragMoved !== 'true') {
                    setCollapsedState('parent-stats', !GROUPS['parent-stats'].open);
                }
            });
        }
        
        makeDraggable(el);
    });
    
    // Başlangıçta tüm grupları kapat
    setCollapsedState('parent-api', false);
    setCollapsedState('parent-rag', false);
    setCollapsedState('parent-plain', false);
    setCollapsedState('parent-stats', false);
    
    // Rope'ları başlat (collapsed state'lerden sonra)
    initRopes();
    
    // Collapsed node'ların pozisyonları ayarlandıktan sonra rope'ları güncelle
    // requestAnimationFrame ile bir sonraki frame'de güncelleme yap
    requestAnimationFrame(() => {
        updateRopesImmediate();
        requestAnimationFrame(stepRopes);
    });

    window.__nodesInitialized = true;
}

/**
 * Node'u draggable yapar
 * @param {HTMLElement} node - Node elementi
 */
function makeDraggable(node) {
    let dragging = false;
    let startX = 0, startY = 0;
    let startLeft = 0, startTop = 0;
    let lastVX = 0, lastVY = 0;
    let lastTs = 0;
    let prevLeft = 0, prevTop = 0;
    let moved = false;
    let groupDrag = false; // Sağ tıkla parent'ı sürüklerken child'ları birlikte taşı
    
    node.addEventListener('pointerdown', (e) => {
        dragging = true;
        node.setPointerCapture(e.pointerId);
        startX = e.clientX;
        startY = e.clientY;
        lastVX = 0;
        lastVY = 0;
        lastTs = performance.now();
        moved = false;
        node.dataset.dragMoved = 'false';
        // Sağ tık (button===2) ve parent hub ise grup sürükleme aktif
        groupDrag = (e.button === 2) && (node.id || '').startsWith('fn-parent-');
        if (groupDrag) {
            try { document.documentElement.classList.add('group-dragging'); } catch (_) {}
        }
        
        const rect = node.getBoundingClientRect();
        startLeft = rect.left;
        startTop = rect.top;
        prevLeft = rect.left;
        prevTop = rect.top;
        
        node.classList.add('dragging');
    });
    
    node.addEventListener('pointermove', (e) => {
        if (!dragging) return;
        
        const now = performance.now();
        const dt = Math.max(0.016, (now - lastTs) / 1000);
        const dx = e.clientX - startX;
        const dy = e.clientY - startY;
        
        if (!moved && (Math.abs(dx) > 4 || Math.abs(dy) > 4)) {
            moved = true;
            node.dataset.dragMoved = 'true';
        }
        
        let newLeft = Math.max(8, Math.min(window.innerWidth - node.offsetWidth - 8, startLeft + dx));
        const newTop = Math.max(80, Math.min(window.innerHeight - node.offsetHeight - 8, startTop + dy));
        
        // Side constraint: node'u kendi tarafında tut
        try {
            const cRect = document.querySelector('.container').getBoundingClientRect();
            const gap = 12;
            if (node.dataset.side === 'left') {
                const maxLeft = cRect.left - node.offsetWidth - gap;
                newLeft = Math.min(newLeft, maxLeft);
            } else if (node.dataset.side === 'right') {
                const minLeft = cRect.right + gap;
                newLeft = Math.max(newLeft, minLeft);
            }
        } catch (_) {}
        
        const deltaLeft = newLeft - prevLeft;
        const deltaTop = newTop - prevTop;
        node.style.left = newLeft + 'px';
        node.style.right = 'auto';
        node.style.top = newTop + 'px';
        
        // Hız hesaplama
        lastVX = (newLeft - prevLeft) / dt;
        lastVY = (newTop - prevTop) / dt;
        prevLeft = newLeft;
        prevTop = newTop;
        lastTs = now;
        
        // Grup sürükleme: parent açıksa child'ları aynı delta ile taşı
        if (groupDrag && (node.id || '').startsWith('fn-parent-')) {
            try {
                const parentKey = (node.id || '').replace('fn-parent-','parent-');
                const g = GROUPS[parentKey];
                if (g && g.open) {
                    g.children.forEach(childKey => {
                        const el = document.getElementById('fn-' + childKey);
                        if (!el || el.classList.contains('collapsed')) return;
                        const cr = el.getBoundingClientRect();
                        let cl = cr.left + deltaLeft;
                        let ct = cr.top + deltaTop;
                        // Kenarlara çarpmayı önle
                        cl = Math.max(8, Math.min(window.innerWidth - el.offsetWidth - 8, cl));
                        ct = Math.max(80, Math.min(window.innerHeight - el.offsetHeight - 8, ct));
                        el.style.left = cl + 'px';
                        el.style.right = 'auto';
                        el.style.top = ct + 'px';
                    });
                }
            } catch (_) {}
        }
        
        updateRopesImmediate();
    });
    
    node.addEventListener('pointerup', () => {
        dragging = false;
        impartVelocity(node, lastVX, lastVY);
        lastVX = 0;
        lastVY = 0;
        groupDrag = false;
        try { document.documentElement.classList.remove('group-dragging'); } catch (_) {}
        node.classList.remove('dragging');
        setTimeout(() => {
            node.dataset.dragMoved = 'false';
        }, 0);
    });
    
    node.addEventListener('pointercancel', () => {
        dragging = false;
        groupDrag = false;
        try { document.documentElement.classList.remove('group-dragging'); } catch (_) {}
        node.classList.remove('dragging');
    });
    // Sağ tık menüsünü engelle (grup sürükleme için)
    node.addEventListener('contextmenu', (e) => {
        try { e.preventDefault(); } catch (_) {}
    });
}

/**
 * Halat sistemini başlatır
 */
function initRopes() {
    const svg = document.getElementById('wires');
    const container = document.querySelector('.container');
    if (!svg || !container) return;
    
    svg.setAttribute('width', window.innerWidth);
    svg.setAttribute('height', window.innerHeight);
    
    // Parent wire'ları oluştur (parent→chat)
    ['parent-api','parent-rag','parent-plain','parent-stats'].forEach(pk => {
        let pw = document.getElementById('wire-' + pk);
        if (!pw) {
            pw = document.createElementNS('http://www.w3.org/2000/svg', 'path');
            pw.setAttribute('id', 'wire-' + pk);
            pw.setAttribute('class', 'wire');
            svg.appendChild(pw);
        }
        ROPES[pk] = ROPES[pk] || {
            points: [],
            pathEl: pw,
            side: (pk === 'parent-api' || pk === 'parent-stats' ? 'right' : 'left'),
            restLen: 0
        };
    });
    
    // Child wire'ları oluştur
    DRAGGABLES.forEach(cfg => {
        const key = cfg.id.replace('fn-','');
        let path = document.getElementById('wire-' + key);
        if (!path) {
            path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
            path.setAttribute('id', 'wire-' + key);
            path.setAttribute('class', 'wire');
            svg.appendChild(path);
        }
        
        // Anchor ratio hesapla
        const nRect = document.getElementById(cfg.id).getBoundingClientRect();
        const cRect = container.getBoundingClientRect();
        const ratio = Math.min(0.95, Math.max(0.05, (nRect.top + nRect.height / 2 - cRect.top) / Math.max(1, cRect.height)));
        cfg.anchorRatio = ratio;
        
        ROPES[key] = ROPES[key] || {
            points: [],
            pathEl: path,
            side: cfg.side,
            restLen: 0
        };
    });
}

/**
 * Halat uç noktalarını hesaplar
 * @param {string} key - Halat anahtarı
 * @returns {object} {startX, startY, endX, endY}
 */
function ropeEndpoints(key) {
    const container = document.querySelector('.container');
    const node = document.getElementById('fn-' + key) || document.getElementById('fn-parent-' + key.split('parent-')[1]);
    // Container kenarına bağlan
    const cRect = container.getBoundingClientRect();
    const nRect = node.getBoundingClientRect();
    const cfg = DRAGGABLES.find(c => c.id === 'fn-' + key) || { side: 'left', anchorRatio: 0.5 };
    
    // Child node ise parent merkezine bağla
    const parentKey = GROUP_PARENT[key];
    if (parentKey) {
        const parentEl = document.getElementById('fn-' + parentKey);
        const pRect = parentEl.getBoundingClientRect();
        const parentCenterX = pRect.left + pRect.width / 2;
        const parentCenterY = pRect.top + pRect.height / 2;
        
        // Eğer node collapsed durumdaysa (görünmez), parent merkezinde say
        const isCollapsed = node.classList.contains('collapsed');
        
        return {
            // Collapsed durumdaysa parent merkezini kullan, değilse node'un merkezini kullan
            startX: isCollapsed ? parentCenterX : (nRect.left + nRect.width / 2),
            startY: isCollapsed ? parentCenterY : (nRect.top + nRect.height / 2),
            endX: parentCenterX,
            endY: parentCenterY,
        };
    }
    
    // Parent wire'lar container/chat kenarına bağlanır
    if (key === 'parent-api' || key === 'parent-rag' || key === 'parent-plain' || key === 'parent-stats') {
        // Üst/alt ayrımı sabit oranla (daha belirgin ayrım):
        // CHAT(plain) ve STATS üstte, RAG ve API altta
        const h = Math.max(1, cRect.height);
        const ratioTop = 0.40;   // üst bağlantı oranı
        const ratioBottom = 0.60; // alt bağlantı oranı
        const ratioMap = {
            'parent-plain': ratioTop,
            'parent-stats': ratioTop,
            'parent-rag': ratioBottom,
            'parent-api': ratioBottom,
        };
        const ratio = ratioMap[key] ?? 0.5;
        let anchorY = cRect.top + ratio * h;
        // Kenar tamponlarını koru
        anchorY = Math.min(Math.max(anchorY, cRect.top + 24), cRect.bottom - 24);
        const side = (key === 'parent-api' || key === 'parent-stats') ? 'right' : 'left';
        return {
            startX: nRect.left + nRect.width / 2,
            startY: nRect.top + nRect.height / 2,
            endX: (side === 'left') ? cRect.left : cRect.right,
            endY: anchorY
        };
    }
    
    // Normal child node'lar container kenarına bağlanır
    const anchorY = Math.min(Math.max(cRect.top + (cfg.anchorRatio || 0.5) * cRect.height, cRect.top + 24), cRect.bottom - 24);
    return {
        startX: nRect.left + nRect.width / 2,
        startY: nRect.top + nRect.height / 2,
        endX: (cfg.side === 'left') ? cRect.left : cRect.right,
        endY: anchorY
    };
}

/**
 * Halat noktalarını oluşturur veya günceller
 * @param {string} key - Halat anahtarı
 */
function ensurePoints(key) {
    const rope = ROPES[key];
    if (!rope) return;
    
    const ep = ropeEndpoints(key);
    
    if (rope.points.length === 0) {
        // İlk kez oluştur
        rope.points = [];
        for (let i = 0; i <= SEGMENTS; i++) {
            const t = i / SEGMENTS;
            rope.points.push({
                x: ep.startX + (ep.endX - ep.startX) * t,
                y: ep.startY + (ep.endY - ep.startY) * t,
                vx: 0,
                vy: 0
            });
        }
        const totalDist = Math.hypot(ep.endX - ep.startX, ep.endY - ep.startY);
        rope.restLen = (totalDist / SEGMENTS) * 1.02; // Biraz gevşek
    } else {
        // Uçları güncelle
        rope.points[0].x = ep.startX;
        rope.points[0].y = ep.startY;
        rope.points[SEGMENTS].x = ep.endX;
        rope.points[SEGMENTS].y = ep.endY;
    }
}

/**
 * Halat simülasyonunu çalıştırır
 * @param {number} ts - Timestamp
 */
function stepRopes(ts) {
    const container = document.querySelector('.container');
    if (!container) return;
    
    // Collapsed durumdaki child node'ları parent merkezinde tut
    for (const groupKey in GROUPS) {
        const g = GROUPS[groupKey];
        if (!g || g.open) continue; // Açık grupları atla
        
        const parentEl = document.getElementById('fn-' + groupKey);
        if (!parentEl) continue;
        
        const pRect = parentEl.getBoundingClientRect();
        const parentCenterX = pRect.left + pRect.width / 2;
        const parentCenterY = pRect.top + pRect.height / 2;
        
        g.children.forEach(childKey => {
            const childEl = document.getElementById('fn-' + childKey);
            if (!childEl || !childEl.classList.contains('collapsed')) return;
            
            // Collapsed node'u parent merkezine taşı
            const targetLeft = parentCenterX - childEl.offsetWidth / 2;
            const targetTop = parentCenterY - childEl.offsetHeight / 2;
            childEl.style.left = targetLeft + 'px';
            childEl.style.right = 'auto';
            childEl.style.top = targetTop + 'px';
        });
    }
    
    for (const key in ROPES) {
        const rope = ROPES[key];
        ensurePoints(key);
        const pts = rope.points;
        
        // Hedef segment uzunluğu
        const ep = ropeEndpoints(key);
        const targetLen = (Math.hypot(ep.endX - ep.startX, ep.endY - ep.startY) / SEGMENTS) * 1.02;
        if (!rope.restLen || rope.restLen > targetLen) {
            rope.restLen = targetLen;
        }
        
        // Sürtünme uygula
        for (let i = 1; i < pts.length - 1; i++) {
            const p = pts[i];
            p.vx *= DAMPING;
            p.vy *= DAMPING;
            p.x += p.vx;
            p.y += p.vy;
        }
        
        // Uzunluk kısıtları (Verlet benzeri)
        for (let k = 0; k < CONSTRAINT_ITERS; k++) {
            for (let i = 0; i < pts.length - 1; i++) {
                const a = pts[i];
                const b = pts[i + 1];
                let dx = b.x - a.x;
                let dy = b.y - a.y;
                let dist = Math.hypot(dx, dy) || 0.0001;
                const diff = (dist - rope.restLen) / dist;
                
                if (i === 0) {
                    b.x -= dx * diff;
                    b.y -= dy * diff;
                } else if (i + 1 === SEGMENTS) {
                    a.x += dx * diff;
                    a.y += dy * diff;
                } else {
                    a.x += dx * diff * 0.5;
                    a.y += dy * diff * 0.5;
                    b.x -= dx * diff * 0.5;
                    b.y -= dy * diff * 0.5;
                }
            }
        }
        
        // Anchor hedefi
        const anchor = pts[SEGMENTS];
        anchor.x = ep.endX;
        anchor.y = ep.endY;
        
        drawRope(key);
    }
    
    requestAnimationFrame(stepRopes);
}

/**
 * Halatı SVG path olarak çizer
 * @param {string} key - Halat anahtarı
 */
function drawRope(key) {
    const rope = ROPES[key];
    if (!rope) return;
    
    const pts = rope.points;
    if (!pts || pts.length < 2) return;
    
    // Quadratic bezier curve ile pürüzsüz yol
    let d = `M ${pts[0].x},${pts[0].y}`;
    for (let i = 1; i < pts.length; i++) {
        const p0 = pts[i - 1];
        const p1 = pts[i];
        const cx = (p0.x + p1.x) / 2;
        const cy = (p0.y + p1.y) / 2;
        d += ` Q ${cx},${cy} ${p1.x},${p1.y}`;
    }
    
    rope.pathEl.setAttribute('d', d);
}

/**
 * Halatları anında günceller (sürükleme sırasında)
 */
function updateRopesImmediate() {
    for (const key in ROPES) {
        ensurePoints(key);
        drawRope(key);
    }
}

/**
 * Sürükleme bırakıldığında halata momentum verir
 * @param {HTMLElement} node - Node elementi
 * @param {number} vx - X hızı
 * @param {number} vy - Y hızı
 */
function impartVelocity(node, vx, vy) {
    const key = (node.id || '').replace('fn-','');
    const rope = ROPES[key];
    if (!rope) return;
    
    // Sonsuz değer kontrolü
    if (!isFinite(vx) || !isFinite(vy)) {
        vx = 0;
        vy = 0;
    }
    
    // Hız sınırlama
    let speed = Math.hypot(vx, vy);
    if (speed > 1200) {
        const s = 1200 / Math.max(1e-6, speed);
        vx *= s;
        vy *= s;
    }
    
    // Momentum uygula
    const n = rope.points.length;
    for (let i = 1; i < n - 1; i++) {
        const falloff = 1 - (i / (n - 1)); // Uca yakın daha fazla
        rope.points[i].vx += vx * 0.01 * falloff;
        rope.points[i].vy += vy * 0.01 * falloff;
    }
    
    // Halat uzunluğunu biraz kısalt
    const ep = ropeEndpoints(key);
    const minLen = Math.max(8, Math.hypot(ep.endX - ep.startX, ep.endY - ep.startY) / SEGMENTS * 0.9);
    rope.restLen = Math.max(minLen, (rope.restLen || minLen) * 0.995);
}

/**
 * Tüm halat uzunluklarını yeniden hesaplar
 */
function recomputeRestLenAll() {
    for (const key in ROPES) {
        const rope = ROPES[key];
        const ep = ropeEndpoints(key);
        const target = (Math.hypot(ep.endX - ep.startX, ep.endY - ep.startY) / SEGMENTS) * 1.02;
        rope.restLen = Math.min(rope.restLen || target, target);
    }
}

/**
 * Flower modunu aç/kapatır: parent kabloları gizler, child'ları açar
 */
function toggleFlowerMode() {
    try {
        window.__flowerMode = !window.__flowerMode;
        // Parent kabloları gizle/göster
        ['parent-api','parent-rag','parent-plain','parent-stats'].forEach(pk => {
            const pw = document.getElementById('wire-' + pk);
            if (pw) pw.style.display = window.__flowerMode ? 'none' : '';
            // Flower modunda ilgili grubu aç ki child'lar çiçek gibi yayılsın
            if (window.__flowerMode) {
                if (!GROUPS[pk] || !GROUPS[pk].open) setCollapsedState(pk, true);
            }
        });
        // Halatları anında güncelle
        updateRopesImmediate();
    } catch (e) {
        // Sessiz hata yakalama
    }
}

/**
 * Tüm node'lerin pozisyonlarını ekran sınırları içinde tutar
 * Resize event'inde çağrılır
 */
function constrainAllNodes() {
    try {
        // Tüm node'ları al
        const allNodes = document.querySelectorAll('.func-node');
        const container = document.querySelector('.container');
        
        if (!container) return;
        
        const cRect = container.getBoundingClientRect();
        const minGap = 8; // Minimum kenar boşluğu
        const topOffset = 80; // Üst boşluk (action button'lar için)
        const sideGap = 12; // Container yanındaki boşluk
        
        allNodes.forEach(node => {
            // Eğer node collapsed durumdaysa atla (parent merkezinde)
            if (node.classList.contains('collapsed')) return;
            
            const rect = node.getBoundingClientRect();
            const side = node.dataset.side || 'left';
            
            // Mevcut pozisyonu al
            let currentLeft = rect.left;
            let currentTop = rect.top;
            
            // Yatay sınır kontrolü
            let newLeft = currentLeft;
            
            // Container'a göre side constraint
            if (side === 'left') {
                // Sol taraftaki node'lar container'ın solunda olmalı
                const maxLeft = cRect.left - rect.width - sideGap;
                newLeft = Math.min(newLeft, maxLeft);
                // Ekranın sol kenarından taşmamalı
                newLeft = Math.max(newLeft, minGap);
            } else if (side === 'right') {
                // Sağ taraftaki node'lar container'ın sağında olmalı
                const minLeft = cRect.right + sideGap;
                newLeft = Math.max(newLeft, minLeft);
                // Ekranın sağ kenarından taşmamalı
                newLeft = Math.min(newLeft, window.innerWidth - rect.width - minGap);
            } else {
                // Side bilgisi yoksa genel sınır kontrolü
                newLeft = Math.max(minGap, Math.min(window.innerWidth - rect.width - minGap, newLeft));
            }
            
            // Dikey sınır kontrolü
            const newTop = Math.max(topOffset, Math.min(window.innerHeight - rect.height - minGap, currentTop));
            
            // Pozisyonu güncelle (sadece değişiklik varsa)
            if (Math.abs(newLeft - currentLeft) > 1 || Math.abs(newTop - currentTop) > 1) {
                node.style.left = newLeft + 'px';
                node.style.right = 'auto';
                node.style.top = newTop + 'px';
            }
        });
        
        // Halatları güncelle
        if (typeof updateRopesImmediate === 'function') {
            updateRopesImmediate();
        }
    } catch (e) {
        // Hata olsa da sessizce devam et
        console.error('constrainAllNodes error:', e);
    }
}

/**
 * Çalışma alanı yerleşimini toplar
 * @returns {{nodes: Array, groups: Object, flowerMode: boolean}}
 */
function collectWorkspaceLayout() {
    const nodeItems = [];
    document.querySelectorAll('.func-node').forEach(node => {
        const styleLeft = parseFloat(node.style.left);
        const styleTop = parseFloat(node.style.top);
        const rect = node.getBoundingClientRect();
        nodeItems.push({
            id: node.id,
            left: Number.isFinite(styleLeft) ? styleLeft : rect.left,
            top: Number.isFinite(styleTop) ? styleTop : rect.top,
            collapsed: node.classList.contains('collapsed'),
            side: node.dataset.side || null
        });
    });
    const groupStates = {};
    Object.keys(GROUPS || {}).forEach(key => {
        groupStates[key] = !!(GROUPS[key] && GROUPS[key].open);
    });
    return {
        nodes: nodeItems,
        groups: groupStates,
        flowerMode: !!window.__flowerMode
    };
}

/**
 * Çalışma alanı yerleşimini uygular
 * @param {Object} layout - Kaydedilmiş yerleşim verisi
 */
function applyWorkspaceLayout(layout) {
    if (!layout || typeof layout !== 'object') return;

    if (layout.groups && typeof layout.groups === 'object') {
        Object.keys(layout.groups).forEach(key => {
            if (GROUPS[key] && GROUPS[key].open !== layout.groups[key]) {
                setCollapsedState(key, !!layout.groups[key]);
            }
        });
    }

    if (Array.isArray(layout.nodes)) {
        layout.nodes.forEach(item => {
            const el = document.getElementById(item.id);
            if (!el) return;

            if (typeof item.collapsed === 'boolean') {
                if (item.collapsed) {
                    el.classList.add('collapsed');
                } else {
                    el.classList.remove('collapsed');
                }
            }

            const leftVal = parseFloat(item.left);
            const topVal = parseFloat(item.top);
            if (Number.isFinite(leftVal)) {
                el.style.left = leftVal + 'px';
                el.style.right = 'auto';
            }
            if (Number.isFinite(topVal)) {
                el.style.top = topVal + 'px';
            }
        });
    }

    if (typeof layout.flowerMode === 'boolean' && layout.flowerMode !== !!window.__flowerMode) {
        toggleFlowerMode();
    }

    if (typeof updateRopesImmediate === 'function') {
        updateRopesImmediate();
        requestAnimationFrame(stepRopes);
    }
}

/**
 * Çalışma alanı meta verilerini toplar
 * @returns {{matrixEnabled: boolean}}
 */
function collectWorkspaceMeta() {
    return {
        matrixEnabled: (typeof matrixEnabled === 'boolean') ? matrixEnabled : true
    };
}

/**
 * Çalışma alanı meta verisini uygular
 * @param {Object} meta - Kaydedilmiş meta verisi
 */
function applyWorkspaceMeta(meta) {
    if (!meta || typeof meta !== 'object') return;
    if (Object.prototype.hasOwnProperty.call(meta, 'matrixEnabled') && typeof meta.matrixEnabled === 'boolean') {
        if (typeof matrixEnabled === 'boolean' && matrixEnabled !== meta.matrixEnabled) {
            toggleMatrix();
        }
    }
}

/**
 * Çalışma alanı durumunu sunucuya kaydeder
 */
async function saveWorkspaceState() {
    const btn = document.getElementById('workspace-save-btn');
    const token = localStorage.getItem('access_token');
    if (!token) {
        if (btn) {
            const original = btn.textContent;
            btn.textContent = '⚠ Giriş gerekir';
            setTimeout(() => { btn.textContent = original; }, 1500);
        }
        return;
    }

    const layout = collectWorkspaceLayout();
    const meta = collectWorkspaceMeta();
    const themeName = document.documentElement.classList.contains('dark') ? 'dark' : 'light';

    try {
        if (btn) {
            btn.disabled = true;
            btn.textContent = 'Kaydediliyor...';
        }
        const response = await fetch('/auth/workspace/state', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify({
                layout_json: JSON.stringify(layout),
                matrix_json: JSON.stringify(meta),
                theme: themeName
            })
        });

        if (!response.ok) {
            throw new Error(`Kaydetme hatası: ${response.status}`);
        }

        window.__workspaceStateLoaded = true;
        if (btn) {
            btn.textContent = '✅ Kaydedildi';
        }
    } catch (error) {
        console.error('Workspace kaydetme hatası:', error);
        if (btn) {
            btn.textContent = '❌ Hata';
        }
    } finally {
        if (btn) {
            setTimeout(() => {
                btn.textContent = '💾 Kaydet';
                btn.disabled = false;
            }, 1600);
        }
    }
}

/**
 * Sunucudan çalışma alanı durumunu yükler
 */
async function loadWorkspaceState() {
    if (window.__workspaceStateLoading || window.__workspaceStateLoaded) return;
    const token = localStorage.getItem('access_token');
    if (!token) return;
    if (!window.__nodesInitialized) {
        setTimeout(loadWorkspaceState, 300);
        return;
    }

    window.__workspaceStateLoading = true;
    try {
        const response = await fetch('/auth/workspace/state', {
            method: 'GET',
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });
        if (!response.ok) {
            throw new Error(`Yükleme hatası: ${response.status}`);
        }
        const data = await response.json();

        if (data.theme && typeof applyTheme === 'function') {
            applyTheme(data.theme);
        }

        if (data.layout_json) {
            try {
                const layout = JSON.parse(data.layout_json);
                applyWorkspaceLayout(layout);
            } catch (e) {
                console.error('Yerleşim verisi parse hatası:', e);
            }
        }

        if (data.matrix_json) {
            try {
                const meta = JSON.parse(data.matrix_json);
                applyWorkspaceMeta(meta);
            } catch (e) {
                console.error('Matrix verisi parse hatası:', e);
            }
        }

        window.__workspaceStateLoaded = true;
    } catch (error) {
        console.error('Workspace yükleme hatası:', error);
    } finally {
        window.__workspaceStateLoading = false;
    }
}

