'use strict';
// Run against a local static copy: SITE_URL=http://127.0.0.1:8090/ node tests/booking.browser.cjs
const {chromium} = require('playwright');
const assert = require('node:assert/strict');
(async () => {
    const browser = await chromium.launch({executablePath: process.env.CHROMIUM_BIN || '/usr/bin/chromium', args: ['--no-sandbox']});
    try {
        const page = await browser.newPage({viewport: {width: 1440, height: 1000}, reducedMotion: 'reduce'});
        const errors = [], submissions = [], trackers = [];
        page.on('pageerror', error => errors.push(error.message));
        await page.route('**/*', route => {
            const url = new URL(route.request().url());
            if (/mc\.yandex\.ru|googletagmanager\.com|google-analytics\.com/.test(url.hostname)) {
                trackers.push(url.href); return route.abort();
            }
            if (url.hostname === 'yandex.ru') return route.abort();
            return route.continue();
        });
        await page.route('**/send.php', async route => {
            submissions.push(route.request().postData());
            await route.fulfill({json: {status: 'success'}});
        });
        const base = process.env.SITE_URL || 'http://127.0.0.1:8090/';
        await page.goto(base, {waitUntil: 'networkidle'});
        assert.equal(trackers.length, 0, 'optional analytics must not load before permission');
        await page.getByRole('button', {name: 'Только необходимые', exact: true}).click();
        assert.equal(await page.evaluate(() => localStorage.getItem('yotaxi-analytics-v1')), 'deny');
        for (const width of [320, 390, 768, 1024, 1440]) {
            await page.setViewportSize({width, height: 1000});
            assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false, `overflow at ${width}`);
        }
        const cards = page.locator('#catalog .car-card');
        assert.equal(await cards.count(), 6);
        const tops = await cards.evaluateAll(items => items.map(item => Math.round(item.querySelector('.car-rates').getBoundingClientRect().top - item.getBoundingClientRect().top)));
        assert.ok(tops.every(top => top === tops[0]), 'prices should occupy the same place in each card');
        for (const [index, model] of ['vesta-2019-21', 'vesta-2023', 'solaris-manual', 'jetta', 'solaris-2024', 'haval-rent'].entries()) {
            await cards.nth(index).getByRole('button', {name: 'Бронировать', exact: true}).click();
            await page.locator('#callbackModal').waitFor({state: 'visible'});
            assert.equal(await page.locator('#cb-vehicle').inputValue(), model);
            await page.locator('#callbackModal').getByRole('button', {name: 'Закрыть', exact: true}).click();
            await page.locator('#callbackModal').waitFor({state: 'hidden'});
        }
        await cards.nth(5).getByRole('button', {name: 'Бронировать', exact: true}).click();
        await page.locator('#cb-vehicle').selectOption('haval-buyout');
        await page.locator('#cb-name').fill('Анна');
        await page.locator('#cb-phone').fill('8 (999) 123-45-67');
        await page.getByRole('button', {name: 'Отправить заявку на бронь', exact: true}).click();
        assert.equal(submissions.length, 0, 'unchecked consent must prevent delivery');
        assert.equal(await page.locator('#cb-consent').getAttribute('aria-invalid'), 'true');
        for (const file of ['privacy.html', 'consent.html']) {
            assert.ok(await page.locator(`#callbackModal a[href="${file}"][target="_blank"]`).count());
            const response = await page.request.get(base + file);
            assert.equal(response.status(), 200);
        }
        await page.locator('#cb-consent').check();
        await page.getByRole('button', {name: 'Отправить заявку на бронь', exact: true}).click();
        await page.waitForFunction(() => document.getElementById('callbackStatus').textContent.includes('Менеджер'));
        assert.equal(submissions.length, 1);
        assert.match(submissions[0], /haval-buyout/);
        assert.match(submissions[0], /2026-11-09/);
        assert.match(submissions[0], /\+79991234567/);
        assert.equal(await page.locator('#cb-consent').isChecked(), false);
        assert.equal(await page.locator('#cb-vehicle').inputValue(), 'haval-buyout');
        await page.locator('#callbackModal').getByRole('button', {name: 'Закрыть', exact: true}).click();
        await page.locator('#callbackModal').waitFor({state: 'hidden'});
        await page.evaluate(() => scrollTo(0, 0));
        await page.getByRole('button', {name: 'Заказать звонок', exact: true}).click();
        assert.equal(await page.locator('#cb-vehicle-group').isVisible(), false);
        assert.equal(await page.locator('#cb-vehicle').inputValue(), '');
        await page.locator('#callbackModal').getByRole('button', {name: 'Закрыть', exact: true}).click();
        await page.locator('#callbackModal').waitFor({state: 'hidden'});
        const details = cards.first().locator('.car-details');
        await details.locator(':scope > summary').click();
        await details.getByText('Кондиционер', {exact: true}).click();
        assert.equal(await details.getByText('Охлаждение воздуха в салоне.', {exact: true}).isVisible(), true);
        assert.equal(await details.locator('figure img').isVisible(), true);
        await details.locator(':scope > summary').click();
        await page.reload({waitUntil: 'networkidle'});
        assert.equal(await page.locator('#analyticsNotice').isVisible(), false);
        assert.equal(trackers.length, 0);
        await page.getByRole('button', {name: 'Настройки аналитики', exact: true}).click();
        await page.getByRole('button', {name: 'Разрешить аналитику', exact: true}).click();
        await page.waitForFunction(() => document.querySelector('script[src*="metrika/tag.js"]'));
        assert.equal(await page.evaluate(() => localStorage.getItem('yotaxi-analytics-v1')), 'allow');
        assert.deepEqual(errors, []);
        console.log('PASS: responsive cards, six model selections, Haval buyout, required consent, booking payload, ordinary callback, disclosures/photos, legal links and opt-in analytics. No real submissions.');
    } finally { await browser.close(); }
})().catch(error => {console.error(error); process.exitCode = 1;});
