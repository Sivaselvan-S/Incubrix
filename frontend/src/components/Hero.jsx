import React from 'react';

export default function Hero({ onOpenCourt }) {
  return (
    <section className="hero">
      {/* Liquid Pill Chip */}
      <div className="hero-chip">
        <span>Passport Mission Control</span>
      </div>

      {/* Masked Headline Reveal */}
      <h1 className="hero-h1">
        <span className="ln">
          <span>LongTail</span>
        </span>
        <span className="ln">
          <span>Verifiable Passports</span>
        </span>
      </h1>

      {/* Explanatory Blurb */}
      <p className="hero-blurb">
        Zero-duplication publishing to long-tail destination networks.
        Every destination carries a verifiable living Passport with pure
        deterministic Preflight Court rulings and automated Drift Canaries.
      </p>
    </section>
  );
}
