'use strict';
document.addEventListener('DOMContentLoaded', () => {
    const cards = [...document.querySelectorAll('#catalog .car-card')];
    const vehicle = document.getElementById('cb-vehicle');
    const modal = document.getElementById('callbackModal');
    const form = document.getElementById('callbackForm');
    const summary = document.getElementById('bookingSummary');
    const success = document.getElementById('bookingSuccess');
    const variants = new Map();
    cards.forEach(card => {
        const trigger = card.querySelector('.booking-trigger');
        const image = card.querySelector('.car-img-wrapper img');
        const title = card.querySelector('h3').textContent;
        const year = card.querySelector('.car-year').textContent.trim();
        const rates = [...card.querySelectorAll('.car-rate')];
        rates.forEach(rate => {
            const key = rate.dataset.variant || trigger.dataset.vehicle;
            variants.set(key, {
                image: image.getAttribute('src'),
                title: `${title} ${year}`.trim(),
                label: rate.querySelector('.car-rate-label').textContent,
                price: rate.querySelector('.car-rate-value').textContent
            });
            if (!rate.matches('button')) return;
            rate.addEventListener('click', () => {
                rates.forEach(other => other.setAttribute('aria-pressed', String(other === rate)));
                trigger.dataset.vehicle = key;
            });
        });
    });
    const updateSummary = () => {
        const selected = variants.get(vehicle.value);
        summary.hidden = !selected;
        if (!selected) return;
        const image = document.getElementById('bookingSummaryImage');
        image.src = selected.image;
        image.alt = selected.title;
        document.getElementById('bookingSummaryName').textContent = `${selected.title} · ${selected.label}`;
        document.getElementById('bookingSummaryPrice').textContent = `${selected.price} /сутки`;
    };
    vehicle.addEventListener('change', updateSummary);
    modal.addEventListener('show.bs.modal', event => {
        if (event.defaultPrevented) return;
        form.hidden = false;
        success.hidden = true;
        document.getElementById('callbackFootnote').hidden = false;
        modal.querySelector('.callback-intro').hidden = false;
        updateSummary();
        const menu = document.getElementById('navbarNav');
        if (menu.classList.contains('show') && window.bootstrap) {
            window.bootstrap.Collapse.getOrCreateInstance(menu, {toggle: false}).hide();
        }
    });
    form.addEventListener('booking:success', () => {
        form.hidden = true;
        success.hidden = false;
        document.getElementById('callbackFootnote').hidden = true;
        modal.querySelector('.callback-intro').hidden = true;
        modal.querySelector('.modal-body').scrollTop = 0;
        success.querySelector('h3').focus({preventScroll: true});
    });
    const filters = [...document.querySelectorAll('[data-filter]')];
    filters.forEach(button => button.addEventListener('click', () => {
        const filter = button.dataset.filter;
        filters.forEach(other => other.setAttribute('aria-pressed', String(other === button)));
        let count = 0;
        cards.forEach(card => {
            const visible = filter === 'all' || card.dataset.gearbox.split(' ').includes(filter);
            card.parentElement.hidden = !visible;
            if (visible) count++;
        });
        const word = count === 1 ? 'модель' : count > 1 && count < 5 ? 'модели' : 'моделей';
        document.getElementById('catalogCount').textContent = `${count} ${word} · наличие уточнит менеджер`;
        window.AOS?.refresh();
    }));
    document.querySelectorAll('#navbarNav a[href^="#"]').forEach(link => link.addEventListener('click', () => {
        if (window.bootstrap) window.bootstrap.Collapse.getOrCreateInstance(document.getElementById('navbarNav'), {toggle: false}).hide();
    }));
});
