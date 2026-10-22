import React, { useState, useEffect } from 'react';

function generateRandomKey() {
  return 'idem_' + Math.random().toString(36).substring(2, 10) + '_' + Date.now().toString(36);
}

export default function PublishModal({
  isOpen,
  onClose,
  destinations = [],
  initialDestId = '',
}) {
  if (!isOpen) return null;

  const defaultDest = initialDestId || (destinations[0]?.id || 'dest_devto');
  const [destId, setDestId] = useState(defaultDest);
  const [title, setTitle] = useState('Verifiable Passports: Zero Duplication Architecture');
  const [body, setBody] = useState(
    '# Zero Duplication Publishing\n\nHow distributed systems leverage cryptographic intent ledgers and idempotent dispatch pipelines.'
  );
  const [idempotencyKey, setIdempotencyKey] = useState(generateRandomKey());
  const [lastKeyUsed, setLastKeyUsed] = useState('');
  const [loading, setLoading] = useState(false);
  const [publishResult, setPublishResult] = useState(null);
  const [jobStatus, setJobStatus] = useState(null);
  const [error, setError] = useState(null);

  // Poll job status if a job_id was returned
  useEffect(() => {
    if (!publishResult?.job_id) return;
    let timer;
    let attempts = 0;

    const poll = async () => {
      try {
        const res = await fetch(`/api/v1/jobs/${publishResult.job_id}`);
        if (res.ok) {
          const data = await res.json();
          setJobStatus(data);
          if (data.status === 'completed' || data.status === 'failed' || attempts > 10) {
            return;
          }
        }
      } catch (err) {
        // ignore polling errors
      }
      attempts++;
      timer = setTimeout(poll, 1200);
    };

    poll();
    return () => clearTimeout(timer);
  }, [publishResult?.job_id]);

  const handlePublish = async (e) => {
    e?.preventDefault();
    if (!idempotencyKey.trim()) {
      setError('Idempotency key is required to guarantee zero duplication.');
      return;
    }

    setLoading(true);
    setError(null);
    setPublishResult(null);
    setJobStatus(null);

    try {
      const payload = {
        destination_id: destId,
        content_id: 'article_' + Date.now().toString(36),
        rendition: {
          title,
          body_markdown: body,
          tags: ['architecture', 'idempotency', 'distributed'],
        },
      };

      const res = await fetch('/api/v1/publications', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Idempotency-Key': idempotencyKey,
        },
        body: JSON.stringify(payload),
      });

      const data = await res.json();
      if (!res.ok) {
        throw new Error(data?.detail?.error?.message || data?.detail || `HTTP ${res.status}`);
      }

      setPublishResult(data);
      setLastKeyUsed(idempotencyKey);
    } catch (err) {
      setError(err.message || 'Failed to dispatch publication');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="liquid-modal-backdrop" onClick={onClose}>
      <div
        className="liquid-modal"
        style={{ width: 'calc(800 * var(--u))' }}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="liquid-modal-header">
          <div>
            <h2 className="liquid-modal-title">Idempotency Ledger & Content Dispatch</h2>
            <p style={{ fontSize: 'calc(12 * var(--u))', opacity: 0.8, marginTop: 'calc(4 * var(--u))' }}>
              Guaranteed single-execution delivery. Replaying identical keys guarantees zero duplicate posts.
            </p>
          </div>
          <button className="liquid-modal-close" onClick={onClose} aria-label="Close">
            ✕
          </button>
        </div>

        <form onSubmit={handlePublish}>
          <div className="form-field">
            <label className="form-label">Target Destination</label>
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
                    Dev.to Community
                  </option>
                  <option value="dest_discourse" style={{ background: '#0a1d29', color: '#fff' }}>
                    Discourse Forum
                  </option>
                  <option value="dest_ghost" style={{ background: '#0a1d29', color: '#fff' }}>
                    Ghost Publication
                  </option>
                </>
              )}
            </select>
          </div>

          <div className="form-field">
            <label className="form-label">Content Title</label>
            <input
              type="text"
              className="glass-input"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              required
            />
          </div>

          <div className="form-field">
            <label className="form-label">Body Markdown</label>
            <textarea
              className="glass-textarea"
              style={{ height: 'calc(110 * var(--u))', resize: 'vertical' }}
              value={body}
              onChange={(e) => setBody(e.target.value)}
              required
            />
          </div>

          {/* Idempotency Key Section with Replay Test */}
          <div className="form-field">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <label className="form-label">Idempotency-Key Header</label>
              <div style={{ display: 'flex', gap: 'calc(6 * var(--u))' }}>
                <button
                  type="button"
                  className="preset-chip"
                  onClick={() => setIdempotencyKey(generateRandomKey())}
                  title="Generate a fresh unique UUID key"
                >
                  🎲 Fresh Key
                </button>
                {lastKeyUsed && (
                  <button
                    type="button"
                    className="preset-chip"
                    onClick={() => setIdempotencyKey(lastKeyUsed)}
                    title="Replay the exact key used previously to test deduplication"
                    style={{ borderColor: '#f59e0b', color: '#fbbf24' }}
                  >
                    🔁 Replay Last Key ({lastKeyUsed.slice(0, 10)}...)
                  </button>
                )}
              </div>
            </div>
            <input
              type="text"
              className="glass-input"
              style={{ fontFamily: 'var(--font-mono)' }}
              value={idempotencyKey}
              onChange={(e) => setIdempotencyKey(e.target.value)}
              required
            />
          </div>

          <button
            type="submit"
            className="glass-btn-primary"
            disabled={loading}
            style={{ width: '100%', marginTop: 'calc(8 * var(--u))' }}
          >
            <svg style={{ width: 'calc(18 * var(--u))', height: 'calc(18 * var(--u))', fill: '#ffffff' }}>
              <use href="#i-plus" />
            </svg>
            {loading ? 'Reserving Intent & Dispatching...' : 'Dispatch with Intent Guarantee'}
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

        {/* Live Result Display */}
        {publishResult && (
          <div style={{ marginTop: 'calc(20 * var(--u))' }}>
            {publishResult.status === 'cached' ? (
              <div className="verdict-banner rewrite">
                <div>
                  <span style={{ fontSize: 'calc(11 * var(--u))', textTransform: 'uppercase', opacity: 0.8 }}>
                    Deduplication Triggered
                  </span>
                  <div style={{ fontSize: 'calc(18 * var(--u))', fontWeight: 800 }}>
                    ⚡ Idempotent Cache Hit — Zero Duplicates Created!
                  </div>
                  <div style={{ fontSize: 'calc(12 * var(--u))', opacity: 0.9, marginTop: 'calc(4 * var(--u))' }}>
                    Identical idempotency key <code>{publishResult.idempotency_key}</code> detected in ledger.
                    Returned cached response without firing duplicate outbound network requests.
                  </div>
                </div>
                <span className="badge badge-rewrite">CACHED</span>
              </div>
            ) : (
              <div className="verdict-banner allow">
                <div style={{ flex: 1 }}>
                  <span style={{ fontSize: 'calc(11 * var(--u))', textTransform: 'uppercase', opacity: 0.8 }}>
                    Job Enqueued
                  </span>
                  <div style={{ fontSize: 'calc(18 * var(--u))', fontWeight: 800 }}>
                    Dispatched Job: {publishResult.job_id || 'Queued'}
                  </div>
                  <div style={{ fontSize: 'calc(12 * var(--u))', opacity: 0.85, marginTop: 'calc(4 * var(--u))' }}>
                    Status:{' '}
                    <strong>
                      {jobStatus?.status?.toUpperCase() || publishResult.status?.toUpperCase() || 'QUEUED'}
                    </strong>{' '}
                    · Intent reserved in ledger.
                  </div>

                  {/* Progress bar */}
                  <div className="progress-track">
                    <div
                      className="progress-bar"
                      style={{
                        width:
                          jobStatus?.status === 'completed'
                            ? '100%'
                            : jobStatus?.status === 'running'
                            ? '65%'
                            : '25%',
                      }}
                    />
                  </div>
                </div>
                <span className="badge badge-allow">ACCEPTED</span>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
