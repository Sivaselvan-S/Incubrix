import React from 'react';

export default function Header({
  apiStatus,
  onOpenPublish,
  onOpenChaos,
  onOpenPassports,
}) {
  return (
    <header className="header">
      {/* Left: Welcome & Operator Identity */}
      <div className="header-left">
        <span className="header-welcome">Welcome</span>
        <h2 className="header-title">Calfin Danang</h2>
      </div>

      {/* Right Tools & Avatar */}
      <div className="header-tools">
        {/* Tool 1: + New Publication */}
        <button
          className="tool-btn"
          aria-label="New Publication"
          title="New Publication Dispatch"
          onClick={onOpenPublish}
        >
          <svg>
            <use href="#i-plus" />
          </svg>
        </button>

        {/* Tool 2: Search & Passport Explorer */}
        <button
          className="tool-btn"
          aria-label="Search Destinations"
          title="Explore Destinations & Passports"
          onClick={onOpenPassports}
        >
          <svg>
            <use href="#i-search" />
          </svg>
        </button>

        {/* Tool 3: Chaos Drift Alert Trigger */}
        <button
          className="tool-btn"
          aria-label="Drift Canary Alerts"
          title="Drift Canary & Chaos Testing"
          onClick={onOpenChaos}
        >
          <svg>
            <use href="#i-bell" />
          </svg>
        </button>

        {/* Avatar with remote Unsplash photo & SVG fallback */}
        <div
          className="header-avatar"
          title={`Operator Profile - API ${apiStatus}`}
          onClick={onOpenPassports}
        >
          <img
            src="https://images.unsplash.com/photo-1500648767791-00dcc994a43e?w=160&h=160&fit=crop&crop=faces&q=80&auto=format"
            alt="Calfin Danang"
            loading="eager"
            decoding="async"
            onError={(e) => {
              e.currentTarget.style.display = 'none';
              const parent = e.currentTarget.parentElement;
              if (parent && !parent.querySelector('svg')) {
                const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
                svg.style.width = '100%';
                svg.style.height = '100%';
                svg.style.fill = '#ffffff';
                const use = document.createElementNS('http://www.w3.org/2000/svg', 'use');
                use.setAttributeNS('http://www.w3.org/1999/xlink', 'href', '#i-avatar');
                svg.appendChild(use);
                parent.appendChild(svg);
              }
            }}
          />
        </div>
      </div>
    </header>
  );
}
