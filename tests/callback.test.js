'use strict';
const {test} = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const path = require('node:path');
const source = fs.readFileSync(path.join(__dirname, '../callback.js'), 'utf8');

function setup(fetchResult) {
    const elements = {};
    for (const id of ['callbackForm', 'callbackSubmit', 'callbackStatus', 'cb-name', 'cb-phone', 'cb-name-error', 'cb-phone-error']) {
        elements[id] = {
            value: '', textContent: '', handlers: {}, attrs: {},
            classList: {toggle() {}},
            setAttribute(key, value) {this.attrs[key] = value;},
            addEventListener(event, callback) {this.handlers[event] = callback;},
            focus() {this.focused = true;}
        };
    }
    elements['cb-name'].value = 'Анна';
    elements['cb-phone'].value = '8 (999) 123-45-67';
    elements.callbackForm.reset = () => {
        elements['cb-name'].value = '';
        elements['cb-phone'].value = '';
    };
    const calls = [];
    class Data {
        constructor() {this.values = {website: ''};}
        set(key, value) {this.values[key] = value;}
    }
    vm.runInNewContext(source, {
        document: {getElementById: id => elements[id], addEventListener: (_, fn) => fn()},
        FormData: Data, AbortController, setTimeout, clearTimeout,
        fetch: async (url, options) => {calls.push({url, options}); return fetchResult();}
    });
    return {elements, calls, submit: () => elements.callbackForm.handlers.submit({preventDefault() {}})};
}

test('invalid phone stays local and focuses its error field', async () => {
    const view = setup(() => {throw Error('must not send');});
    view.elements['cb-phone'].value = 'not a phone';
    await view.submit();
    assert.equal(view.calls.length, 0);
    assert.equal(view.elements['cb-phone'].attrs['aria-invalid'], 'true');
    assert.equal(view.elements['cb-phone'].focused, true);
});

test('success normalizes phone, resets form, and works without AOS or Bootstrap', async () => {
    const view = setup(() => ({ok: true, json: async () => ({status: 'success'})}));
    await view.submit();
    assert.equal(view.calls[0].url, 'send-booking.php');
    assert.equal(view.calls[0].options.body.values.phone, '+79991234567');
    assert.equal(view.calls[0].options.body.values.name, 'Анна');
    assert.equal(view.elements['cb-phone'].value, '');
    assert.match(view.elements.callbackStatus.textContent, /Заявка принята/);
    assert.equal(view.elements.callbackSubmit.disabled, false);
});

test('server rejection shows field errors and preserves entered data', async () => {
    const view = setup(() => ({ok: false, json: async () => ({status: 'error', message: 'Проверьте номер', errors: {phone: 'Ошибка номера'}})}));
    await view.submit();
    assert.equal(view.elements['cb-phone-error'].textContent, 'Ошибка номера');
    assert.equal(view.elements['cb-phone'].value, '8 (999) 123-45-67');
    assert.equal(view.elements.callbackStatus.textContent, 'Проверьте номер');
});

test('network or malformed response gives no false success and no automatic retry', async () => {
    for (const result of [() => {throw Error('offline');}, () => ({json: async () => {throw Error('invalid json');}})]) {
        const view = setup(result);
        await view.submit();
        assert.equal(view.calls.length, 1);
        assert.match(view.elements.callbackStatus.textContent, /Не удалось подтвердить/);
        assert.equal(view.elements['cb-name'].value, 'Анна');
        assert.equal(view.elements.callbackSubmit.disabled, false);
    }
});

test('double submit creates one request and a 429 is displayed', async () => {
    let release;
    const view = setup(() => new Promise(resolve => {release = resolve;}));
    const pending = view.submit();
    await view.submit();
    assert.equal(view.calls.length, 1);
    assert.equal(view.elements.callbackSubmit.disabled, true);
    release({ok: false, json: async () => ({status: 'error', message: 'Попробуйте через 10 минут'})});
    await pending;
    assert.equal(view.elements.callbackStatus.textContent, 'Попробуйте через 10 минут');
});
