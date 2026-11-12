'use strict';
document.addEventListener('DOMContentLoaded', () => {
    const dialog = document.getElementById('vehicleDialog');
    if (!dialog) return;
    const cards = [...document.querySelectorAll('#catalog .car-card')];
    const byId = id => document.getElementById(id);
    let models = [], current = null, modelIndex = 0, photoIndex = 0;
    let opener = null, catalogScroll = 0, ownsHistory = false;
    let galleries = {};
    const galleryFor = card => galleries[card.dataset.car] || [{src: card.querySelector('.car-img-wrapper img').getAttribute('src'), caption: 'Внешний вид'}];
    const safePhotos = photos => Array.isArray(photos) ? photos.slice(0, 12).filter(photo => {
        if (!photo || typeof photo.src !== 'string' || typeof photo.caption !== 'string') return false;
        try {
            const url = new URL(photo.src, document.baseURI);
            return url.origin === location.origin && /\.(?:jpe?g|png|webp|avif)$/i.test(url.pathname) && photo.caption.length <= 140;
        } catch { return false; }
    }) : [];
    const script = document.querySelector('script[src*="vehicle.js"]');
    if (script) fetch(new URL('vehicle-galleries.json', script.src), {cache: 'no-cache'}).then(response => {
        if (!response.ok) throw Error('Gallery unavailable');
        return response.json();
    }).then(data => {
        for (const card of cards) {
            const photos = safePhotos(data?.[card.dataset.car]);
            if (photos.length) galleries[card.dataset.car] = photos;
        }
        if (dialog.open) renderPhoto();
    }).catch(() => { /* Existing exterior images remain available without a manifest. */ });

    function renderPhoto() {
        const photos = galleryFor(current);
        photoIndex = Math.min(photoIndex, photos.length - 1);
        const photo = photos[photoIndex];
        const image = byId('vehicleGalleryImage');
        image.src = photo.src;
        image.alt = `${current.querySelector('h3').textContent} — ${photo.caption}`;
        byId('vehiclePhotoCaption').textContent = photo.caption;
        byId('vehiclePhotoCount').textContent = photos.length > 1 ? `${photoIndex + 1} / ${photos.length}` : '1 фото';
        byId('vehiclePhotoPrev').hidden = photos.length < 2;
        byId('vehiclePhotoNext').hidden = photos.length < 2;
        const thumbs = byId('vehicleThumbnails');
        thumbs.replaceChildren();
        thumbs.hidden = photos.length < 2;
        photos.forEach((item, index) => {
            const button = document.createElement('button');
            button.type = 'button';
            button.setAttribute('aria-label', `Фото ${index + 1}: ${item.caption}`);
            button.setAttribute('aria-pressed', String(index === photoIndex));
            const thumbnail = document.createElement('img');
            thumbnail.src = item.src; thumbnail.alt = ''; thumbnail.loading = 'lazy';
            button.append(thumbnail);
            button.addEventListener('click', () => { photoIndex = index; renderPhoto(); });
            thumbs.append(button);
        });
    }
    function movePhoto(direction) {
        const photos = galleryFor(current);
        if (photos.length < 2) return;
        photoIndex = (photoIndex + direction + photos.length) % photos.length;
        renderPhoto();
    }
    function renderRates() {
        const container = byId('vehicleRates');
        const clone = current.querySelector('.car-rates').cloneNode(true);
        clone.querySelectorAll('[data-variant]').forEach(button => {
            button.addEventListener('click', () => {
                current.querySelector(`[data-variant="${button.dataset.variant}"]`).click();
                renderRates();
                byId('vehicleRates').querySelector(`[data-variant="${button.dataset.variant}"]`).focus({preventScroll: true});
            });
        });
        container.replaceChildren(clone);
        const rate = current.querySelector('.car-rate[aria-pressed="true"]') || current.querySelector('.car-rate');
        byId('vehicleFooterLabel').textContent = rate.querySelector('.car-rate-label').textContent;
        byId('vehicleFooterPrice').textContent = rate.querySelector('.car-rate-value').textContent;
        byId('vehicleBook').dataset.vehicle = current.querySelector('.booking-trigger').dataset.vehicle;
    }
    function renderModel() {
        current = models[modelIndex];
        photoIndex = 0;
        byId('vehicleTitle').textContent = current.querySelector('h3').textContent;
        byId('vehicleYear').textContent = current.querySelector('.car-year').textContent.trim();
        byId('vehicleModelCount').textContent = `${modelIndex + 1} / ${models.length}`;
        byId('vehicleModelPrev').disabled = modelIndex === 0;
        byId('vehicleModelNext').disabled = modelIndex === models.length - 1;
        byId('vehicleTags').replaceChildren(...[...current.querySelector('.car-tags').childNodes].map(node => node.cloneNode(true)));
        const content = current.querySelector('.vehicle-content').content.cloneNode(true);
        content.querySelectorAll('figure').forEach(figure => figure.remove());
        byId('vehicleDescription').replaceChildren(content);
        renderRates(); renderPhoto();
        dialog.querySelector('.vehicle-view-scroll').scrollTop = 0;
        if (ownsHistory) history.replaceState({...history.state, vehicleView: true}, '', '#car=' + current.dataset.car);
    }
    function openModel(card, trigger) {
        models = cards.filter(item => !item.parentElement.hidden);
        modelIndex = models.indexOf(card);
        if (modelIndex < 0) return;
        opener = trigger; catalogScroll = scrollY;
        ownsHistory = true;
        history.pushState({...history.state, vehicleView: true}, '', '#car=' + card.dataset.car);
        renderModel();
        document.body.classList.add('vehicle-view-open');
        dialog.showModal();
        byId('vehicleBack').focus({preventScroll: true});
    }
    function closeView() {
        document.body.classList.remove('vehicle-view-open');
        dialog.close();
        if (ownsHistory) { ownsHistory = false; history.back(); }
    }
    cards.forEach(card => card.querySelectorAll('.car-detail-trigger, .car-photo-trigger').forEach(button => {
        button.addEventListener('click', () => openModel(card, button));
    }));
    byId('vehicleBack').addEventListener('click', closeView);
    dialog.addEventListener('cancel', event => { event.preventDefault(); closeView(); });
    dialog.addEventListener('close', () => {
        document.body.classList.remove('vehicle-view-open');
        window.scrollTo({top: catalogScroll, behavior: 'instant'});
        opener?.focus({preventScroll: true});
    });
    window.addEventListener('popstate', () => {
        if (dialog.open) { ownsHistory = false; closeView(); }
    });
    dialog.addEventListener('click', event => {
        if (event.target !== dialog) return;
        const rect = dialog.getBoundingClientRect();
        if (event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom) closeView();
    });
    byId('vehiclePhotoPrev').addEventListener('click', () => movePhoto(-1));
    byId('vehiclePhotoNext').addEventListener('click', () => movePhoto(1));
    byId('vehicleModelPrev').addEventListener('click', () => { if (modelIndex > 0) { modelIndex--; renderModel(); } });
    byId('vehicleModelNext').addEventListener('click', () => { if (modelIndex < models.length - 1) { modelIndex++; renderModel(); } });
    byId('vehicleBook').addEventListener('click', () => {
        const trigger = byId('vehicleBook');
        closeView();
        if (window.bootstrap) window.bootstrap.Modal.getOrCreateInstance(byId('callbackModal')).show(trigger);
    });
    const gallery = byId('vehicleGallery');
    gallery.addEventListener('keydown', event => {
        if (event.target !== gallery) return;
        if (event.key === 'ArrowLeft' || event.key === 'ArrowRight') { event.preventDefault(); movePhoto(event.key === 'ArrowLeft' ? -1 : 1); }
    });
    let touch = null;
    gallery.addEventListener('pointerdown', event => {
        if (event.pointerType !== 'touch' || event.target.closest('button')) return;
        touch = {x: event.clientX, y: event.clientY};
    });
    gallery.addEventListener('pointercancel', () => { touch = null; });
    gallery.addEventListener('pointerup', event => {
        if (!touch) return;
        const dx = event.clientX - touch.x, dy = event.clientY - touch.y; touch = null;
        if (Math.abs(dx) < 45 || Math.abs(dx) < Math.abs(dy) * 1.4) return;
        if (galleryFor(current).length > 1) movePhoto(dx < 0 ? 1 : -1);
        else if (dx < 0) byId('vehicleModelNext').click();
        else byId('vehicleModelPrev').click();
    });
});
