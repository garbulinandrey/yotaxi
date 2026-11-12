'use strict';
document.addEventListener('DOMContentLoaded', () => {
    const notice = document.getElementById('analyticsNotice');
    if (!notice) return;
    const key = 'yotaxi-analytics-v1';
    let loaded = false;
    const loadAnalytics = () => {
        if (loaded) return;
        loaded = true;
        window.ym = window.ym || function () { (window.ym.a = window.ym.a || []).push(arguments); };
        window.ym.l = Date.now();
        const metrika = document.createElement('script');
        metrika.src = 'https://mc.yandex.ru/metrika/tag.js'; metrika.async = true;
        document.head.append(metrika);
        window.ym(103286938, 'init', {clickmap: false, trackLinks: true, accurateTrackBounce: true, webvisor: false});
        window.dataLayer = window.dataLayer || [];
        window.gtag = function () { window.dataLayer.push(arguments); };
        window.gtag('js', new Date());
        window.gtag('config', 'G-HM2E5L88J7', {allow_google_signals: false, allow_ad_personalization_signals: false});
        const google = document.createElement('script');
        google.src = 'https://www.googletagmanager.com/gtag/js?id=G-HM2E5L88J7'; google.async = true;
        document.head.append(google);
    };
    let choice = null;
    try { choice = localStorage.getItem(key); } catch { /* A blocked store must not break the form. */ }
    if (choice === 'allow') loadAnalytics();
    notice.hidden = choice === 'allow' || choice === 'deny';
    const choose = value => {
        try { localStorage.setItem(key, value); } catch { /* Choice applies for this page. */ }
        notice.hidden = true;
        if (value === 'allow') loadAnalytics();
        if (value === 'deny' && loaded) {
            window['ga-disable-G-HM2E5L88J7'] = true;
            window.ym?.(103286938, 'destruct');
            // Reload removes the previously loaded tracker scripts; consent is now denied.
            window.location.reload();
        }
    };
    document.getElementById('analyticsAccept').addEventListener('click', () => choose('allow'));
    document.getElementById('analyticsDecline').addEventListener('click', () => choose('deny'));
    document.getElementById('analyticsSettings').addEventListener('click', () => {
        notice.hidden = false;
        document.getElementById('analyticsDecline').focus();
    });
});
