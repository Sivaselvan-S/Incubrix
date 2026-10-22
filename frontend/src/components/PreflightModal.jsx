import React, { useState } from 'react';

const PRESETS = [
  {
    name: 'Clean Tech Post (PASS)',
    title: 'Distributed Systems & Long-Tail Idempotency in 2026',
    body: 'Exploring how verifiable passports prevent content duplication across federated networks.\n\n### Key Takeaways\n- Deterministic preflight gates\n- Instant hash reservation\n- Zero duplicates guaranteed.',
    tags: 'distributed, architecture, passports, webdev',
    canonical_url: 'https://longtail.engineering/passports-guide',
    is_promotional: false,
  },
  {
    name: 'Excessive Tags (REWRITE)',
    title: 'Building Real-time Canaries for Upstream APIs',
    body: 'Automated drift detection alerts before breaking downstream clients.\n\nCheck out the continuous canary harness specification.',
    tags: 'api, microservices, cloud, monitoring, devops, react, python, devto',
    canonical_url: '',
    is_promotional: false,
  },
  {
    name: 'Restricted Spam Keyword (BLOCK)',
    title: 'Guaranteed 1000x Returns with Free Crypto Airdrop Tokens!',
    body: 'Sign up now for our exclusive telegram airdrop pump! Instant profit guaranteed with zero risk.\n\nClick here for token claims.',
    tags: 'crypto, airdrop, pump, money',
    canonical_url: 'https://scam-airdrop.example.com',
    is_promotional: true,
  },
  {
    name: 'Title Overlength Limit (REWRITE/BLOCK)',
    title: 'A'.repeat(160),
    body: 'A very short body with an abnormally oversized title exceeding destination constraint limits.',
    tags: 'testing, edgecase',
    canonical_url: '',
    is_promotional: false,
  },
];

