// =============================================================================
// COURTVIEW — Shared pieces used across all option variants
// Custom pictograms (basketball, court, camera, etc), top nav, ticker.
// =============================================================================

// --------- Pictograms (custom, line-based, 16px viewBox by default) ----------
const Pict = {
  Court: ({ size = 14, stroke = "currentColor", strokeWidth = 1.4 }) => (
    <svg className="cv-icon" width={size} height={size} viewBox="0 0 16 16" fill="none">
      <rect x="1.5" y="3" width="13" height="10" stroke={stroke} strokeWidth={strokeWidth} />
      <line x1="8" y1="3" x2="8" y2="13" stroke={stroke} strokeWidth={strokeWidth} />
      <circle cx="8" cy="8" r="1.6" stroke={stroke} strokeWidth={strokeWidth} />
      <path d="M1.5 5.5h2.2v5h-2.2M14.5 5.5h-2.2v5h2.2" stroke={stroke} strokeWidth={strokeWidth} />
    </svg>
  ),
  Ball: ({ size = 14, stroke = "currentColor", strokeWidth = 1.4 }) => (
    <svg className="cv-icon" width={size} height={size} viewBox="0 0 16 16" fill="none">
      <circle cx="8" cy="8" r="6" stroke={stroke} strokeWidth={strokeWidth} />
      <path d="M2 8h12M8 2v12M3.4 3.4c2 2 2 7 0 9.2M12.6 3.4c-2 2-2 7 0 9.2"
            stroke={stroke} strokeWidth={strokeWidth} fill="none" />
    </svg>
  ),
  Camera: ({ size = 14, stroke = "currentColor", strokeWidth = 1.4 }) => (
    <svg className="cv-icon" width={size} height={size} viewBox="0 0 16 16" fill="none">
      <rect x="1.5" y="4.5" width="11" height="8" stroke={stroke} strokeWidth={strokeWidth} />
      <path d="M12.5 7l2.5-1.5v6l-2.5-1.5z" stroke={stroke} strokeWidth={strokeWidth} fill="none" />
      <circle cx="4" cy="6.8" r="0.6" fill={stroke} />
    </svg>
  ),
  Pin: ({ size = 14, stroke = "currentColor", strokeWidth = 1.4 }) => (
    <svg className="cv-icon" width={size} height={size} viewBox="0 0 16 16" fill="none">
      <path d="M8 1.5c-2.8 0-5 2.2-5 5 0 3.7 5 8 5 8s5-4.3 5-8c0-2.8-2.2-5-5-5z"
            stroke={stroke} strokeWidth={strokeWidth} />
      <circle cx="8" cy="6.5" r="1.6" stroke={stroke} strokeWidth={strokeWidth} />
    </svg>
  ),
  Whistle: ({ size = 14, stroke = "currentColor", strokeWidth = 1.4 }) => (
    <svg className="cv-icon" width={size} height={size} viewBox="0 0 16 16" fill="none">
      <path d="M1.5 7.5h7l3-2v6l-3-2h-7v-2z" stroke={stroke} strokeWidth={strokeWidth} fill="none" />
      <circle cx="4.5" cy="8.5" r="1.4" stroke={stroke} strokeWidth={strokeWidth} />
      <path d="M11.5 5l2-2" stroke={stroke} strokeWidth={strokeWidth} />
    </svg>
  ),
  Database: ({ size = 14, stroke = "currentColor", strokeWidth = 1.4 }) => (
    <svg className="cv-icon" width={size} height={size} viewBox="0 0 16 16" fill="none">
      <ellipse cx="8" cy="3.5" rx="5.5" ry="1.8" stroke={stroke} strokeWidth={strokeWidth} />
      <path d="M2.5 3.5v9c0 1 2.5 1.8 5.5 1.8s5.5-.8 5.5-1.8v-9M2.5 8c0 1 2.5 1.8 5.5 1.8s5.5-.8 5.5-1.8"
            stroke={stroke} strokeWidth={strokeWidth} fill="none" />
    </svg>
  ),
  Key: ({ size = 14, stroke = "currentColor", strokeWidth = 1.4 }) => (
    <svg className="cv-icon" width={size} height={size} viewBox="0 0 16 16" fill="none">
      <circle cx="5" cy="8" r="3" stroke={stroke} strokeWidth={strokeWidth} />
      <path d="M8 8h6.5M12 8v2M14.5 8v1.5" stroke={stroke} strokeWidth={strokeWidth} />
    </svg>
  ),
  Settings: ({ size = 14, stroke = "currentColor", strokeWidth = 1.4 }) => (
    <svg className="cv-icon" width={size} height={size} viewBox="0 0 16 16" fill="none">
      <circle cx="8" cy="8" r="2" stroke={stroke} strokeWidth={strokeWidth} />
      <path d="M8 1v2M8 13v2M1 8h2M13 8h2M3.5 3.5l1.4 1.4M11.1 11.1l1.4 1.4M3.5 12.5l1.4-1.4M11.1 4.9l1.4-1.4"
            stroke={stroke} strokeWidth={strokeWidth} />
    </svg>
  ),
  Stats: ({ size = 14, stroke = "currentColor", strokeWidth = 1.4 }) => (
    <svg className="cv-icon" width={size} height={size} viewBox="0 0 16 16" fill="none">
      <path d="M2 14V6M6 14V2M10 14v-6M14 14V8" stroke={stroke} strokeWidth={strokeWidth} strokeLinecap="square" />
    </svg>
  ),
  Home: ({ size = 14, stroke = "currentColor", strokeWidth = 1.4 }) => (
    <svg className="cv-icon" width={size} height={size} viewBox="0 0 16 16" fill="none">
      <path d="M2 7l6-5 6 5v7H2z" stroke={stroke} strokeWidth={strokeWidth} fill="none" />
      <path d="M6 14V9h4v5" stroke={stroke} strokeWidth={strokeWidth} />
    </svg>
  ),
  Power: ({ size = 14, stroke = "currentColor", strokeWidth = 1.4 }) => (
    <svg className="cv-icon" width={size} height={size} viewBox="0 0 16 16" fill="none">
      <path d="M8 2v6M4.5 4.5a5 5 0 107 0" stroke={stroke} strokeWidth={strokeWidth} fill="none" />
    </svg>
  ),
  Arrow: ({ size = 12, stroke = "currentColor", strokeWidth = 1.4, dir = "right" }) => (
    <svg className="cv-icon" width={size} height={size} viewBox="0 0 16 16" fill="none"
         style={{ transform: `rotate(${ {right:0,down:90,left:180,up:270}[dir] }deg)` }}>
      <path d="M3 8h10M9 4l4 4-4 4" stroke={stroke} strokeWidth={strokeWidth} fill="none" />
    </svg>
  ),
};

