import React, { useState, useEffect, useCallback } from 'react';
import SvgSprite from './components/SvgSprite';
import Sidebar from './components/Sidebar';
import Header from './components/Header';
import Hero from './components/Hero';
import TelemetryWave from './components/TelemetryWave';
import RightRail from './components/RightRail';
import PreflightModal from './components/PreflightModal';
import PublishModal from './components/PublishModal';
import ChaosCanaryModal from './components/ChaosCanaryModal';
import PassportRegistryModal from './components/PassportRegistryModal';
import RecommenderModal from './components/RecommenderModal';

const DEFAULT_DESTINATIONS = [
  {
    id: 'dest_devto',
    name: 'Dev.to Community',
    platform_key: 'devto',
    surface: 'community',
    level: 'L4',
    status: 'active',
    passport: { health_score: 98, schema_fingerprint: 'sha256:7f83b165d4918e' },
  },
  {
    id: 'dest_discourse',
    name: 'Discourse Forum',
    platform_key: 'discourse',
    surface: 'forum',
    level: 'L4',
    status: 'active',
    passport: { health_score: 99, schema_fingerprint: 'sha256:a12b4e89f3301a' },
  },
  {
    id: 'dest_ghost',
    name: 'Ghost Publication',
    platform_key: 'ghost',
    surface: 'blog',
    level: 'L3',
    status: 'active',
    passport: { health_score: 95, schema_fingerprint: 'sha256:c34d5e67a8821f' },
  },
  {
    id: 'dest_lemmy',
    name: 'Lemmy Federated Tech',
    platform_key: 'lemmy',
    surface: 'fediverse',
    level: 'L4',
    status: 'active',
    passport: { health_score: 97, schema_fingerprint: 'sha256:b89e2110cf900e' },
  },
  {
    id: 'dest_slack',
    name: 'Slack Operator Broadcast',
    platform_key: 'slack',
    surface: 'chat',
    level: 'L4',
    status: 'active',
    passport: { health_score: 100, schema_fingerprint: 'sha256:f55a1099d1234c' },
  },
  {
    id: 'dest_hashnode',
    name: 'Hashnode Engineering',
    platform_key: 'hashnode',
    surface: 'blog',
    level: 'L3',
    status: 'active',
    passport: { health_score: 94, schema_fingerprint: 'sha256:d88e7711a7654b' },
  },
  {
    id: 'dest_mrss',
    name: 'MRSS Syndication Feed',
    platform_key: 'mrss',
    surface: 'feed',
    level: 'L4',
    status: 'active',
    passport: { health_score: 99, schema_fingerprint: 'sha256:e44b3322c9988a' },
  },
];

