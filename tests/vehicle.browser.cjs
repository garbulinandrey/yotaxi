'use strict';
const {chromium} = require('playwright');
const assert = require('node:assert/strict');
(async () => {
    const browser = await chromium.launch({executablePath: process.env.CHROMIUM_BIN || '/usr/bin/chromium', args: ['--no-sandbox']});
    try {
        const page = await browser.newPage({viewport: {width: 390, height: 844}, isMobile: true, hasTouch: true, reducedMotion: 'reduce'});
        const errors = [], requests = [];
        page.on('pageerror', error => errors.push(error.message));
        await page.route('**/*', route => /yandex\.ru|googletagmanager\.com/.test(new URL(route.request().url()).hostname) ? route.abort() : route.continue());
        await page.route('**/vehicle-galleries.json', route => route.fulfill({json: {
            // Synthetic gallery fixture; production contains only the supplied exterior.
            'vesta-2019-21': [1,2,3].map(number => ({src: `vesta21.jpeg?fixture=${number}`, caption: `Тестовый ракурс ${number}`}))
        }}));
        await page.route('**/send-booking.php', async route => {requests.push(route.request().postData()); await route.fulfill({json: {status: 'success'}});});
        const base = process.env.SITE_URL || 'http://127.0.0.1:8090/';
        await page.goto(base + (process.env.PREVIEW_PAGE || 'booking-preview.html'), {waitUntil: 'networkidle'});
        await page.getByRole('button', {name: 'Только необходимые', exact: true}).click();
        const cards = page.locator('#catalog .car-card');
        assert.equal(await cards.first().locator('.car-highlights').getByText('Кондиционер', {exact: true}).isVisible(), true);
        assert.equal(await page.locator('.rental-assurances li').count(), 3);
        await page.getByRole('button', {name: 'Автомат', exact: true}).click();
        const auto = cards.nth(2);
        await auto.getByRole('button', {name: 'Подробнее', exact: true}).evaluate(element => element.scrollIntoView({block: 'center', behavior: 'instant'}));
        const scroll = await page.evaluate(() => scrollY);
        await auto.getByRole('button', {name: 'Подробнее', exact: true}).click();
        const dialog = page.locator('#vehicleDialog');
        await dialog.waitFor({state: 'visible'});
        assert.equal(await dialog.locator('#vehicleTitle').textContent(), 'Solaris');
        assert.equal(await dialog.locator('#vehicleModelCount').textContent(), '1 / 4');
        assert.equal(await dialog.locator('#vehiclePhotoNext').isVisible(), false);
        await dialog.getByRole('button', {name: 'Следующая модель', exact: true}).click();
        assert.equal(await dialog.locator('#vehicleTitle').textContent(), 'Jetta VA3');
        await dialog.getByRole('button', {name: 'Назад к автомобилям', exact: true}).click();
        await dialog.waitFor({state: 'hidden'});
        await page.waitForFunction(() => !location.hash.startsWith('#car='));
        assert.equal(await page.getByRole('button', {name: 'Автомат', exact: true}).getAttribute('aria-pressed'), 'true');
        const restored = await page.evaluate(() => scrollY);
        assert.ok(Math.abs(restored - scroll) < 3, `catalog scroll must be preserved: before ${scroll}, after ${restored}`);
        await page.getByRole('button', {name: 'Все авто', exact: true}).click();
        await cards.first().getByRole('button', {name: 'Смотреть Lada Vesta', exact: true}).click();
        assert.equal(await dialog.locator('#vehiclePhotoCount').textContent(), '1 / 3');
        await dialog.getByRole('button', {name: 'Следующее фото', exact: true}).click();
        assert.equal(await dialog.locator('#vehiclePhotoCaption').textContent(), 'Тестовый ракурс 2');
        await dialog.getByRole('button', {name: 'Фото 3: Тестовый ракурс 3', exact: true}).click();
        assert.equal(await dialog.locator('#vehiclePhotoCount').textContent(), '3 / 3');
        await dialog.locator('#vehicleGallery').focus();
        await page.keyboard.press('ArrowLeft');
        assert.equal(await dialog.locator('#vehiclePhotoCount').textContent(), '2 / 3');
        await dialog.locator('#vehicleGallery').dispatchEvent('pointerdown', {pointerType:'touch', clientX:260, clientY:100});
        await dialog.locator('#vehicleGallery').dispatchEvent('pointerup', {pointerType:'touch', clientX:100, clientY:110});
        assert.equal(await dialog.locator('#vehiclePhotoCount').textContent(), '3 / 3');
        for (const width of [320,390,768,1440]) {
            await page.setViewportSize({width,height:844});
            assert.equal(await dialog.evaluate(element => element.scrollWidth > element.clientWidth), false, `dialog overflow at ${width}`);
        }
        await page.setViewportSize({width:390,height:844});
        await page.keyboard.press('Escape');
        await dialog.waitFor({state:'hidden'});
        await page.waitForFunction(() => !location.hash.startsWith('#car='));
        await cards.last().getByRole('button', {name:'Подробнее',exact:true}).click();
        await page.goBack();
        await dialog.waitFor({state:'hidden'});
        await auto.getByRole('button', {name:'Подробнее',exact:true}).click();
        await dialog.locator('[data-variant="solaris-auto"]').click();
        assert.match(await dialog.locator('#vehicleFooterPrice').textContent(), /2\s*100/);
        await dialog.getByRole('button', {name:'Забронировать',exact:true}).click();
        await page.locator('#callbackModal').waitFor({state:'visible'});
        assert.equal(await dialog.isVisible(), false);
        assert.equal(await page.locator('#cb-vehicle').inputValue(), 'solaris-auto');
        await page.locator('#cb-name').fill('Анна');
        await page.locator('#cb-phone').fill('89991234567');
        await page.locator('#cb-consent').check();
        await page.getByRole('button', {name:'Отправить заявку на бронь',exact:true}).click();
        await page.locator('#bookingSuccess').waitFor({state:'visible'});
        assert.equal(requests.length,1); assert.match(requests[0],/solaris-auto/);
        assert.deepEqual(errors,[]);
        console.log('PASS: visible benefits, standalone vehicle dialog, filtered model navigation, preserved scroll, photo arrows/thumbnails/keys/swipe, one-photo fallback, responsive overlay, Escape/browser Back, correct booking variant and consent. No real messages.');
    } finally {await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
