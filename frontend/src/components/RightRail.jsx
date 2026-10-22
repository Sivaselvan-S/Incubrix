import React from 'react';

export default function RightRail({
  activeDestination,
  onOpenCourt,
  onOpenPublish,
  onOpenChaos,
  onOpenPassports,
}) {
  const destName = activeDestination?.name || 'Dev.to Community';
  const destLevel = activeDestination?.level || 'L4';
  const healthScore = activeDestination?.passport?.health_score || 98;

  return (
    <aside className="rail">
      {/* Card A: Big Liquid Glass Spotlight Card */}
      <div
        className="glass-card big"
        onClick={onOpenPassports}
        title="View Living Destination Passport"
      >
        <div>
          <div className="card-place">
            <svg>
              <use href="#i-node" />
            </svg>
            <span>{destName}</span>
          </div>

          <div className="big-rating">
            {destLevel}
            <i>{healthScore}%</i>
          </div>
        </div>

        <div className="card-metrics">
          <div className="sub-metric">
            <svg>
              <use href="#i-eye" />
            </svg>
            <span>19.4k views</span>
          </div>
          <div className="sub-metric">
            <svg>
              <use href="#i-heart" />
            </svg>
            <span>429 likes</span>
          </div>
          <div className="sub-metric">
            <svg>
              <use href="#i-comment" />
            </svg>
            <span>15 cmts</span>
          </div>
        </div>
      </div>

      {/* Card B: Preflight Court Row Card */}
      <div
        className="glass-card row"
        onClick={onOpenCourt}
        title="Open Preflight Court Simulator"
      >
        <div>
          <div className="row-left-title">Preflight Gatekeeper</div>
          <div className="row-left-name">Court Verdict: PASS</div>
          <div className="row-left-sub">0 Rule Violations Caught</div>
        </div>
        <div className="row-right">
          <div className="row-right-val">100%</div>
          <svg>
            <use href="#i-scale" />
          </svg>
        </div>
      </div>

      {/* Card C: Idempotency Ledger Row Card */}
      <div
        className="glass-card row"
        onClick={onOpenPublish}
        title="Open Idempotency & Publishing Console"
      >
        <div>
          <div className="row-left-title">Idempotency Ledger</div>
          <div className="row-left-name">Safe Retry Protection</div>
          <div className="row-left-sub">Zero Duplicate Posts</div>
        </div>
        <div className="row-right">
          <div className="row-right-val">0 dup</div>
          <svg>
            <use href="#i-key" />
          </svg>
        </div>
      </div>

      {/* Card D: Drift Canary Row Card */}
      <div
        className="glass-card row"
        onClick={onOpenChaos}
        title="Test Drift Canary & Upstream Chaos"
      >
        <div>
          <div className="row-left-title">Drift Canary</div>
          <div className="row-left-name">Dev.to Pinned Schema</div>
          <div className="row-left-sub">Fingerprint: 100% Valid</div>
        </div>
        <div className="row-right">
          <div className="row-right-val">Active</div>
          <svg>
            <use href="#i-zap" />
          </svg>
        </div>
      </div>
    </aside>
  );
}