export default function App() {
  const [activeTab, setActiveTab] = useState('dashboard');
  const [activePlatform, setActivePlatform] = useState('devto');
  const [activeModal, setActiveModal] = useState(null);
  const [selectedDestId, setSelectedDestId] = useState('dest_devto');
  const [destinations, setDestinations] = useState(DEFAULT_DESTINATIONS);
  const [apiStatus, setApiStatus] = useState('LIVE');

  // Load destinations from FastAPI backend
  const loadDestinations = useCallback(async () => {
    try {
      const res = await fetch('/api/v1/destinations');
      if (res.ok) {
        const data = await res.json();
        if (Array.isArray(data) && data.length > 0) {
          setDestinations(data);
        }
      }
    } catch (err) {
      // Backend not yet ready or offline, keep default rich state
    }
  }, []);

  // Check backend health
  const checkHealth = useCallback(async () => {
    try {
      const res = await fetch('/health');
      if (res.ok) {
        setApiStatus('ONLINE');
      } else {
        setApiStatus('DEGRADED');
      }
    } catch {
      setApiStatus('LOCAL');
    }
  }, []);

  useEffect(() => {
    loadDestinations();
    checkHealth();
  }, [loadDestinations, checkHealth]);

  // Find currently highlighted destination for RightRail card
  const currentDest =
    destinations.find(
      (d) =>
        d.platform_key?.toLowerCase() === activePlatform.toLowerCase() ||
        d.id === selectedDestId
    ) || destinations[0];

  const handleSelectTab = (tabId) => {
    setActiveTab(tabId);
    if (tabId === 'dashboard') {
      setActiveModal(null);
    } else if (tabId === 'passports') {
      setActiveModal('passports');
    } else if (tabId === 'court') {
      setActiveModal('court');
    } else if (tabId === 'publish') {
      setActiveModal('publish');
    } else if (tabId === 'chaos') {
      setActiveModal('chaos');
    } else if (tabId === 'recommender') {
      setActiveModal('recommender');
    }
  };

  const handleSelectPlatform = (platformId) => {
    setActivePlatform(platformId);
    const match = destinations.find(
      (d) => d.platform_key?.toLowerCase() === platformId.toLowerCase()
    );
    if (match) {
      setSelectedDestId(match.id);
    }
  };

  return (
    <>
      {/* SVG Symbol Library */}
      <SvgSprite />

      {/* Full-bleed stage with 1357 × 871 CSS reference canvas */}
      <main className="stage" role="main" aria-label="Flight Deck">
        {/* Left Sidebar */}
        <Sidebar activeTab={activeTab} onSelectTab={handleSelectTab} />

        {/* Top Header */}
        <Header
          apiStatus={apiStatus}
          onOpenPublish={() => setActiveModal('publish')}
          onOpenChaos={() => setActiveModal('chaos')}
          onOpenPassports={() => setActiveModal('passports')}
        />

        {/* Left Hero Title & Masked Reveal */}
        <Hero onOpenCourt={() => setActiveModal('court')} />

        {/* SVG Cubic Wave Telemetry & Platform Selectors */}
        <TelemetryWave
          activePlatform={activePlatform}
          onSelectPlatform={handleSelectPlatform}
        />

        {/* Right Rail Cards (Spotlight, Court, Idempotency, Canary) */}
        <RightRail
          activeDestination={currentDest}
          onOpenCourt={() => setActiveModal('court')}
          onOpenPublish={() => setActiveModal('publish')}
          onOpenChaos={() => setActiveModal('chaos')}
          onOpenPassports={() => setActiveModal('passports')}
        />
      </main>

      {/* Interactive Liquid Glass Modals */}
      <PreflightModal
        isOpen={activeModal === 'court'}
        onClose={() => {
          setActiveModal(null);
          setActiveTab('dashboard');
        }}
        destinations={destinations}
        initialDestId={selectedDestId}
      />

      <PublishModal
        isOpen={activeModal === 'publish'}
        onClose={() => {
          setActiveModal(null);
          setActiveTab('dashboard');
        }}
        destinations={destinations}
        initialDestId={selectedDestId}
      />

      <ChaosCanaryModal
        isOpen={activeModal === 'chaos'}
        onClose={() => {
          setActiveModal(null);
          setActiveTab('dashboard');
        }}
        destinations={destinations}
        onDestinationUpdated={loadDestinations}
      />

      <PassportRegistryModal
        isOpen={activeModal === 'passports'}
        onClose={() => {
          setActiveModal(null);
          setActiveTab('dashboard');
        }}
        destinations={destinations}
        onOpenCourtWithDest={(destId) => {
          setSelectedDestId(destId);
          setActiveModal('court');
        }}
        onOpenPublishWithDest={(destId) => {
          setSelectedDestId(destId);
          setActiveModal('publish');
        }}
        onRefreshDestinations={loadDestinations}
      />

      <RecommenderModal
        isOpen={activeModal === 'recommender'}
        onClose={() => {
          setActiveModal(null);
          setActiveTab('dashboard');
        }}
        onSelectDestForCourt={(destId) => {
          setSelectedDestId(destId);
          setActiveModal('court');
        }}
      />
    </>
  );
}
