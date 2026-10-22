import React from 'react';

const NAV_ITEMS = [
  { id: 'dashboard', label: 'Dashboard', icon: '#i-grid', pipY: 131 },
  { id: 'passports', label: 'Passports Registry', icon: '#i-shield', pipY: 197 },
  { id: 'court', label: 'Preflight Court', icon: '#i-scale', pipY: 263 },
  { id: 'publish', label: 'Publish & Idempotency', icon: '#i-plus', pipY: 329 },
  { id: 'chaos', label: 'Drift Canary & Chaos', icon: '#i-zap', pipY: 395 },
  { id: 'recommender', label: 'Recommender Engine', icon: '#i-chart', pipY: 461 },
];

export default function Sidebar({ activeTab, onSelectTab }) {
  const currentItem = NAV_ITEMS.find(item => item.id === activeTab) || NAV_ITEMS[0];

  return (
    <aside className="sidebar">
      {/* Active White Pip */}
      <div
        className="sidebar-pip"
        style={{ '--pip-y': currentItem.pipY }}
        aria-hidden="true"
      />

      {/* Wave-Circle Logo */}
      <div className="logo-wrap" onClick={() => onSelectTab('dashboard')} title="LongTail Passport Flight Deck">
        <svg>
          <use href="#logo-mark" />
        </svg>
      </div>

      {/* Navigation Icons */}
      <nav className="sidebar-nav" aria-label="Main Navigation">
        {NAV_ITEMS.map((item) => {
          const isActive = activeTab === item.id;
          return (
            <button
              key={item.id}
              className={`nav-link ${isActive ? 'active' : ''}`}
              aria-label={item.label}
              aria-current={isActive ? 'page' : undefined}
              onClick={() => onSelectTab(item.id)}
              title={item.label}
            >
              <svg>
                <use href={item.icon} />
              </svg>
            </button>
          );
        })}
      </nav>

      {/* Sign Out at Bottom */}
      <button
        className="sidebar-logout"
        aria-label="Sign out"
        onClick={() => alert('Flight Deck session locked')}
        title="Sign out"
      >
        <svg>
          <use href="#i-out" />
        </svg>
      </button>
    </aside>
  );
}