// --------- Top nav (horizontal) ---------
function TopNav({ active = "home", clock = "21:34:08" }) {
  const items = [
    { id: "home", label: "DASH", icon: Pict.Home, href: "#home" },
    { id: "analysis", label: "ANALYSIS", icon: Pict.Ball, href: "#analysis" },
    { id: "result", label: "RESULTS", icon: Pict.Stats, href: "#result" },
    { id: "database", label: "DB", icon: Pict.Database, href: "#database" },
    { id: "equipment", label: "RIG", icon: Pict.Camera, href: "#equipment" },
    { id: "court", label: "VENUE", icon: Pict.Pin, href: "#court" },
    { id: "referee", label: "OFFICIALS", icon: Pict.Whistle, href: "#referee" },
    { id: "rules", label: "RULES", icon: Pict.Whistle, href: "#rules" },
    { id: "license", label: "LICENSE", icon: Pict.Key, href: "#license" },
    { id: "settings", label: "CFG", icon: Pict.Settings, href: "#settings" },
  ];
  return (
    <div className="cv-topbar">
      <div className="cv-brand">
        <span className="mark"></span>
        <span className="name">COURT<b>VIEW</b></span>
      </div>
      <nav className="cv-nav">
        {items.map(it => {
          const Icon = it.icon;
          return (
            <a key={it.id} className={`cv-nav-item ${active === it.id ? "active" : ""}`} href={it.href}>
              <Icon size={13} />
              <span>{it.label}</span>
            </a>
          );
        })}
        <span className="cv-nav-spacer"></span>
      </nav>
      <div className="cv-nav-meta">
        <div className="pill">
          <span className="val">{clock}</span>
        </div>
        <div className="avatar">JS</div>
      </div>
    </div>
  );
}

// --------- Ticker (broadcast-style scroll) ---------
function Ticker({ items, accent = "var(--hot)" }) {
  return (
    <div style={{
      height: 28, background: "var(--bg-0)", borderTop: "1px solid var(--line-2)",
      borderBottom: "1px solid var(--line-2)",
      display: "flex", alignItems: "center", overflow: "hidden",
      fontFamily: "var(--f-mono)", fontSize: 11, color: "var(--fg-1)"
    }}>
      <div style={{
        background: accent, color: "#0A0B0D", height: "100%",
        display: "flex", alignItems: "center", padding: "0 12px",
        fontWeight: 700, fontSize: 10, letterSpacing: "1px"
      }}>LIVE FEED</div>
      <div style={{ display: "flex", gap: 32, padding: "0 16px", whiteSpace: "nowrap", animation: "tickerScroll 60s linear infinite" }}>
        {[...items, ...items].map((t, i) => (
          <span key={i} style={{ display: "inline-flex", gap: 8, alignItems: "center" }}>
            <span style={{ color: "var(--fg-2)" }}>{t.tag}</span>
            <span>{t.text}</span>
            {t.val && <span style={{ color: t.up ? "var(--good)" : t.down ? "var(--bad)" : "var(--fg-0)" }}>{t.val}</span>}
            <span style={{ color: "var(--line-3)" }}>·</span>
          </span>
        ))}
      </div>
      <style>{`@keyframes tickerScroll { 0%{transform:translateX(0)} 100%{transform:translateX(-50%)} }`}</style>
    </div>
  );
}

// expose
Object.assign(window, { Pict, TopNav, Ticker });
