'use strict';
const {chromium} = require('playwright');
const assert = require('node:assert/strict');
(async () => {
    const browser = await chromium.launch({executablePath: process.env.CHROMIUM_BIN || '/usr/bin/chromium', args: ['--no-sandbox']});
    try {
        const page = await browser.newPage({viewport: {width: 390, height: 844}, isMobile: true, hasTouch: true});
        const errors = [], submissions = [];
        page.on('pageerror', error => errors.push(error.message));
        await page.route('**/*', route => /mc\.yandex\.ru|googletagmanager\.com|yandex\.ru/.test(new URL(route.request().url()).hostname) ? route.abort() : route.continue());
        await page.route('**/send-booking.php', async route => {
            submissions.push(route.request().postData());
            await route.fulfill({json: {status: 'success'}});
        });
        await page.goto((process.env.SITE_URL || 'http://127.0.0.1:8090/') + 'booking-preview.html', {waitUntil: 'networkidle'});
        await page.getByRole('button', {name: 'Только необходимые', exact: true}).click();
        const bar = page.locator('.mobile-nav');
        for (const width of [320, 360, 375, 390, 430]) {
            await page.setViewportSize({width, height: 844});
            assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false, `overflow at ${width}`);
            const rect = await bar.boundingBox();
            assert.ok(rect.y + rect.height <= 845, 'contact bar must stay inside viewport');
            assert.ok((await page.locator('.mobile-request').boundingBox()).height >= 44);
        }
        await page.setViewportSize({width: 390, height: 844});
        await page.screenshot({path: '/workspace/shared/downloads/mobile-hero.png'});
        await page.locator('.hero-actions').getByRole('link', {name: 'Выбрать автомобиль', exact: true}).click();
        await page.getByRole('button', {name: 'Автомат', exact: true}).click();
        assert.equal(await page.locator('#catalog .car-card:visible').count(), 4);
        await page.getByRole('button', {name: 'Механика', exact: true}).click();
        assert.equal(await page.locator('#catalog .car-card:visible').count(), 3);
        await page.getByRole('button', {name: 'Все авто', exact: true}).click();
        assert.equal(await page.locator('#catalog .car-card:visible').count(), 6);
        const solaris = page.locator('#catalog .car-card').nth(2);
        await solaris.locator('[data-variant="solaris-auto"]').click();
        assert.equal(await solaris.locator('[data-variant="solaris-auto"]').getAttribute('aria-pressed'), 'true');
        await solaris.getByRole('button', {name: 'Бронировать', exact: true}).click();
        assert.equal(await page.locator('#cb-vehicle').inputValue(), 'solaris-auto');
        assert.match(await page.locator('#bookingSummaryPrice').textContent(), /2\s*100/);
        assert.equal(await bar.isVisible(), false, 'contact bar must not overlap modal');
        await page.locator('#cb-vehicle').selectOption('haval-buyout');
        assert.match(await page.locator('#bookingSummaryPrice').textContent(), /3\s*500/);
        await page.waitForFunction(() => getComputedStyle(document.querySelector('#callbackModal')).opacity === '1' && getComputedStyle(document.querySelector('#callbackModal .modal-content')).opacity === '1');
        await page.screenshot({path: '/workspace/shared/downloads/mobile-booking-form.png'});
        // A smaller visible area approximates the space left by the software keyboard.
        await page.setViewportSize({width: 390, height: 500});
        await page.locator('#cb-name').fill('Анна');
        await page.locator('#cb-phone').fill('8 (999) 123-45-67');
        await page.locator('#cb-consent').check();
        await page.getByRole('button', {name: 'Отправить заявку на бронь', exact: true}).click();
        await page.locator('#bookingSuccess').waitFor({state: 'visible'});
        assert.equal(submissions.length, 1);
        assert.match(submissions[0], /haval-buyout/);
        assert.equal(await page.locator('#callbackForm').isVisible(), false);
        await page.getByRole('button', {name: 'Хорошо, спасибо', exact: true}).click();
        await page.locator('#callbackModal').waitFor({state: 'hidden'});
        await page.waitForFunction(() => !document.body.classList.contains('modal-open'));
        await page.setViewportSize({width: 390, height: 844});
        await page.locator('.mobile-request').click();
        await page.locator('#callbackForm').waitFor({state: 'visible'});
        assert.equal(await page.locator('#callbackForm').isVisible(), true);
        assert.equal(await page.locator('#bookingSuccess').isVisible(), false);
        assert.equal(await page.locator('#bookingSummary').isVisible(), false);
        await page.locator('#callbackModal').getByRole('button', {name: 'Закрыть', exact: true}).click();
        await page.locator('#callbackModal').waitFor({state: 'hidden'});
        await page.waitForFunction(() => !document.body.classList.contains('modal-open'));
        await page.locator('#catalog .car-card').first().scrollIntoViewIfNeeded();
        await page.screenshot({path: '/workspace/shared/downloads/mobile-catalog.png'});
        await page.emulateMedia({reducedMotion: 'reduce'});
        assert.equal(await page.evaluate(() => getComputedStyle(document.documentElement).scrollBehavior), 'auto');
        assert.deepEqual(errors, []);
        console.log('PASS: isolated preview, five phone widths, touch-sized sticky contacts, transmission filters, rate selection, model/price summary, small-height form, one booking, success state, clean reopening, reduced motion; no real messages.');
    } finally { await browser.close(); }
})().catch(error => {console.error(error); process.exitCode = 1;});
