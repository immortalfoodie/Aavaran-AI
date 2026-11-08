import { useState, useEffect } from 'react'
import {
  Button,
  Card,
  Stat,
  Tag,
  ConfidenceMeter,
  AssumptionRow,
  SafetyBlock,
  SpecTable,
  ModeSwitch,
  SourceBadge,
  type AppMode,
  type CitationInfo,
} from './design'
import { UI_LANGUAGES, setUiLanguage } from './i18n'
import { useTranslation } from 'react-i18next'
import { KisanMode } from './modes/kisan'
import { BusinessMode } from './modes/business'
import { ExpertMode } from './modes/expert'
import { AccuracyView } from './modes/accuracy'
import type { SaathiTurn } from './voice/voiceApi'

interface ComparisonRow {
  [key: string]: unknown
  material: string
  gauge: string
  otr: string
  wvtr: string
  cost: string
  epr: string
}

export function App() {
  const { t, i18n } = useTranslation()
  // Developer-only panels (design system, raw mode switcher) are hidden unless ?dev is in the URL.
  const isDev = typeof window !== 'undefined' && new URLSearchParams(window.location.search).has('dev')
  const [theme, setTheme] = useState<'light' | 'dark'>('light')
  const [activeMode, setActiveMode] = useState<AppMode>(() => {
    if (typeof window !== 'undefined') {
      const params = new URLSearchParams(window.location.search)
      const modeParam = params.get('mode')
      if (modeParam === 'kisan' || modeParam === 'business' || modeParam === 'expert') {
        return modeParam
      }
    }
    // Aavaran AI is voice-first: land on Kisan mode, where Saathi lives.
    return 'kisan'
  })
  const [voiceBusinessTurn, setVoiceBusinessTurn] = useState<SaathiTurn | null>(null)
  const [showAccuracyView, setShowAccuracyView] = useState<boolean>(false)
  const [showDesignShowcase, setShowDesignShowcase] = useState<boolean>(false)
  const [confidenceScore, setConfidenceScore] = useState<number>(8)
  const [activeCitation, setActiveCitation] = useState<CitationInfo | null>(null)
  const [activeEditField, setActiveEditField] = useState<string | null>(null)

  const handleModeChange = (newMode: AppMode) => {
    setActiveMode(newMode)
    if (typeof window !== 'undefined') {
      const url = new URL(window.location.href)
      url.searchParams.set('mode', newMode)
      window.history.replaceState({}, '', url.toString())
    }
  }

  // Toggle data-theme attribute on document root
  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme)
  }, [theme])

  const toggleTheme = () => {
    setTheme((prev) => (prev === 'light' ? 'dark' : 'light'))
  }

  const comparisonData: ComparisonRow[] = [
    {
      material: 'Mono-material PP Film',
      gauge: '40 µm',
      otr: '1,800 cc/m²·d',
      wvtr: '5.2 g/m²·d',
      cost: '₹1.95',
      epr: 'CAT-I (RECYCLABLE)',
    },
    {
      material: 'BOPP / Metallized CPP',
      gauge: '35 µm',
      otr: '45 cc/m²·d',
      wvtr: '1.2 g/m²·d',
      cost: '₹2.80',
      epr: 'CAT-III (MULTI-LAYER)',
    },
    {
      material: 'Laser Micro-perforated LDPE',
      gauge: '50 µm',
      otr: '8,400 cc/m²·d',
      wvtr: '18.5 g/m²·d',
      cost: '₹2.20',
      epr: 'CAT-I (RECYCLABLE)',
    },
    {
      material: 'High-Barrier PET / EVOH / PE',
      gauge: '65 µm',
      otr: '0.8 cc/m²·d',
      wvtr: '0.5 g/m²·d',
      cost: '₹5.10',
      epr: 'CAT-III (SPECIALTY)',
    },
  ]

  return (
    <div className="min-h-screen bg-paper text-ink px-3 py-3 sm:p-8 lg:p-12 transition-colors duration-[80ms]">
      <div className="max-w-5xl mx-auto space-y-5 sm:space-y-8">
        {/* Compact app bar: brand, language, who-am-I tabs. Nothing technical above the fold. */}
        <header className="border-3 border-ink bg-yellow px-3 py-2.5 sm:px-5 sm:py-3 shadow-[4px_4px_0_var(--ink)] space-y-2.5">
          <div className="flex items-center justify-between gap-3">
            <h1 className="font-display text-2xl sm:text-3xl uppercase tracking-tight text-ink m-0 leading-none">
              {t('app.title_short', { defaultValue: 'Aavaran AI' })}
            </h1>
            <label className="flex items-center gap-1.5 font-mono text-xs font-bold">
              <span aria-hidden="true">🌐</span>
              <select
                value={i18n.language}
                onChange={(e) => setUiLanguage(e.target.value)}
                className="min-h-[40px] border-3 border-ink bg-paper px-2 font-display text-sm text-ink cursor-pointer"
                aria-label={t('nav.language')}
              >
                {UI_LANGUAGES.map((l) => (
                  <option key={l.id} value={l.id}>
                    {l.label}
                  </option>
                ))}
              </select>
            </label>
          </div>
          {!showAccuracyView && (
            <nav className="grid grid-cols-2 gap-2" role="tablist" aria-label="Who are you?">
              {(
                [
                  ['kisan', '🌱', t('nav.farmer')],
                  ['business', '🏪', t('nav.shop')],
                ] as const
              ).map(([mode, icon, label]) => (
                <button
                  key={mode}
                  type="button"
                  role="tab"
                  aria-selected={activeMode === mode}
                  onClick={() => handleModeChange(mode)}
                  className={`min-h-[48px] px-2 border-3 border-ink font-display uppercase text-sm sm:text-base cursor-pointer flex items-center justify-center gap-2 ${
                    activeMode === mode ? 'bg-ink text-paper' : 'bg-paper text-ink hover:bg-grey/40'
                  }`}
                >
                  <span aria-hidden="true">{icon}</span>
                  <span>{label}</span>
                </button>
              ))}
            </nav>
          )}
        </header>

        {showAccuracyView ? (
          <div className="space-y-4">
            <Button variant="ghost" size="sm" label="✕" onClick={() => setShowAccuracyView(false)} />
            <AccuracyView />
          </div>
        ) : (
          <>
            {isDev && (
              <section className="space-y-2">
                <ModeSwitch activeMode={activeMode} onChange={handleModeChange} />
              </section>
            )}
            <div className={activeMode === 'kisan' ? 'block' : 'hidden'}>
              <KisanMode
                onVoiceBusiness={(turn) => {
                  setVoiceBusinessTurn(turn)
                  handleModeChange('business')
                }}
              />
            </div>
            <div className={activeMode === 'business' ? 'block' : 'hidden'}>
              <BusinessMode voiceTurn={voiceBusinessTurn} />
            </div>
            <div className={activeMode === 'expert' ? 'block' : 'hidden'}>
              <ExpertMode />
            </div>
          </>
        )}

        {/* Footer: the technical and secondary links live here, out of a farmer's way. */}
        <footer className="border-t-3 border-ink pt-4 flex flex-wrap items-center gap-x-4 gap-y-2 font-mono text-xs">
          <span className="font-bold">🎙 {t('nav.voice_by')} · Prisma + Timbre</span>
          <button type="button" className="underline cursor-pointer" onClick={() => setShowAccuracyView((v) => !v)}>
            📊 {t('nav.accuracy')}
          </button>
          <button type="button" className="underline cursor-pointer" onClick={() => handleModeChange('expert')}>
            🔬 {t('nav.expert')}
          </button>
          <button type="button" className="underline cursor-pointer" onClick={toggleTheme}>
            {theme === 'dark' ? `☀ ${t('nav.light')}` : `☾ ${t('nav.dark')}`}
          </button>
          {isDev && (
            <button type="button" className="underline cursor-pointer" onClick={() => setShowDesignShowcase((v) => !v)}>
              🎨 Design showcase
            </button>
          )}
          {isDev && <Tag variant="lime" label="✓ CONTRAST ≥ 7:1 AAA" />}
        </footer>

        {/* 3. Optional Design System Showcase */}
        {isDev && showDesignShowcase && (
          <div className="border-t-6 border-ink pt-12 space-y-12">
            <div className="p-4 bg-yellow border-3 border-ink flex items-center justify-between">
              <h2 className="font-display text-xl uppercase text-ink m-0">
                Design System Component Tokens Showcase
              </h2>
              <span className="font-mono text-xs font-bold bg-ink text-paper px-2 py-1">
                SECTION 10 ATOMS
              </span>
            </div>
            {/* 2. Safety Block (Critical Interlock) */}
            <section className="space-y-4">
          <div className="flex items-center justify-between flex-wrap gap-2">
            <h2 className="font-display text-xl sm:text-2xl uppercase tracking-tight text-ink m-0">
              02 · Safety Block (Refusal Interlock)
            </h2>
            <Tag variant="coral" label="CORAL RESERVED EXCLUSIVELY" />
          </div>
          <p className="font-body text-sm text-ink/80">
            Full coral fill, ink text, 6px border, 10px shadow, ⚠ paired with &quot;UNSAFE&quot;, and no dismiss button.
          </p>
          <SafetyBlock
            title="PACKAGING WILL NOT SAVE THIS FOOD"
            advisory="Cut {commodity_name} stored at 30 °C ambient presents fatal Clostridium botulinum and rapid bacterial soft-rot hazards. Any barrier film sealing this commodity will accelerate anaerobic toxins."
            action="Do not seal {commodity_name} in plastic. Chill immediately to &lt; 4 °C, sell unsealed within 8 hours, or cook."
            hazardCode="FSSAI-SEC-16 / BOT-01"
            result={{ resolved: { commodity: { display_name: 'mango' } } }}
          />
        </section>

        {/* 3. High-Trust Assumption Rows */}
        <section className="space-y-4">
          <div className="flex items-center justify-between flex-wrap gap-2">
            <h2 className="font-display text-xl sm:text-2xl uppercase tracking-tight text-ink m-0">
              03 · High-Trust Assumption Ledger
            </h2>
            <Tag variant="yellow" label="HIGHEST-TRUST COMPONENT" />
          </div>
          <p className="font-body text-sm text-ink/80">
            Tappable and obvious with field name, value, provenance badge, confidence meter, and edit trigger.
          </p>
          <div className="space-y-4">
            <AssumptionRow
              fieldName="Storage Temperature"
              value="28.5"
              unit="°C"
              source="GEO CLIMATOLOGY"
              citation={{
                source: 'GEO CLIMATOLOGY',
                title: 'Mumbai 95th Percentile Historical Ambient September Peak',
                year: 2026,
              }}
              confidence={7}
              onEdit={() => setActiveEditField('Storage Temperature')}
              onOpenCitation={setActiveCitation}
            />
            <AssumptionRow
              fieldName="Respiration Rate (R_O2)"
              value="22.4"
              unit="mg/kg·h"
              source="USDA AH-66"
              citation={{
                source: 'USDA AH-66',
                title: 'Handbook 66: Commercial Storage of Fruits, Vegetables & Florist Stocks',
                clause: 'Table 2: Solanum tuberosum respiration at 20°C',
                year: 2016,
              }}
              confidence={9}
              onEdit={() => setActiveEditField('Respiration Rate')}
              onOpenCitation={setActiveCitation}
            />
            <AssumptionRow
              fieldName="Critical Water Activity"
              value="0.65"
              unit="aw"
              source="LABUZA ISOTHERM"
              citation={{
                source: 'LABUZA ISOTHERM',
                title: 'GAB Moisture Sorption Isotherm Constants for Root Tubers',
                year: 2020,
              }}
              confidence={10}
              isExplicit={true}
              onEdit={() => setActiveEditField('Critical Water Activity')}
              onOpenCitation={setActiveCitation}
            />
          </div>
        </section>

        {/* 4. Confidence Meter Interactive Testing */}
        <section className="space-y-4">
          <div className="flex items-center justify-between flex-wrap gap-2">
            <h2 className="font-display text-xl sm:text-2xl uppercase tracking-tight text-ink m-0">
              04 · Confidence Meter
            </h2>
            <Tag variant="lime" label="DISCRETE BLOCKS · NEVER A GRADIENT" />
          </div>
          <Card variant="paper">
            <p className="font-body text-sm mb-4">
              Ten discrete blocks inside a 3px border communicate uncertainty honestly. Test the discrete levels:
            </p>
            <div className="flex flex-col sm:flex-row sm:items-center gap-6">
              <input
                type="range"
                min="0"
                max="10"
                value={confidenceScore}
                onChange={(e) => setConfidenceScore(Number(e.target.value))}
                className="w-48 accent-black cursor-pointer"
                aria-label="Confidence score slider"
              />
              <ConfidenceMeter score={confidenceScore} showNumeric={true} />
            </div>
          </Card>
        </section>

        {/* 5. SpecTable */}
        <section className="space-y-4">
          <div className="flex items-center justify-between flex-wrap gap-2">
            <h2 className="font-display text-xl sm:text-2xl uppercase tracking-tight text-ink m-0">
              05 · Spec Table
            </h2>
            <Tag variant="paper" label="2PX INTERNAL RULES · MONO NUMERALS" />
          </div>
          <SpecTable<ComparisonRow>
            caption="PERMEABILITY & EPR COMPLIANCE MATRIX"
            columns={[
              { key: 'material', header: 'MATERIAL STRUCTURE' },
              { key: 'gauge', header: 'GAUGE', isNumeric: true },
              { key: 'otr', header: 'OTR (cc/m²·d)', isNumeric: true },
              { key: 'wvtr', header: 'WVTR (g/m²·d)', isNumeric: true },
              { key: 'cost', header: 'COST ₹/PACK', isNumeric: true },
              { key: 'epr', header: 'EPR RECYCLING' },
            ]}
            data={comparisonData}
          />
        </section>

        {/* 6. Key Stats */}
        <section className="space-y-4">
          <div className="flex items-center justify-between flex-wrap gap-2">
            <h2 className="font-display text-xl sm:text-2xl uppercase tracking-tight text-ink m-0">
              06 · Display Stats
            </h2>
            <Tag variant="yellow" label="DISPLAY TYPE + UPPERCASE LABEL" />
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-6">
            <Stat
              value="42"
              unit="DAYS"
              label="PREDICTED SHELF LIFE"
              helper="Governed by GAB moisture sorption floor"
            />
            <Stat
              value="₹2.20"
              unit="/PACK"
              label="MONO-MATERIAL PACK COST"
              helper="Saves ₹0.60/pack vs multi-layer laminate"
            />
            <Stat
              value="15.05"
              unit="%"
              label="POST-HARVEST LOSS BASELINE"
              helper="MoFPI / NABCONS 2022 national benchmark"
            />
          </div>
        </section>

        {/* 7. Button Kit */}
        <section className="space-y-4">
          <div className="flex items-center justify-between flex-wrap gap-2">
            <h2 className="font-display text-xl sm:text-2xl uppercase tracking-tight text-ink m-0">
              07 · Button Kit
            </h2>
            <Tag variant="cyan" label="PRESS TRANSLATE 4PX · SHADOW 2PX" />
          </div>
          <Card variant="paper">
            <div className="space-y-6">
              <div>
                <h3 className="font-display text-sm uppercase mb-3">Color Variants</h3>
                <div className="flex flex-wrap gap-4">
                  <Button variant="primary" label="PRIMARY YELLOW" />
                  <Button variant="info" label="INFO CYAN" />
                  <Button variant="success" label="SUCCESS LIME" />
                  <Button variant="danger" label="DANGER CORAL" />
                  <Button variant="ghost" label="GHOST BUTTON" />
                </div>
              </div>

              <div>
                <h3 className="font-display text-sm uppercase mb-3">Sizes</h3>
                <div className="flex flex-wrap items-center gap-4">
                  <Button size="sm" label="SMALL (SM)" />
                  <Button size="md" label="MEDIUM (MD)" />
                  <Button size="lg" label="LARGE (LG)" />
                </div>
              </div>

              <div>
                <h3 className="font-display text-sm uppercase mb-3">
                  Kisan Mode (Minimum 64px Height for Outdoor Field & Calloused Thumb)
                </h3>
                <Button
                  size="xl"
                  variant="primary"
                  label="🌾 KISAN ONE-TAP GENERATE SPEC (64PX)"
                  className="w-full sm:w-auto"
                />
              </div>
            </div>
          </Card>
        </section>

        {/* 8. Layered Cards with Deliberate Overlap */}
        <section className="space-y-4">
          <div className="flex items-center justify-between flex-wrap gap-2">
            <h2 className="font-display text-xl sm:text-2xl uppercase tracking-tight text-ink m-0">
              08 · Layered Overlapping Cards
            </h2>
            <Tag variant="violet" label="PAPER-STACK LAYOUT" />
          </div>
          <div className="relative pt-4 pb-8 max-w-2xl">
            <Card variant="grey" className="relative z-0">
              <span className="font-display text-sm uppercase bg-ink text-paper px-2 py-0.5 inline-block mb-2">
                BASE FILM LAYER
              </span>
              <p className="font-body text-sm font-semibold">
                Outer Carrier: 12 µm Biaxially-Oriented Polyethylene Terephthalate (BOPET)
              </p>
            </Card>
            <Card variant="paper" offset="top">
              <span className="font-display text-sm uppercase bg-ink text-paper px-2 py-0.5 inline-block mb-2">
                BARRIER LAYER
              </span>
              <p className="font-body text-sm font-semibold">
                Core Barrier: 15 µm EVOH (32 mol% ethylene)
              </p>
            </Card>
            <Card variant="yellow" offset="top">
              <span className="font-display text-sm uppercase bg-ink text-paper px-2 py-0.5 inline-block mb-2">
                SEALANT LAYER
              </span>
              <p className="font-body text-sm font-semibold">
                Inner Sealant: 40 µm Metallocene Linear Low-Density Polyethylene (mLLDPE)
              </p>
            </Card>
          </div>
        </section>

        {/* 9. Tags & Source Badges Showcase */}
        <section className="space-y-4">
          <div className="flex items-center justify-between flex-wrap gap-2">
            <h2 className="font-display text-xl sm:text-2xl uppercase tracking-tight text-ink m-0">
              09 · Micro Tags & Provenance Badges
            </h2>
            <Tag variant="lime" label="UPPERCASE MONO MICRO-LABELS" />
          </div>
          <Card variant="paper">
            <div className="flex flex-wrap gap-3 items-center">
              <Tag variant="paper" label="PAPER TAG" />
              <Tag variant="yellow" label="YELLOW TAG" />
              <Tag variant="cyan" label="CYAN TAG" />
              <Tag variant="lime" label="LIME TAG" />
              <Tag variant="coral" label="CORAL TAG" />
              <Tag variant="violet" label="VIOLET TAG" />
              <Tag variant="grey" label="GREY TAG" />
            </div>
            <div className="mt-4 pt-4 border-t-2 border-ink flex flex-wrap gap-4 items-center">
              <SourceBadge
                source="FSSAI 2018"
                citation={{
                  source: 'FSSAI 2018',
                  title: 'Food Safety and Standards (Packaging) Regulations, 2018',
                  clause: 'Schedule I, Article 4',
                }}
                onOpenCitation={setActiveCitation}
              />
              <SourceBadge
                source="USDA AH-66"
                citation={{
                  source: 'USDA AH-66',
                  title: 'The Commercial Storage of Fruits, Vegetables, and Florist and Nursery Stocks',
                  clause: 'Table 2, Commodity Respiration Rates',
                }}
                onOpenCitation={setActiveCitation}
              />
              <SourceBadge
                source="PWM 2022"
                citation={{
                  source: 'PWM 2022',
                  title: 'Plastic Waste Management (Amendment) Rules, 2022',
                  clause: 'EPR Schedule II',
                }}
                onOpenCitation={setActiveCitation}
              />
            </div>
          </Card>
        </section>
      </div>
    )}

        {/* Citation Modal / Flyout */}
        {activeCitation && (
          <div
            role="dialog"
            aria-modal="true"
            aria-label="Citation Details"
            className="fixed inset-0 bg-ink/70 flex items-center justify-center p-4 z-50"
          >
            <div className="bg-paper border-6 border-ink p-6 max-w-lg w-full shadow-[10px_10px_0_var(--ink)] space-y-4">
              <div className="flex items-center justify-between border-b-3 border-ink pb-3">
                <span className="font-display text-lg uppercase bg-yellow text-ink px-2 py-0.5 border border-ink">
                  OFFICIAL CITATION
                </span>
                <span className="font-mono text-xs font-bold text-ink">
                  {activeCitation.source}
                </span>
              </div>
              <h3 className="font-display text-xl text-ink uppercase">
                {activeCitation.title}
              </h3>
              {activeCitation.clause && (
                <p className="font-mono text-xs bg-grey/40 p-2 border-2 border-ink text-ink font-semibold">
                  CLAUSE: {activeCitation.clause}
                </p>
              )}
              <div className="flex justify-end pt-2">
                <Button
                  size="sm"
                  variant="primary"
                  label="CLOSE CITATION"
                  onClick={() => setActiveCitation(null)}
                />
              </div>
            </div>
          </div>
        )}

        {/* Edit Parameter Modal */}
        {activeEditField && (
          <div
            role="dialog"
            aria-modal="true"
            aria-label="Edit Assumption Parameter"
            className="fixed inset-0 bg-ink/70 flex items-center justify-center p-4 z-50"
          >
            <div className="bg-paper border-6 border-ink p-6 max-w-md w-full shadow-[10px_10px_0_var(--ink)] space-y-4">
              <div className="flex items-center justify-between border-b-3 border-ink pb-3">
                <span className="font-display text-base uppercase bg-cyan text-ink px-2 py-0.5 border border-ink">
                  PARAMETER OVERRIDE
                </span>
                <span className="font-mono text-xs font-bold">LEDGER</span>
              </div>
              <h3 className="font-display text-lg uppercase text-ink">
                EDIT {activeEditField}
              </h3>
              <p className="font-body text-xs text-ink/80">
                Updating this parameter will immediately trigger recalculation of permeation, microbial growth, and shelf life models.
              </p>
              <input
                type="text"
                placeholder="Enter new verified value..."
                className="w-full border-3 border-ink p-3 font-mono text-base bg-paper text-ink focus:outline-none focus:bg-yellow/20"
                autoFocus
              />
              <div className="flex justify-end gap-3 pt-2">
                <Button
                  size="sm"
                  variant="ghost"
                  label="CANCEL"
                  onClick={() => setActiveEditField(null)}
                />
                <Button
                  size="sm"
                  variant="primary"
                  label="SAVE & RECALCULATE"
                  onClick={() => setActiveEditField(null)}
                />
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

export default App