export default function PreflightModal({
  isOpen,
  onClose,
  destinations = [],
  initialDestId = '',
}) {
  if (!isOpen) return null;

  const defaultDest = initialDestId || (destinations[0]?.id || 'dest_devto');
  const [destId, setDestId] = useState(defaultDest);
  const [title, setTitle] = useState(PRESETS[0].title);
  const [body, setBody] = useState(PRESETS[0].body);
  const [tags, setTags] = useState(PRESETS[0].tags);
  const [canonicalUrl, setCanonicalUrl] = useState(PRESETS[0].canonical_url);
  const [isPromotional, setIsPromotional] = useState(false);
  const [loading, setLoading] = useState(false);
  const [verdict, setVerdict] = useState(null);
  const [error, setError] = useState(null);

  const applyPreset = (p) => {
    setTitle(p.title);
    setBody(p.body);
    setTags(p.tags);
    setCanonicalUrl(p.canonical_url);
    setIsPromotional(p.is_promotional);
    setVerdict(null);
    setError(null);
  };

  const handleEvaluate = async (e) => {
    e?.preventDefault();
    setLoading(true);
    setError(null);

    const tagArray = tags
      .split(',')
      .map((t) => t.trim())
      .filter(Boolean);

    const payload = {
      destination_id: destId,
      rendition: {
        title,
        body_markdown: body,
        tags: tagArray,
        canonical_url: canonicalUrl.trim() || null,
        language: 'en',
        is_promotional: isPromotional,
      },
    };

    try {
      const res = await fetch('/api/v1/preflight', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      if (!res.ok) {
        const errJson = await res.json().catch(() => ({}));
        throw new Error(errJson?.detail?.error?.message || errJson?.detail || `Preflight returned HTTP ${res.status}`);
      }

      const data = await res.json();
      setVerdict(data);
    } catch (err) {
      setError(err.message || 'Failed to evaluate preflight request');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="liquid-modal-backdrop" onClick={onClose}>
      <div
        className="liquid-modal"
        style={{ width: 'calc(860 * var(--u))' }}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="liquid-modal-header">
          <div>
            <h2 className="liquid-modal-title">Preflight Court Gatekeeper</h2>
            <p style={{ fontSize: 'calc(12 * var(--u))', opacity: 0.8, marginTop: 'calc(4 * var(--u))' }}>
              Pure, deterministic rule evaluation against destination passport constraints before publication.
            </p>
          </div>
          <button className="liquid-modal-close" onClick={onClose} aria-label="Close">
            ✕
          </button>
        </div>

        {/* Preset Strip */}
        <div className="preset-strip">
          <span style={{ fontSize: 'calc(11 * var(--u))', opacity: 0.7, alignSelf: 'center', marginRight: 'calc(6 * var(--u))' }}>
            Presets:
          </span>
          {PRESETS.map((p, idx) => (
            <button
              key={idx}
              className="preset-chip"
              onClick={() => applyPreset(p)}
              type="button"
            >
              {p.name}
            </button>
          ))}
        </div>

        <form onSubmit={handleEvaluate}>
          <div className="modal-grid-2">
            <div>
              <div className="form-field">
                <label className="form-label">Destination Passport</label>
                <select
                  className="glass-select"
                  value={destId}
                  onChange={(e) => setDestId(e.target.value)}
                >
                  {destinations.length > 0 ? (
                    destinations.map((d) => (
                      <option key={d.id} value={d.id} style={{ background: '#0a1d29', color: '#fff' }}>
                        {d.name} ({d.platform_key} · {d.level || 'L4'})
                      </option>
                    ))
                  ) : (
                    <>
                      <option value="dest_devto" style={{ background: '#0a1d29', color: '#fff' }}>
                        Dev.to Community (L4 · 98% Health)
                      </option>
                      <option value="dest_discourse" style={{ background: '#0a1d29', color: '#fff' }}>
                        Discourse Forum (L4 · 99% Health)
                      </option>
                      <option value="dest_ghost" style={{ background: '#0a1d29', color: '#fff' }}>
                        Ghost Publication (L3 · 95% Health)
                      </option>
                    </>
                  )}
                </select>
              </div>

              <div className="form-field">
                <label className="form-label">Article / Post Title</label>
                <input
                  type="text"
                  className="glass-input"
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  placeholder="Enter publication title..."
                  required
                />
              </div>

              <div className="form-field">
                <label className="form-label">Tags (comma-separated)</label>
                <input
                  type="text"
                  className="glass-input"
                  value={tags}
                  onChange={(e) => setTags(e.target.value)}
                  placeholder="e.g. devops, architecture, python"
                />
              </div>

              <div className="form-field">
                <label className="form-label">Canonical URL</label>
                <input
                  type="url"
                  className="glass-input"
                  value={canonicalUrl}
                  onChange={(e) => setCanonicalUrl(e.target.value)}
                  placeholder="https://..."
                />
              </div>

              <div className="form-field" style={{ display: 'flex', alignItems: 'center', gap: 'calc(8 * var(--u))' }}>
                <input
                  type="checkbox"
                  id="promo-check"
                  checked={isPromotional}
                  onChange={(e) => setIsPromotional(e.target.checked)}
                  style={{ accentColor: '#06b6d4', width: 'calc(16 * var(--u))', height: 'calc(16 * var(--u))' }}
                />
                <label htmlFor="promo-check" style={{ fontSize: 'calc(12 * var(--u))', cursor: 'pointer' }}>
                  Contains Promotional / Commercial Content
                </label>
              </div>
            </div>

            <div>
              <div className="form-field">
                <label className="form-label">Body Markdown</label>
                <textarea
                  className="glass-textarea"
                  style={{ height: 'calc(230 * var(--u))', resize: 'vertical' }}
                  value={body}
                  onChange={(e) => setBody(e.target.value)}
                  placeholder="Write body content in Markdown..."
                  required
                />
              </div>
            </div>
          </div>

          <div style={{ display: 'flex', gap: 'calc(12 * var(--u))', marginTop: 'calc(12 * var(--u))' }}>
            <button
              type="submit"
              className="glass-btn-primary"
              disabled={loading}
              style={{ flex: 1 }}
            >
              <svg style={{ width: 'calc(18 * var(--u))', height: 'calc(18 * var(--u))', fill: '#ffffff' }}>
                <use href="#i-scale" />
              </svg>
              {loading ? 'Evaluating Court Rules...' : 'Submit to Preflight Court'}
            </button>
          </div>
        </form>

        {/* Error notification */}
        {error && (
          <div
            style={{
              marginTop: 'calc(16 * var(--u))',
              padding: 'calc(12 * var(--u))',
              background: 'rgba(244, 63, 94, 0.25)',
              border: '1px solid rgba(244, 63, 94, 0.5)',
              borderRadius: 'calc(10 * var(--u))',
              fontSize: 'calc(13 * var(--u))',
              color: '#fecdd3',
            }}
          >
            <strong>Error:</strong> {error}
          </div>
        )}

        {/* Verdict Results Display */}
        {verdict && (
          <div style={{ marginTop: 'calc(20 * var(--u))' }}>
            <div
              className={`verdict-banner ${
                verdict.action === 'ALLOW'
                  ? 'allow'
                  : verdict.action === 'REWRITE'
                  ? 'rewrite'
                  : 'block'
              }`}
            >
              <div>
                <span style={{ fontSize: 'calc(11 * var(--u))', textTransform: 'uppercase', opacity: 0.8 }}>
                  Court Verdict
                </span>
                <div style={{ fontSize: 'calc(22 * var(--u))', fontWeight: 800, letterSpacing: '0.04em' }}>
                  {verdict.action === 'ALLOW' && 'ALLOW — Passed All Checks'}
                  {verdict.action === 'REWRITE' && 'REWRITE — Sanitized Auto-Fixes Applied'}
                  {verdict.action === 'BLOCK' && 'BLOCK — Publication Rejected'}
                </div>
              </div>
              <span
                className={`badge ${
                  verdict.action === 'ALLOW'
                    ? 'badge-allow'
                    : verdict.action === 'REWRITE'
                    ? 'badge-rewrite'
                    : 'badge-block'
                }`}
                style={{ fontSize: 'calc(13 * var(--u))', padding: 'calc(6 * var(--u)) calc(14 * var(--u))' }}
              >
                {verdict.action}
              </span>
            </div>

            {/* Violations Details */}
            {verdict.violations && verdict.violations.length > 0 && (
              <div style={{ marginTop: 'calc(14 * var(--u))' }}>
                <div className="form-label">
                  Violations Caught ({verdict.violations.length})
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 'calc(8 * var(--u))' }}>
                  {verdict.violations.map((v, i) => (
                    <div
                      key={i}
                      style={{
                        background: 'rgba(0, 0, 0, 0.3)',
                        border: '1px solid rgba(255, 255, 255, 0.15)',
                        borderRadius: 'calc(8 * var(--u))',
                        padding: 'calc(8 * var(--u)) calc(12 * var(--u))',
                        fontSize: 'calc(12 * var(--u))',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                      }}
                    >
                      <div>
                        <strong style={{ color: '#fb7185', marginRight: 'calc(8 * var(--u))' }}>
                          [{v.code}]
                        </strong>
                        <span>{v.message}</span>
                      </div>
                      <span
                        className={`badge ${
                          v.severity === 'FATAL' || v.severity === 'ERROR'
                            ? 'badge-block'
                            : 'badge-rewrite'
                        }`}
                      >
                        {v.severity || 'RULE'}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Sanitized Rendition Preview if REWRITE */}
            {verdict.action === 'REWRITE' && verdict.rewritten_rendition && (
              <div style={{ marginTop: 'calc(14 * var(--u))' }}>
                <div className="form-label">Rewritten / Sanitized Result</div>
                <div className="diff-box">
                  <strong>Title:</strong> {verdict.rewritten_rendition.title}
                  {'\n'}
                  <strong>Tags:</strong> {(verdict.rewritten_rendition.tags || []).join(', ')}
                  {'\n'}
                  <strong>Canonical:</strong> {verdict.rewritten_rendition.canonical_url || 'N/A'}
                  {'\n\n'}
                  <strong>Body Snippet:</strong>
                  {'\n'}
                  {verdict.rewritten_rendition.body_markdown}
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
