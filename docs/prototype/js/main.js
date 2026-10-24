document: {
    const images = [];
    const waterfallContainer = document.getElementById('waterfall-container');
    const lightbox = document.getElementById('lightbox');
    const lightboxImg = document.getElementById('lightbox-img');
    const closeBtn = document.querySelector('.close-btn');
    const prevBtn = document.querySelector('.prev-btn');
    const nextBtn = document.querySelector('.next-btn');
    const selectedCountEl = document.getElementById('selected-count');
    const batchActionsEl = document.getElementById('batch-actions');

    let currentImgIndex = 0;
    let selectedIds = new Set();

    // 模拟生成 50 张图片数据
    function generateMockData() {
        for (let i = 1; i <= 50; i++) {
            const width = Math.floor(Math.random() * 400) + 300;
            const height = Math.floor(Math.random() * 500) + 300;
            images.push({
                id: i,
                url: `https://picsum.photos/seed/${i + 100}/${width}/${height}`,
                name: `IMG_${i.toString().padStart(4, '0')}.jpg`,
                size: `${(Math.random() * 5 + 1).toFixed(1)} MB`,
                resolution: `${width * 4} x ${height * 4}`
            });
        }
    }

    // 渲染瀑布流
    function renderWaterfall() {
        waterfallContainer.innerHTML = '';
        images.forEach((img, index) => {
            const card = document.createElement('div');
            card.className = 'img-card' + (selectedIds.has(img.id) ? ' selected' : '');
            card.innerHTML = `
                <div class="select-indicator"></div>
                <img src="${img.url}" alt="${img.name}" loading="lazy">
                <div class="card-overlay">
                    <button class="action-btn fav-btn"><i class="far fa-heart"></i></button>
                    <button class="action-btn more-btn"><i class="fas fa-ellipsis-v"></i></button>
                </div>
                <div class="img-info">
                    <div class="img-name">${img.name}</div>
                    <div class="img-meta">${img.size} | 2024-02-28</div>
                </div>
            `;

            // 点击查看原图
            card.addEventListener('click', (e) => {
                if (e.target.closest('.select-indicator')) {
                    toggleSelect(img.id, card);
                } else if (e.target.closest('.action-btn')) {
                    // 处理按钮点击
                    const btn = e.target.closest('.action-btn');
                    if (btn.classList.contains('fav-btn')) {
                        btn.querySelector('i').classList.toggle('fas');
                        btn.querySelector('i').classList.toggle('far');
                        btn.style.color = btn.querySelector('i').classList.contains('fas') ? '#ff4757' : 'white';
                    }
                } else {
                    openLightbox(index);
                }
            });

            waterfallContainer.appendChild(card);
        });
    }

    // 选择逻辑
    function toggleSelect(id, element) {
        if (selectedIds.has(id)) {
            selectedIds.delete(id);
            element.classList.remove('selected');
        } else {
            selectedIds.add(id);
            element.classList.add('selected');
        }
        updateStatus();
    }

    function updateStatus() {
        const count = selectedIds.size;
        selectedCountEl.textContent = count;
        batchActionsEl.style.display = count > 0 ? 'flex' : 'none';
    }

    // 灯箱逻辑
    function openLightbox(index) {
        currentImgIndex = index;
        const img = images[index];
        lightboxImg.src = img.url;
        document.getElementById('meta-filename').textContent = img.name;
        document.getElementById('meta-resolution').textContent = img.resolution;
        lightbox.style.display = 'flex';
        document.body.style.overflow = 'hidden';
    }

    function closeLightbox() {
        lightbox.style.display = 'none';
        document.body.style.overflow = '';
    }

    function showPrev() {
        currentImgIndex = (currentImgIndex - 1 + images.length) % images.length;
        openLightbox(currentImgIndex);
    }

    function showNext() {
        currentImgIndex = (currentImgIndex + 1) % images.length;
        openLightbox(currentImgIndex);
    }

    // 事件监听
    closeBtn.addEventListener('click', closeLightbox);
    prevBtn.addEventListener('click', (e) => { e.stopPropagation(); showPrev(); });
    nextBtn.addEventListener('click', (e) => { e.stopPropagation(); showNext(); });
    
    // 遮罩层点击关闭
    document.querySelector('.lightbox-overlay').addEventListener('click', closeLightbox);

    // 键盘支持
    document.addEventListener('keydown', (e) => {
        if (lightbox.style.display === 'flex') {
            if (e.key === 'Escape') closeLightbox();
            if (e.key === 'ArrowLeft') showPrev();
            if (e.key === 'ArrowRight') showNext();
        }
    });

    // 初始化
    generateMockData();
    renderWaterfall();
}
