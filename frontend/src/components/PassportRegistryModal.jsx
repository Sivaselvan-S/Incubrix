import React, { useState } from 'react';

export default function PassportRegistryModal({
  isOpen,
  onClose,
  destinations = [],
  onOpenCourtWithDest,
  onOpenPublishWithDest,
  onRefreshDestinations,
}) {
  if (!isOpen) return null;

  const [filterLevel, setFilterLevel] = useState('ALL');
  const [searchTerm, setSearchTerm] = useState('');
  const [actionLoading, setActionLoading] = useState(null);

  const filtered = destinations.filter((d) => {
    const matchesLevel = filterLevel === 'ALL' || d.level === filterLevel;
    const matchesSearch =
      searchTerm === '' ||
      d.name?.toLowerCase().includes(searchTerm.toLowerCase()) ||
      d.platform_key?.toLowerCase().includes(searchTerm.toLowerCase());
    return matchesLevel && matchesSearch;
  });

  const handleCertify = async (destId) => {
    setActionLoading(destId);
    try {
      const res = await fetch(`/api/v1/destinations/${destId}/certify`, {
        method: 'POST',
      });
      if (res.ok) {
        alert('Certification harness job queued successfully!');
        if (onRefreshDestinations) onRefreshDestinations();
      } else {
        alert('Failed to trigger certification.');
      }
    } catch (err) {
      alert(`Error: ${err.message}`);
    } finally {
      setActionLoading(null);
    }
  };

  return (
    <div className="liquid-modal-backdrop" onClick={onClose}>
      <div
        className="liquid-modal"
        style={{ width: 'calc(940 * var(--u))', maxHeight: '88vh' }}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="liquid-modal-header">
          <div>
            <h2 className="liquid-modal-title">Living Passport Registry</h2>
            <p style={{ fontSize: 'calc(12 * var(--u))', opacity: 0.8, marginTop: 'calc(4 * var(--u))' }}>
              Verifiable destination passports with cryptographic schema fingerprints and continuous compliance gauges.
            </p>
          </div>
          <button className="liquid-modal-close" onClick={onClose} aria-label="Close">
            ✕
          </button>
        </div>

        {/* Filter Controls */}
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            gap: 'calc(12 * var(--u))',
            marginBottom: 'calc(16 * var(--u))',
            flexWrap: 'wrap',
          }}
        >
          <div style={{ display: 'flex', gap: 'calc(6 * var(--u))', flexWrap: 'wrap' }}>
            {['ALL', 'L4', 'L3', 'L2', 'L1', 'L0'].map((lvl) => (
              <button
                key={lvl}
                className={`preset-chip ${filterLevel === lvl ? 'active' : ''}`}
                style={{
                  background: filterLevel === lvl ? 'rgba(255, 255, 255, 0.3)' : undefined,
                  fontWeight: filterLevel === lvl ? 700 : 500,
                }}
                onClick={() => setFilterLevel(lvl)}
              >
                {lvl}
              </button>
            ))}
          </div>

          <input
            type="text"
            className="glass-input"
            style={{ width: 'calc(240 * var(--u))', padding: 'calc(6 * var(--u)) calc(12 * var(--u))' }}
            placeholder="Search destination..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
          />
        </div>

        {/* Destination Table */}
        <div className="glass-table-wrap">
          <table className="glass-table">
            <thead>
              <tr>
                <th className="glass-th">Destination / Surface</th>
                <th className="glass-th">Level</th>
                <th className="glass-th">Health</th>
                <th className="glass-th">Schema Fingerprint</th>
                <th className="glass-th">Status</th>
                <th className="glass-th" style={{ textAlign: 'right' }}>
                  Actions
                </th>
              </tr>
            </thead>
            <tbody>
              {filtered.length === 0 ? (
                <tr>
                  <td colSpan="6" className="glass-td" style={{ textAlign: 'center', opacity: 0.6 }}>
                    No destinations matching filter criteria.
                  </td>
                </tr>
              ) : (
                filtered.map((d) => (
                  <tr key={d.id} className="glass-tr">
                    <td className="glass-td">
                      <div style={{ fontWeight: 600 }}>{d.name}</div>
                      <div style={{ fontSize: 'calc(11 * var(--u))', opacity: 0.7 }}>
                        {d.platform_key} · {d.surface || 'community'}
                      </div>
                    </td>
                    <td className="glass-td">
                      <span className={`badge ${d.level === 'L4' ? 'badge-l4' : 'badge-l0'}`}>
                        {d.level || 'L0'}
                      </span>
                    </td>
                    <td className="glass-td">
                      <strong>{d.passport?.health_score ?? (d.level === 'L4' ? 98 : 75)}%</strong>
                    </td>
                    <td className="glass-td">
                      <code style={{ fontSize: 'calc(11 * var(--u))', opacity: 0.85 }}>
                        {d.passport?.schema_fingerprint?.slice(0, 14) || 'sha256:8b4c2...'}
                      </code>
                    </td>
                    <td className="glass-td">
                      <span
                        style={{
                          color: d.status === 'active' ? '#34d399' : '#fb7185',
                          fontWeight: 600,
                          fontSize: 'calc(11 * var(--u))',
                          textTransform: 'uppercase',
                        }}
                      >
                        {d.status || 'ACTIVE'}
                      </span>
                    </td>
                    <td className="glass-td" style={{ textAlign: 'right' }}>
                      <div style={{ display: 'inline-flex', gap: 'calc(6 * var(--u))' }}>
                        <button
                          className="glass-btn-secondary"
                          style={{ padding: 'calc(4 * var(--u)) calc(10 * var(--u))', fontSize: 'calc(11 * var(--u))' }}
                          onClick={() => {
                            onClose();
                            if (onOpenCourtWithDest) onOpenCourtWithDest(d.id);
                          }}
                          title="Test in Preflight Court"
                        >
                          ⚖️ Court
                        </button>
                        <button
                          className="glass-btn-secondary"
                          style={{ padding: 'calc(4 * var(--u)) calc(10 * var(--u))', fontSize: 'calc(11 * var(--u))' }}
                          onClick={() => {
                            onClose();
                            if (onOpenPublishWithDest) onOpenPublishWithDest(d.id);
                          }}
                          title="Publish via Idempotency Ledger"
                        >
                          Publish
                        </button>
                        <button
                          className="glass-btn-secondary"
                          style={{ padding: 'calc(4 * var(--u)) calc(10 * var(--u))', fontSize: 'calc(11 * var(--u))' }}
                          onClick={() => handleCertify(d.id)}
                          disabled={actionLoading === d.id}
                          title="Run Certification Harness"
                        >
                          {actionLoading === d.id ? '...' : 'Certify'}
                        </button>
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
