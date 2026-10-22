import React from 'react';

export default function SvgSprite() {
  return (
    <svg style={{ display: 'none' }} aria-hidden="true">
      <defs>
        {/* Wave-Circle Logo Mark */}
        <symbol id="logo-mark" viewBox="0 0 40 40">
          <rect width="40" height="40" rx="12" fill="none" stroke="rgba(255,255,255,0.4)" strokeWidth="1.5" />
          <clipPath id="logo-clip">
            <rect width="40" height="40" rx="12" />
          </clipPath>
          <g clipPath="url(#logo-clip)" fill="none" stroke="#ffffff" strokeWidth="1.8" strokeLinecap="round">
            <path d="M-5 10 Q 5 6, 15 10 T 35 10 T 55 10" opacity="0.4" />
            <path d="M-5 15 Q 5 11, 15 15 T 35 15 T 55 15" opacity="0.6" />
            <path d="M-5 20 Q 5 16, 15 20 T 35 20 T 55 20" opacity="0.9" />
            <path d="M-5 25 Q 5 21, 15 25 T 35 25 T 55 25" opacity="1" />
            <path d="M-5 30 Q 5 26, 15 30 T 35 30 T 55 30" opacity="0.7" />
          </g>
        </symbol>

        {/* Dashboard Grid */}
        <symbol id="i-grid" viewBox="0 0 24 24">
          <path d="M3 3h7v7H3V3zm11 0h7v7h-7V3zm-11 11h7v7H3v-7zm11 0h7v7h-7v-7z" fill="currentColor"/>
        </symbol>

        {/* Chart */}
        <symbol id="i-chart" viewBox="0 0 24 24">
          <path d="M4 19h16v2H2V3h2v16zm4-7h3v5H8v-5zm5-4h3v9h-3V8zm5-4h3v13h-3V4z" fill="currentColor"/>
        </symbol>

        {/* Globe / Destinations */}
        <symbol id="i-globe" viewBox="0 0 24 24">
          <circle cx="12" cy="12" r="9" fill="none" stroke="currentColor" strokeWidth="2"/>
          <path d="M3.6 9h16.8M3.6 15h16.8M12 3a15.3 15.3 0 0 1 4 9 15.3 15.3 0 0 1-4 9 15.3 15.3 0 0 1-4-9 15.3 15.3 0 0 1 4-9z" fill="none" stroke="currentColor" strokeWidth="1.8"/>
        </symbol>

        {/* Calendar / Recertification */}
        <symbol id="i-cal" viewBox="0 0 24 24">
          <path d="M19 4h-1V2h-2v2H8V2H6v2H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V6c0-1.1-.9-2-2-2zm0 16H5V10h14v10zm0-12H5V6h14v2z" fill="currentColor"/>
        </symbol>

        {/* Gear / Settings */}
        <symbol id="i-gear" viewBox="0 0 24 24">
          <path d="M19.14 12.94c.04-.3.06-.61.06-.94 0-.32-.02-.64-.07-.94l2.03-1.58a.49.49 0 0 0 .12-.61l-1.92-3.32a.49.49 0 0 0-.59-.22l-2.39.96c-.5-.38-1.03-.7-1.62-.94l-.36-2.54A.484.484 0 0 0 14 2h-4c-.25 0-.46.18-.49.42l-.36 2.54c-.59.24-1.13.57-1.62.94l-2.39-.96c-.22-.08-.47 0-.59.22L2.63 8.5c-.12.21-.08.47.12.61l2.03 1.58c-.05.3-.09.63-.09.94s.02.64.07.94l-2.03 1.58a.49.49 0 0 0-.12.61l1.92 3.32c.12.22.37.29.59.22l2.39-.96c.5.38 1.03.7 1.62.94l.36 2.54c.05.24.24.41.48.41h4c.25 0 .46-.18.49-.42l.36-2.54c.59-.24 1.13-.56 1.62-.94l2.39.96c.22.08.47 0 .59-.22l1.92-3.32c.12-.22.07-.47-.12-.61l-2.01-1.58zM12 15.6c-1.98 0-3.6-1.62-3.6-3.6s1.62-3.6 3.6-3.6 3.6 1.62 3.6 3.6-1.62 3.6-3.6 3.6z" fill="currentColor"/>
        </symbol>

        {/* Exit / Sign Out */}
        <symbol id="i-out" viewBox="0 0 24 24">
          <path d="M10.09 15.59L11.5 17l5-5-5-5-1.41 1.41L12.67 11H3v2h9.67l-2.58 2.59zM19 3H5c-1.11 0-2 .9-2 2v4h2V5h14v14H5v-4H3v4c0 1.1.89 2 2 2h14c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2z" fill="currentColor"/>
        </symbol>

        {/* Plus / Create */}
        <symbol id="i-plus" viewBox="0 0 24 24">
          <path d="M19 13h-6v6h-2v-6H5v-2h6V5h2v6h6v2z" fill="currentColor"/>
        </symbol>

        {/* Search */}
        <symbol id="i-search" viewBox="0 0 24 24">
          <path d="M15.5 14h-.79l-.28-.27A6.471 6.471 0 0 0 16 9.5 6.5 6.5 0 1 0 9.5 16c1.61 0 3.09-.59 4.23-1.57l.27.28v.79l5 4.99L20.49 19l-4.99-5zm-6 0C7.01 14 5 11.99 5 9.5S7.01 5 9.5 5 14 7.01 14 9.5 11.99 14 9.5 14z" fill="currentColor"/>
        </symbol>

        {/* Notifications Bell */}
        <symbol id="i-bell" viewBox="0 0 24 24">
          <path d="M12 22c1.1 0 2-.9 2-2h-4a2 2 0 0 0 2 2zm6-6v-5c0-3.07-1.64-5.64-4.5-6.32V4c0-.83-.67-1.5-1.5-1.5s-1.5.67-1.5 1.5v.68C7.63 5.36 6 7.92 6 11v5l-2 2v1h16v-1l-2-2z" fill="currentColor"/>
        </symbol>

        {/* Pin */}
        <symbol id="i-pin" viewBox="0 0 24 24">
          <path d="M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7zm0 9.5c-1.38 0-2.5-1.12-2.5-2.5s1.12-2.5 2.5-2.5 2.5 1.12 2.5 2.5-1.12 2.5-2.5 2.5z" fill="currentColor"/>
        </symbol>

        {/* Wind / Throughput */}
        <symbol id="i-wind" viewBox="0 0 24 24">
          <path d="M14.5 17c0 1.65-1.35 3-3 3s-3-1.35-3-3h2c0 .55.45 1 1 1s1-.45 1-1-.45-1-1-1H2v-2h9.5c1.65 0 3 1.35 3 3zm4.5-9c0 1.65-1.35 3-3 3H2v-2h14c.55 0 1-.45 1-1s-.45-1-1-1-1 .45-1 1h-2c0-1.65 1.35-3 3-3s3 1.35 3 3zm3 4c0 1.65-1.35 3-3 3H2v-2h17c.55 0 1-.45 1-1s-.45-1-1-1-1 .45-1 1h-2c0-1.65 1.35-3 3-3s3 1.35 3 3z" fill="currentColor"/>
        </symbol>

        {/* Drop / Health */}
        <symbol id="i-drop" viewBox="0 0 24 24">
          <path d="M12 2.69l5.66 5.66a8 8 0 1 1-11.31 0z" fill="currentColor"/>
        </symbol>

        {/* Gust / Clicks */}
        <symbol id="i-gust" viewBox="0 0 24 24">
          <path d="M3 8h10a3 3 0 1 0-3-3h2a1 1 0 1 1 1 1H3v2zm0 8h14a3 3 0 1 0-3-3h2a1 1 0 1 1 1 1H3v2zm0-4h18v2H3v-2z" fill="currentColor"/>
        </symbol>

        {/* Shield / Passport */}
        <symbol id="i-shield" viewBox="0 0 24 24">
          <path d="M12 1L3 5v6c0 5.55 3.84 10.74 9 12 5.16-1.26 9-6.45 9-12V5l-9-4zm-2 16l-4-4 1.41-1.41L10 14.17l6.59-6.59L18 9l-8 8z" fill="currentColor"/>
        </symbol>

        {/* Lightning / Chaos */}
        <symbol id="i-zap" viewBox="0 0 24 24">
          <path d="M7 2v11h3v9l7-12h-4l4-8z" fill="currentColor"/>
        </symbol>

        {/* Scale / Preflight Court */}
        <symbol id="i-scale" viewBox="0 0 24 24">
          <path d="M12 3v2m0 0a4 4 0 0 0-4 4v1H5l3 7h6l3-7h-3V9a4 4 0 0 0-4-4zm-7 8l-2 5h6l-2-5h-2zm12 0l-2 5h6l-2-5h-2zm-5 8v2" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
        </symbol>

        {/* Key / Idempotency */}
        <symbol id="i-key" viewBox="0 0 24 24">
          <path d="M7 14A5 5 0 1 1 12 9c0 .4-.05.79-.14 1.16L16 14v2h2v2h2v-2h2v-2l-5.16-5.16A5 5 0 0 1 7 14zm0-2a3 3 0 1 0 0-6 3 3 0 0 0 0 6z" fill="currentColor"/>
        </symbol>

        {/* Vector Avatar Fallback */}
        <symbol id="i-avatar" viewBox="0 0 24 24">
          <path d="M12 12c2.21 0 4-1.79 4-4s-1.79-4-4-4-4 1.79-4 4 1.79 4 4 4zm0 2c-2.67 0-8 1.34-8 4v2h16v-2c0-2.66-5.33-4-8-4z" fill="currentColor"/>
        </symbol>
      </defs>
    </svg>
  );
}
