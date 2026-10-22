import React from 'react';

const METRICS = [
  { val: '6', label: 'L4 Certified', icon: '#i-shield' },
  { val: '98%', label: 'Health Score', icon: '#i-pulse' },
  { val: '0', label: 'Violations Missed', icon: '#i-scale' },
  { val: '0', label: 'Duplicates Replayed', icon: '#i-key' },
  { val: '9', label: 'Active Connectors', icon: '#i-globe' },
  { val: '1.8s', label: '1,000 Ingest', icon: '#i-speed' },
];

const PLATFORMS = [
  { id: 'discourse', name: 'Discourse' },
  { id: 'devto', name: 'Dev.to' },
  { id: 'ghost', name: 'Ghost' },
  { id: 'lemmy', name: 'Lemmy' },
  { id: 'slack', name: 'Slack' },
  { id: 'hashnode', name: 'Hashnode' },
  { id: 'mrss', name: 'MRSS Feed' },
];

export default function TelemetryWave({ activePlatform, onSelectPlatform }) {
  // Exact cubic wave path
  const wavePath = "M 0,79 C 140,40 220,160 360,95 C 480,45 560,140 700,75 L 835,86";
  const fillPath = `${wavePath} L 835,230 L 0,230 Z`;

  return (
    <section className="forecast">
      {/* 1. Top Metrics Row */}
      <div className="metrics-row">
        {METRICS.map((m, idx) => (
          <div key={idx} className="metric-item">
            <div>
              <div className="metric-value">{m.val}</div>
              <div className="metric-label">{m.label}</div>
            </div>
            <svg className="metric-icon">
              <use href={m.icon} />
            </svg>
          </div>
        ))}
      </div>

      {/* 2. SVG Wave Chart with drawLine & wipeX animation */}
      <div className="chart-wrap">
        <svg
          className="wave-svg"
          viewBox="0 0 835 230"
          preserveAspectRatio="none"
          aria-hidden="true"
        >
          <defs>
            {/* Horizontal white opacity gradient */}
            <linearGradient id="wg" x1="0" y1="0" x2="1" y2="0">
              <stop offset="0%" stopColor="#ffffff" stopOpacity="0.4" />
              <stop offset="35%" stopColor="#ffffff" stopOpacity="0.85" />
              <stop offset="70%" stopColor="#ffffff" stopOpacity="1" />
              <stop offset="100%" stopColor="#ffffff" stopOpacity="0.5" />
            </linearGradient>

            {/* Vertical fill fade gradient */}
            <linearGradient id="wf" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#ffffff" stopOpacity="0.28" />
              <stop offset="60%" stopColor="#ffffff" stopOpacity="0.08" />
              <stop offset="100%" stopColor="#ffffff" stopOpacity="0.00" />
            </linearGradient>

            {/* Clip path for wipe-in fill following the pen */}
            <clipPath id="wclip">
              <rect id="wclipr" x="0" y="0" width="835" height="230" />
            </clipPath>
          </defs>

          {/* Fill path clipped by animated rect */}
          <path d={fillPath} fill="url(#wf)" clipPath="url(#wclip)" />

          {/* 3 Stroked outline paths */}
          <path
            className="wline"
            d={wavePath}
            fill="none"
            stroke="url(#wg)"
            strokeWidth="6.2"
            opacity="0.17"
            pathLength="1"
            strokeDasharray="1"
          />
          <path
            className="wline"
            d={wavePath}
            fill="none"
            stroke="url(#wg)"
            strokeWidth="4.6"
            opacity="0.26"
            pathLength="1"
            strokeDasharray="1"
          />
          <path
            className="wline"
            d={wavePath}
            fill="none"
            stroke="url(#wg)"
            strokeWidth="3.4"
            opacity="1.0"
            pathLength="1"
            strokeDasharray="1"
          />
        </svg>
      </div>

      {/* 3. Platform Selectors Row under chart */}
      <div className="platforms-row">
        {PLATFORMS.map((p) => {
          const isOn = activePlatform === p.id;
          return (
            <button
              key={p.id}
              className={`platform-btn ${isOn ? 'on' : ''}`}
              onClick={() => onSelectPlatform(p.id)}
            >
              {p.name}
            </button>
          );
        })}
      </div>
    </section>
  );
}
