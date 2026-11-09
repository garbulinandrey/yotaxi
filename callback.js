'use strict';

document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('callbackForm');
    if (!form) return;
    const button = document.getElementById('callbackSubmit');
    const status = document.getElementById('callbackStatus');
    const fields = {
        name: document.getElementById('cb-name'),
        phone: document.getElementById('cb-phone')
    };
    const vehicle = document.getElementById('cb-vehicle');
    const consent = document.getElementById('cb-consent');
    const modal = document.getElementById('callbackModal');
    if (vehicle) fields.vehicle = vehicle;
    if (consent) fields.consent = consent;
    let booking = false;
    let sending = false;
    const idleLabel = () => booking ? 'Отправить заявку на бронь' : 'Жду звонка';
    const showStatus = (message, success = false) => {
        status.textContent = message;
        status.className = `mt-3 mb-0 ${success ? 'text-success' : 'text-warning'}`;
    };
    const showError = (key, message) => {
        fields[key].classList.toggle('is-invalid', Boolean(message));
        fields[key].setAttribute('aria-invalid', String(Boolean(message)));
        document.getElementById(`cb-${key}-error`).textContent = message;
    };
    Object.entries(fields).forEach(([key, input]) => {
        input.addEventListener('input', () => showError(key, ''));
    });
    if (modal) modal.addEventListener('show.bs.modal', event => {
        if (sending) { event.preventDefault(); return; }
        const selected = event.relatedTarget?.getAttribute('data-vehicle') || '';
        booking = Boolean(selected);
        vehicle.value = selected;
        vehicle.required = booking;
        document.getElementById('cb-vehicle-group').hidden = !booking;
        const title = booking ? 'Заявка на бронирование' : 'Заказать звонок';
        modal.querySelector('.modal-title').textContent = title;
        modal.setAttribute('aria-label', title);
        button.textContent = idleLabel();
        showStatus('');
        Object.keys(fields).forEach(key => showError(key, ''));
    });
    form.addEventListener('submit', async event => {
        event.preventDefault();
        if (sending) return;
        showStatus('');
        Object.keys(fields).forEach(key => showError(key, ''));
        const name = fields.name.value.trim();
        const phone = fields.phone.value.trim();
        const digits = phone.replace(/[^0-9]/g, '');
        const errors = {};
        if (booking && !vehicle.value) errors.vehicle = 'Выберите автомобиль и вариант.';
        if (consent && !consent.checked) errors.consent = 'Подтвердите согласие на обработку данных.';
        if (!/^[\p{L}\p{M}][\p{L}\p{M} '\u2019-]{1,79}$/u.test(name)) {
            errors.name = 'Введите имя: от 2 до 80 букв, можно с пробелом или дефисом.';
        }
        if (phone.length > 40 || !/^\+?[0-9 ()-]+$/.test(phone) || !/^[78][0-9]{10}$/.test(digits)) {
            errors.phone = 'Введите российский номер: +7 (999) 123-45-67 или 8 999 123-45-67.';
        }
        if (Object.keys(errors).length) {
            Object.entries(errors).forEach(([key, message]) => showError(key, message));
            fields[Object.keys(errors)[0]].focus();
            return;
        }
        const selectedVehicle = vehicle?.value || '';
        const data = new FormData(form);
        data.set('name', name);
        data.set('phone', '+7' + digits.slice(1));
        sending = true;
        button.disabled = true;
        if (vehicle) vehicle.disabled = true;
        button.textContent = 'Отправка…';
        form.setAttribute('aria-busy', 'true');
        showStatus('Отправляем заявку…');
        const controller = new AbortController();
        const timeout = setTimeout(() => controller.abort(), 18000);
        try {
            const response = await fetch('send.php', {
                method: 'POST', body: data, signal: controller.signal
            });
            const result = await response.json();
            if (response.ok && result.status === 'success') {
                form.reset();
                if (vehicle) vehicle.value = selectedVehicle;
                showStatus(booking ? 'Заявка на бронирование принята. Менеджер свяжется с вами и подтвердит наличие автомобиля.' : 'Спасибо! Заявка принята. Свяжемся с вами в рабочее время.', true);
            } else {
                if (result.errors && typeof result.errors === 'object') {
                    Object.keys(fields).forEach(key => {
                        if (typeof result.errors[key] === 'string') showError(key, result.errors[key]);
                    });
                    const invalid = Object.keys(fields).find(key => result.errors[key]);
                    if (invalid) fields[invalid].focus();
                }
                showStatus(typeof result.message === 'string' && result.message ? result.message :
                    'Не удалось подтвердить отправку. Позвоните: +7 (927) 883-55-66.');
            }
        } catch {
            // A timeout does not prove delivery failed. Never resend automatically.
            showStatus('Не удалось подтвердить отправку. Позвоните: +7 (927) 883-55-66.');
        } finally {
            clearTimeout(timeout);
            sending = false;
            button.disabled = false;
            button.textContent = idleLabel();
            if (vehicle) vehicle.disabled = false;
            form.setAttribute('aria-busy', 'false');
        }
    });
});
