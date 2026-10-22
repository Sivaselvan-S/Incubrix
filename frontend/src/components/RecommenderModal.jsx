import React, { useState } from 'react';

export default function RecommenderModal({
  isOpen,
  onClose,
  onSelectDestForCourt,
}) {
  if (!isOpen) return null;

  const [title, setTitle] = useState('Scaling Async Task Queues with SQLite and Python 3.12');
  const [body, setBody] = useState(
    'A deep dive into zero-dependency queue architectures, worker heartbeats, and transactional idempotency.'
  );
  const [category, setCategory] = useState('technology');
  const [tags, setTags] = useState('python, devops, database, backend');
  const [isPromotional, setIsPromotional] = useState(false);
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState(null);
  const [error, setError] = useState(null);

  const handleRecommend = async (e) => {
    e?.preventDefault();
    setLoading(true);
    setError(null);

    const tagList = tags
      .split(',')
      .map((t) => t.trim())
      .filter(Boolean);

    try {
      const res = await fetch('/api/v1/recommendations', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          title,
          body,
          category,
          tags: tagList,
          language: 'en',
          is_promotional: isPromotional,
          limit: 6,
        }),
      });

      if (!res.ok) {
        throw new Error(`HTTP ${res.status}`);
      }

      const data = await res.json();
      setResults(data.recommendations || []);
    } catch (err) {
      setError(err.message || 'Failed to generate recommendations');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="liquid-modal-backdrop" onClick={onClose}>
      <div
        className="liquid-modal"
        style={{ width: 'calc(820 * var(--u))', maxHeight: '88vh' }}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="liquid-modal-header">
          <div>
            <h2 className="liquid-modal-title">AI Destination Recommender</h2>
            <p style={{ fontSize: 'calc(12 * var(--u))', opacity: 0.8, marginTop: 'calc(4 * var(--u))' }}>
              Multi-criteria ranking engine matching content semantics, audience fit, and destination policies.
            </p>
          </div>
          <button className="liquid-modal-close" onClick={onClose} aria-label="Close">
            ✕
          </button>
        </div>

        <form onSubmit={handleRecommend}>
          <div className="modal-grid-2">
            <div>
              <div className="form-field">
                <label className="form-label">Article Title</label>
                <input
                  type="text"
                  className="glass-input"
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  required
                />
              </div>

              <div className="form-field">
                <label className="form-label">Topic Category</label>
                <select
                  className="glass-select"
                  value={category}
                  onChange={(e) => setCategory(e.target.value)}
                >
                  <option value="technology" style={{ background: '#0a1d29', color: '#fff' }}>
                    Technology & Software
                  </option>
                  <option value="data-science" style={{ background: '#0a1d29', color: '#fff' }}>
                    Data Science & AI
                  </option>
                  <option value="business" style={{ background: '#0a1d29', color: '#fff' }}>
                    Business & Leadership
                  </option>
                  <option value="general" style={{ background: '#0a1d29', color: '#fff' }}>
                    General Discussion
                  </option>
                </select>
              </div>

              <div className="form-field">
                <label className="form-label">Tags</label>
                <input
                  type="text"
                  className="glass-input"
                  value={tags}
                  onChange={(e) => setTags(e.target.value)}
                />
              </div>
            </div>

            <div>
              <div className="form-field">
                <label className="form-label">Body Content Excerpt</label>
                <textarea
                  className="glass-textarea"
                  style={{ height: 'calc(170 * var(--u))' }}
                  value={body}
                  onChange={(e) => setBody(e.target.value)}
                  required
                />
              </div>
            </div>
          </div>

          <button
            type="submit"
            className="glass-btn-primary"
            disabled={loading}
            style={{ width: '100%', marginTop: 'calc(8 * var(--u))' }}
          >
            <svg style={{ width: 'calc(18 * var(--u))', height: 'calc(18 * var(--u))', fill: '#ffffff' }}>
              <use href="#i-chart" />
            </svg>
            {loading ? 'Ranking Destination Matches...' : 'Find Best Matching Passports'}
          </button>
        </form>

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

        {/* Results Stream */}
        {results && (
          <div style={{ marginTop: 'calc(20 * var(--u))' }}>
            <div className="form-label">Ranked Destinations ({results.length})</div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 'calc(8 * var(--u))' }}>
              {results.length === 0 ? (
                <div style={{ opacity: 0.6, fontSize: 'calc(12 * var(--u))' }}>
                  No matching destinations returned for this topic criteria.
                </div>
              ) : (
                results.map((r, i) => (
                  <div
                    key={r.destination_id || i}
                    style={{
                      background: 'rgba(0, 0, 0, 0.3)',
                      border: '1px solid rgba(255, 255, 255, 0.15)',
                      borderRadius: 'calc(10 * var(--u))',
                      padding: 'calc(10 * var(--u)) calc(14 * var(--u))',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                    }}
                  >
                    <div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 'calc(8 * var(--u))' }}>
                        <span style={{ fontWeight: 700 }}>{r.name || r.destination_name}</span>
                        <span className="badge badge-l4">{r.platform_key}</span>
                        <span style={{ fontSize: 'calc(11 * var(--u))', color: '#34d399', fontWeight: 600 }}>
                          {Math.round((r.score || r.relevance_score || 0.95) * 100)}% Match
                        </span>
                      </div>
                      <div style={{ fontSize: 'calc(11 * var(--u))', opacity: 0.75, marginTop: 'calc(2 * var(--u))' }}>
                        {r.reason || r.relevance_reason || 'Audience tags and policy guidelines align perfectly.'}
                      </div>
                    </div>

                    <button
                      className="glass-btn-secondary"
                      style={{ padding: 'calc(6 * var(--u)) calc(12 * var(--u))', fontSize: 'calc(11 * var(--u))' }}
                      onClick={() => {
                        onClose();
                        if (onSelectDestForCourt) {
                          onSelectDestForCourt(r.destination_id || r.id);
                        }
                      }}
                    >
                      ⚖️ Preflight Test
                    </button>
                  </div>
                ))
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
