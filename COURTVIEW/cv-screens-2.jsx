// =============================================================================
// COURTVIEW — Editorial supporting screens (set 2)
// License, Calibrate, Settings, Result
// =============================================================================

// ---------- LICENSE ----------
function CvLicenseScreen() {
  return (
    <div style={{ background: "var(--bg-1)", color: "var(--fg-0)", height: "100%", display: "flex", flexDirection: "column", overflow: "hidden" }}>
      <TopNav active="license" />
      <div style={{ flex: 1, overflow: "auto" }}>
        <EdHero
          size="sm"
          issue="LIC · 002"
          tag="good" tagText="ACTIVE"
          kicker="ENTERPRISE LICENSE · SPOIN INC. · OLYMPIC PARK"
          title={{ primary: "LICENSED.", accent: "OPERATIONAL." }}
          subline={[
            { k: "PLAN", v: "ENTERPRISE · UNLIMITED" },
            { k: "SEAT", v: "operator@spoin.kr" },
            { k: "EXPIRES", v: "2027-04-30" },
          ]}
        />

        <EdStatStrip items={[
          { k: "STATUS", v: "ACTIVE", c: "var(--good)" },
          { k: "DAYS LEFT", v: 358, sub: "of 365" },
          { k: "GAMES THIS MONTH", v: 47, sub: "of unlimited" },
          { k: "STREAMS", v: "8 / 8", c: "var(--good)" },
          { k: "STORAGE", v: "142 GB", sub: "/ 2 TB" },
        ]} />

        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 1, background: "var(--line-2)" }}>
          <EdPanel kicker="LICENSE KEY" title="ACTIVATION">
            <div style={{ padding: 24, background: "var(--bg-2)", border: "1px solid var(--line-2)", fontFamily: "var(--f-mono)", fontSize: 16, fontWeight: 600, letterSpacing: 4, color: "var(--hot)", textAlign: "center" }}>
              CV-ENT-26 · 8B4F-N3K2-X9W1
            </div>
            <div style={{ marginTop: 14, fontFamily: "var(--f-mono)", fontSize: 11, color: "var(--fg-2)", lineHeight: 1.7 }}>
              <div><span style={{ color: "var(--fg-3)" }}>ISSUED —</span> 2026-04-30 · 14:22 KST</div>
              <div><span style={{ color: "var(--fg-3)" }}>HARDWARE ID —</span> 8B4F-N3K2-X9W1-RTX4090</div>
              <div><span style={{ color: "var(--fg-3)" }}>BOUND TO —</span> SPOIN-OP-001</div>
            </div>
            <div style={{ display: "flex", gap: 8, marginTop: 18 }}>
              <button className="cv-btn">REVOKE</button>
              <button className="cv-btn">EXPORT KEY</button>
              <button className="cv-btn primary">RENEW</button>
            </div>
          </EdPanel>

          <EdPanel kicker="ENTITLEMENTS" title="WHAT'S INCLUDED">
            {[
              ["MULTI-CAMERA TRACKING", "8 streams", true],
              ["BROADCAST SCOREBOARD", "4K · 60FPS", true],
              ["FIBA / KBL / NBL CERT.", "all leagues", true],
              ["PLAYER ANALYTICS", "unlimited", true],
              ["EXPORT · CSV / JSON", "unlimited", true],
              ["NBA RULESET", "license required", false],
              ["CLOUD ARCHIVE", "add-on", false],
              ["24/7 SUPPORT", "included", true],
            ].map(([feat, v, ok], i) => (
              <div key={i} style={{ display: "grid", gridTemplateColumns: "16px 1fr 130px", padding: "12px 0", borderBottom: "1px solid var(--line-1)", alignItems: "center" }}>
                <span style={{ color: ok ? "var(--good)" : "var(--fg-3)", fontFamily: "var(--f-mono)", fontSize: 14 }}>{ok ? "✓" : "—"}</span>
                <span style={{ fontFamily: "var(--f-display)", fontSize: 13, fontWeight: 600, color: ok ? "var(--fg-0)" : "var(--fg-3)" }}>{feat}</span>
                <span style={{ fontFamily: "var(--f-mono)", fontSize: 11, color: ok ? "var(--fg-2)" : "var(--fg-3)", textAlign: "right" }}>{v}</span>
              </div>
            ))}
          </EdPanel>
        </div>
      </div>
    </div>
  );
}

// ---------- CALIBRATE ----------
function CvCalibrateScreen() {
  const points = [
    { id: 0, name: "corner_TL", set: true, err: 0.18 },
    { id: 1, name: "corner_TR", set: true, err: 0.22 },
    { id: 2, name: "corner_BL", set: true, err: 0.31 },
    { id: 3, name: "corner_BR", set: true, err: 0.27 },
    { id: 4, name: "half_T", set: true, err: 0.19 },
    { id: 5, name: "half_B", set: true, err: 0.24 },
    { id: 6, name: "center", set: true, err: 0.16 },
    { id: 7, name: "paint_L_TL", set: true, err: 0.34 },
    { id: 8, name: "paint_L_TR", set: false },
    { id: 9, name: "paint_L_BL", set: false },
    { id: 10, name: "paint_R_TR", set: false },
    { id: 11, name: "freethrow_L", set: false },
    { id: 12, name: "freethrow_R", set: false },
  ];
  const setCount = points.filter(p => p.set).length;
  return (
    <div style={{ background: "var(--bg-1)", color: "var(--fg-0)", height: "100%", display: "flex", flexDirection: "column", overflow: "hidden" }}>
      <TopNav active="equipment" />
      <div style={{ flex: 1, overflow: "auto" }}>
        <EdHero
          size="sm"
          issue="CAL · CAM03"
          tag="hot" tagText="CALIBRATION"
          kicker="CAM 03 · SIDELINE-W · OLYMPIC PARK · COURT 03"
          title={{ primary: "PIN THE COURT.", accent: "PIN POINT." }}
          subline={[
            { k: "STANDARD", v: "FIBA · 28m × 15m" },
            { k: "POINTS SET", v: `${setCount} / 13` },
            { k: "REPROJ. ERROR", v: "0.31 px" },
          ]}
          right={<button className="cv-btn primary" disabled={setCount < 4}>SAVE CALIBRATION</button>}
        />

        <EdStatStrip items={[
          { k: "POINTS", v: `${setCount}/13`, c: setCount >= 4 ? "var(--good)" : "var(--warn)" },
          { k: "QUALITY", v: "94%", c: "var(--good)" },
          { k: "REPROJ. ERR", v: "0.31", sub: "px / m" },
          { k: "TILT", v: "−2.4°", sub: "auto-corrected" },
          { k: "ELAPSED", v: "01:42", sub: "since reset" },
        ]} />

        <div style={{ display: "grid", gridTemplateColumns: "1.5fr 1fr", gap: 1, background: "var(--line-2)" }}>
          {/* Left — snapshot canvas */}
          <EdPanel kicker="CAMERA SNAPSHOT" title="PIN POINTS"
            right={<span style={{ fontFamily: "var(--f-mono)", fontSize: 10, color: "var(--fg-3)" }}>S = SKIP · ⌘Z = UNDO</span>}>
            <div style={{ aspectRatio: "16/9", background: "#000", border: "1px solid var(--line-2)", position: "relative", overflow: "hidden", cursor: "crosshair" }}>
              <div style={{ position: "absolute", inset: 0,
                background: `repeating-linear-gradient(45deg, transparent 0 14px, rgba(255,255,255,0.02) 14px 15px),
                             radial-gradient(ellipse at 50% 60%, rgba(255,90,31,0.05), transparent 60%)` }}></div>
              {/* Court overlay */}
              <svg viewBox="0 0 800 450" style={{ position: "absolute", inset: 0, width: "100%", height: "100%" }} preserveAspectRatio="none">
                <path d="M 60 380 L 740 380 L 690 90 L 110 90 Z" stroke="rgba(255,90,31,0.55)" strokeWidth="2" fill="none" />
                <line x1="400" y1="380" x2="400" y2="90" stroke="rgba(255,90,31,0.4)" strokeWidth="1.5" />
                <ellipse cx="400" cy="235" rx="46" ry="32" stroke="rgba(255,90,31,0.4)" strokeWidth="1.5" fill="none" />
                {/* Pinned points */}
                {[[60,380],[740,380],[690,90],[110,90],[400,380],[400,90],[400,235]].map(([x,y], i) => (
                  <g key={i}>
                    <circle cx={x} cy={y} r="8" fill="var(--hot)" stroke="#000" strokeWidth="1.5" />
                    <text x={x+12} y={y+4} fill="var(--hot)" fontFamily="var(--f-mono)" fontSize="10" fontWeight="700">{i+1}</text>
                  </g>
                ))}
              </svg>
              <div style={{ position: "absolute", top: 10, left: 12, padding: "3px 8px", background: "rgba(0,0,0,0.7)", fontFamily: "var(--f-mono)", fontSize: 10, color: "var(--hot)", letterSpacing: 1 }}>
                NEXT — paint_L_TR
              </div>
              <div style={{ position: "absolute", top: 10, right: 12, padding: "3px 8px", background: "rgba(0,0,0,0.7)", fontFamily: "var(--f-mono)", fontSize: 10, color: "var(--fg-1)", letterSpacing: 1 }}>
                <span style={{ color: "var(--hot)", fontWeight: 700 }}>{setCount}</span> / 13 POINTS
              </div>
            </div>
            {/* Mini map + standard */}
            <div style={{ display: "grid", gridTemplateColumns: "1fr auto", gap: 12, marginTop: 14 }}>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr 1fr", gap: 1, background: "var(--line-2)" }}>
                {[
                  ["STD", "FIBA"],
                  ["LENGTH", "28.0 m"],
                  ["WIDTH", "15.0 m"],
                  ["SCALE", "28.6 px/m"],
                ].map(([k, v], i) => (
                  <div key={i} style={{ background: "var(--bg-1)", padding: "10px 12px" }}>
                    <div style={{ fontFamily: "var(--f-mono)", fontSize: 9, color: "var(--fg-3)", letterSpacing: 1 }}>{k}</div>
                    <div style={{ fontFamily: "var(--f-display)", fontSize: 14, fontWeight: 700, marginTop: 2 }}>{v}</div>
                  </div>
                ))}
              </div>
              <button className="cv-btn">RESET</button>
            </div>
          </EdPanel>

          {/* Right — keypoint list */}
          <EdPanel kicker="KEYPOINT LIST" title="13 POINTS · CLICK TO PIN">
            {points.map(p => (
              <div key={p.id} style={{
                display: "grid", gridTemplateColumns: "20px 24px 1fr 60px", padding: "10px 0",
                borderBottom: "1px solid var(--line-1)", alignItems: "center",
                opacity: p.set ? 1 : 0.6
              }}>
                <span style={{ color: p.set ? "var(--good)" : "var(--fg-3)", fontFamily: "var(--f-mono)" }}>
                  {p.set ? "●" : "○"}
                </span>
                <span style={{ color: "var(--fg-3)", fontFamily: "var(--f-mono)", fontSize: 11 }}>{String(p.id).padStart(2, "0")}</span>
                <span style={{ fontFamily: "var(--f-mono)", fontSize: 12, color: p.set ? "var(--fg-0)" : "var(--fg-1)", letterSpacing: 0.5 }}>{p.name}</span>
                <span style={{ fontFamily: "var(--f-mono)", fontSize: 10, color: p.err ? (p.err < 0.25 ? "var(--good)" : "var(--warn)") : "var(--fg-3)", textAlign: "right" }}>
                  {p.err ? `${p.err}px` : "—"}
                </span>
              </div>
            ))}
          </EdPanel>
        </div>
      </div>
    </div>
  );
}

// ---------- SETTINGS ----------
function CvSettingsScreen() {
  return (
    <div style={{ background: "var(--bg-1)", color: "var(--fg-0)", height: "100%", display: "flex", flexDirection: "column", overflow: "hidden" }}>
      <TopNav active="settings" />
      <div style={{ flex: 1, overflow: "auto" }}>
        <EdHero
          size="sm"
          issue="CFG · 001"
          tag="good" tagText="SETTINGS"
          kicker="OPERATOR PROFILE · ENGINE · BROADCAST"
          title={{ primary: "EVERY KNOB,", accent: "ON ONE PAGE." }}
          subline={[
            { k: "OPERATOR", v: "operator@spoin.kr" },
            { k: "ROLE", v: "ADMIN" },
            { k: "VENUE", v: "OLYMPIC PARK · COURT 03" },
          ]}
        />

        <div style={{ display: "grid", gridTemplateColumns: "240px 1fr", gap: 1, background: "var(--line-2)", minHeight: 600 }}>
          {/* Sidebar */}
          <div style={{ background: "var(--bg-1)", padding: "20px 0" }}>
            {[
              ["ACCOUNT", true],
              ["ENGINE", false],
              ["BROADCAST", false],
              ["NOTIFICATIONS", false],
              ["INTEGRATIONS", false],
              ["DANGER ZONE", false],
            ].map(([label, active], i) => (
              <div key={i} style={{
                padding: "12px 28px",
                borderLeft: active ? "2px solid var(--hot)" : "2px solid transparent",
                background: active ? "var(--bg-2)" : "transparent",
                fontFamily: "var(--f-mono)", fontSize: 11, fontWeight: 600,
                color: active ? "var(--fg-0)" : "var(--fg-2)",
                letterSpacing: 1.2, cursor: "pointer"
              }}>{label}</div>
            ))}
          </div>

          {/* Form */}
          <div style={{ background: "var(--bg-1)", padding: "32px 40px" }}>
            <EdSectionHead kicker="ACCOUNT · 01" title="OPERATOR PROFILE" sub="Identity, language & display preferences." />

            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 24 }}>
              <SetField label="DISPLAY NAME" value="JOON SUH" />
              <SetField label="EMAIL" value="operator@spoin.kr" />
              <SetField label="ROLE" value="ADMIN" readOnly />
              <SetField label="VENUE" value="OLYMPIC PARK · COURT 03" />
              <SetField label="LANGUAGE" value="ENGLISH (US)" select />
              <SetField label="TIMEZONE" value="ASIA/SEOUL · UTC+09" select />
            </div>

            <div style={{ marginTop: 36 }}>
              <EdSectionHead kicker="ACCOUNT · 02" title="DISPLAY" sub="Theme & density." />
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 12 }}>
                {["DENSE", "COMFORT", "SPACIOUS"].map((d, i) => (
                  <div key={i} style={{
                    padding: "16px 18px",
                    background: i === 0 ? "var(--bg-2)" : "transparent",
                    border: i === 0 ? "1px solid var(--hot)" : "1px solid var(--line-2)",
                    cursor: "pointer"
                  }}>
                    <div style={{ fontFamily: "var(--f-mono)", fontSize: 10, color: i === 0 ? "var(--hot)" : "var(--fg-3)", letterSpacing: 1 }}>0{i + 1}</div>
                    <div style={{ fontFamily: "var(--f-display)", fontSize: 16, fontWeight: 700, marginTop: 4 }}>{d}</div>
                    <div style={{ fontFamily: "var(--f-mono)", fontSize: 10, color: "var(--fg-2)", marginTop: 6, lineHeight: 1.5 }}>
                      {i === 0 ? "Maximum data per screen. Operator default." : i === 1 ? "Balanced. Daily use." : "Generous spacing. Demo mode."}
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <div style={{ display: "flex", gap: 8, marginTop: 32, paddingTop: 20, borderTop: "1px solid var(--line-2)" }}>
              <span style={{ flex: 1 }}></span>
              <button className="cv-btn">DISCARD</button>
              <button className="cv-btn primary">SAVE CHANGES</button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function SetField({ label, value, readOnly, select }) {
  return (
    <div>
      <label style={{ fontFamily: "var(--f-mono)", fontSize: 10, color: "var(--fg-2)", letterSpacing: 1.5 }}>{label}</label>
      <div style={{
        marginTop: 6, padding: "12px 14px",
        background: readOnly ? "var(--bg-1)" : "var(--bg-2)",
        border: "1px solid var(--line-2)",
        fontFamily: "var(--f-mono)", fontSize: 13,
        color: readOnly ? "var(--fg-2)" : "var(--fg-0)",
        display: "flex", justifyContent: "space-between", alignItems: "center"
      }}>
        <span>{value}</span>
        {select && <span style={{ color: "var(--fg-3)" }}>▾</span>}
      </div>
    </div>
  );
}

// ---------- RESULT ----------
function CvResultScreen() {
  const allGames = [
    { d: "2026-05-07", h: "FALCONS",  a: "TITANS",   hs: 78, as: 64, mode: "LIVE",  st: "DONE", lg: "FIBA", venue: "Olympic Park" },
    { d: "2026-05-07", h: "VOLTS",    a: "BLAZERS",  hs: 41, as: 38, mode: "LIVE",  st: "Q3 · LIVE", lg: "KBL", venue: "Gocheok Sky" },
    { d: "2026-05-06", h: "STORM",    a: "RIDERS",   hs: 82, as: 79, mode: "LIVE",  st: "DONE", lg: "FIBA", venue: "Busan Asiad" },
    { d: "2026-05-06", h: "FALCONS",  a: "PHANTOMS", hs: 91, as: 70, mode: "BATCH", st: "DONE", lg: "FIBA", venue: "Olympic Park" },
    { d: "2026-05-05", h: "BLAZERS",  a: "CRUSADERS",hs: 88, as: 85, mode: "LIVE",  st: "DONE", lg: "KBL", venue: "Incheon Arena" },
    { d: "2026-05-05", h: "VOLTS",    a: "TITANS",   hs: 95, as: 67, mode: "LIVE",  st: "DONE", lg: "KBL", venue: "Gocheok Sky" },
    { d: "2026-05-04", h: "STORM",    a: "FALCONS",  hs: 71, as: 84, mode: "BATCH", st: "DONE", lg: "FIBA", venue: "Olympic Park" },
    { d: "2026-05-04", h: "RIDERS",   a: "VOLTS",    hs: 66, as: 89, mode: "LIVE",  st: "DONE", lg: "KBL", venue: "Gocheok Sky" },
    { d: "2026-05-03", h: "PHANTOMS", a: "CRUSADERS",hs: 73, as: 73, mode: "LIVE",  st: "DONE", lg: "NBL", venue: "Jeju Municipal" },
    { d: "2026-05-03", h: "BLAZERS",  a: "STORM",    hs: 90, as: 81, mode: "LIVE",  st: "DONE", lg: "KBL", venue: "Incheon Arena" },
  ];

  const allTeams = ["FALCONS","TITANS","VOLTS","BLAZERS","STORM","RIDERS","PHANTOMS","CRUSADERS"];
  const [mode, setMode]     = React.useState("ALL");
  const [team, setTeam]     = React.useState("ALL");
  const [outcome, setOut]   = React.useState("ALL"); // ALL · WINS · LOSSES · 1POSS
  const [date, setDate]     = React.useState("ALL"); // ALL · 7D · 3D · 1D
  const [margin, setMargin] = React.useState(40);     // 0-40
  const [search, setSearch] = React.useState("");

  const today = new Date("2026-05-07");
  const filtered = allGames.filter(g => {
    if (mode !== "ALL" && g.mode !== mode) return false;
    if (team !== "ALL" && g.h !== team && g.a !== team) return false;
    const m = Math.abs(g.hs - g.as);
    if (m > margin) return false;
    if (outcome === "1POSS" && m > 3) return false;
    if (outcome === "WINS" && team !== "ALL") {
      const won = (g.h === team && g.hs > g.as) || (g.a === team && g.as > g.hs);
      if (!won) return false;
    }
    if (outcome === "LOSSES" && team !== "ALL") {
      const lost = (g.h === team && g.hs < g.as) || (g.a === team && g.as < g.hs);
      if (!lost) return false;
    }
    if (date !== "ALL") {
      const days = (today - new Date(g.d)) / 86400000;
      if (date === "1D" && days > 1) return false;
      if (date === "3D" && days > 3) return false;
      if (date === "7D" && days > 7) return false;
    }
    if (search) {
      const q = search.toUpperCase();
      if (!g.h.includes(q) && !g.a.includes(q) && !g.venue.toUpperCase().includes(q)) return false;
    }
    return true;
  });

  const reset = () => { setMode("ALL"); setTeam("ALL"); setOut("ALL"); setDate("ALL"); setMargin(40); setSearch(""); };
  const activeCount = (mode!=="ALL"?1:0)+(team!=="ALL"?1:0)+(outcome!=="ALL"?1:0)+(date!=="ALL"?1:0)+(margin<40?1:0)+(search?1:0);

  return (
    <div style={{ background: "var(--bg-1)", color: "var(--fg-0)", height: "100%", display: "flex", flexDirection: "column", overflow: "hidden" }}>
      <TopNav active="result" />
      <div style={{ flex: 1, overflow: "auto" }}>
        <EdHero
          issue="RES · 028"
          tag="hot" tagText="RESULTS"
          kicker="EVERY GAME, EVERY BOX SCORE, EVERY TREND"
          title={{ primary: "THE RECORD", accent: "BOOK." }}
          subline={[
            { k: "GAMES ANALYZED", v: "28 of 28" },
            { k: "AVG. POSSESSIONS", v: "78.4 / game" },
            { k: "AVG. PACE", v: "94.6" },
          ]}
          right={<button className="cv-btn">EXPORT ALL · CSV</button>}
        />

        <EdStatStrip items={[
          { k: "TOTAL GAMES", v: 28 },
          { k: "TODAY", v: 4, c: "var(--hot)" },
          { k: "AVG. PPG", v: "76.4" },
          { k: "BIGGEST WIN", v: "+27", sub: "VOLTS d. TITANS" },
          { k: "CLOSEST", v: "+1", sub: "STORM v. BLAZERS" },
        ]} />

        {/* C9 Filter rail */}
        <div style={{ padding: "16px 48px", borderBottom: "1px solid var(--line-2)", display: "flex", flexDirection: "column", gap: 12 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
            <span style={{ fontFamily: "var(--f-mono)", fontSize: 10, color: "var(--fg-2)", letterSpacing: 1.5 }}>FILTER —</span>

            <FilterPill label="MODE"    options={["ALL","LIVE","BATCH"]} value={mode} onChange={setMode} />
            <FilterPill label="DATE"    options={["ALL","1D","3D","7D"]} value={date} onChange={setDate} />
            <FilterPill label="OUTCOME" options={["ALL","WINS","LOSSES","1POSS"]} value={outcome} onChange={setOut} />

            {/* Team select */}
            <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
              <span style={{ fontFamily: "var(--f-mono)", fontSize: 9, color: "var(--fg-3)", letterSpacing: 1 }}>TEAM</span>
              <select value={team} onChange={e => setTeam(e.target.value)} style={{ height: 28, background: "var(--bg-2)", border: "1px solid var(--line-2)", color: "var(--fg-0)", fontFamily: "var(--f-mono)", fontSize: 10, letterSpacing: 1, padding: "0 8px" }}>
                <option value="ALL">ALL TEAMS</option>
                {allTeams.map(t => <option key={t} value={t}>{t}</option>)}
              </select>
            </div>

            {/* Margin slider */}
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <span style={{ fontFamily: "var(--f-mono)", fontSize: 9, color: "var(--fg-3)", letterSpacing: 1 }}>MARGIN ≤</span>
              <input type="range" min="0" max="40" value={margin} onChange={e => setMargin(+e.target.value)} style={{ width: 100, accentColor: "var(--hot)" }} />
              <span style={{ fontFamily: "var(--f-mono)", fontSize: 11, color: "var(--hot)", letterSpacing: 0.5, minWidth: 32, fontWeight: 700 }}>{margin}</span>
            </div>

            <span style={{ flex: 1 }}></span>

            <input value={search} onChange={e => setSearch(e.target.value)} placeholder="TEAM, VENUE…" style={{
              width: 180, height: 28, background: "var(--bg-2)", border: "1px solid var(--line-2)",
              color: "var(--fg-0)", padding: "0 10px", fontFamily: "var(--f-mono)", fontSize: 11, letterSpacing: 0.5
            }} />
            {activeCount > 0 && (
              <button className="cv-btn ghost" onClick={reset} style={{ height: 28, fontSize: 10, color: "var(--bad)", borderColor: "var(--bad)" }}>✕ CLEAR ({activeCount})</button>
            )}
          </div>
          <div style={{ fontFamily: "var(--f-mono)", fontSize: 10, color: "var(--fg-3)", letterSpacing: 1.2 }}>
            SHOWING <span style={{ color: "var(--fg-0)", fontWeight: 700 }}>{filtered.length}</span> / {allGames.length} GAMES{activeCount > 0 ? ` · ${activeCount} FILTER${activeCount > 1 ? "S" : ""} ACTIVE` : ""}
          </div>
        </div>

        <EdPanel kicker="GAME LOG" title="ALL RESULTS" padding="28px 48px">
          {filtered.length === 0 ? (
            <window.EdEmptyState kicker="NO RESULTS" title="필터에 맞는 경기가 없어요" body="필터를 완화하거나 CLEAR 버튼을 눌러주세요." action={<button className="cv-btn primary" onClick={reset}>CLEAR FILTERS</button>} />
          ) : filtered.map((g, i) => (
            <a key={i} href="#result-detail" style={{
              display: "grid", gridTemplateColumns: "100px 60px 1fr 60px 80px 60px 1fr 100px 80px",
              padding: "16px 0", borderBottom: "1px solid var(--line-1)", alignItems: "center", textDecoration: "none", color: "inherit"
            }}>
              <span style={{ fontFamily: "var(--f-mono)", fontSize: 11, color: "var(--fg-2)", letterSpacing: 0.5 }}>{g.d}</span>
              <span style={{ fontFamily: "var(--f-mono)", fontSize: 9, color: "var(--cool)", letterSpacing: 1 }}>{g.lg}</span>
              <span style={{ fontFamily: "var(--f-display)", fontSize: 18, fontWeight: 700, color: g.hs > g.as ? "var(--hot)" : "var(--fg-1)", letterSpacing: -0.3, textAlign: "right", paddingRight: 16 }}>{g.h}</span>
              <span style={{ fontFamily: "var(--f-display)", fontSize: 22, fontWeight: 700, color: g.hs > g.as ? "var(--hot)" : "var(--fg-2)", textAlign: "center" }}>{g.hs}</span>
              <span style={{ fontFamily: "var(--f-display)", fontSize: 14, fontWeight: 700, color: "var(--fg-3)", textAlign: "center", letterSpacing: 1 }}>—</span>
              <span style={{ fontFamily: "var(--f-display)", fontSize: 22, fontWeight: 700, color: g.as > g.hs ? "var(--hot)" : "var(--fg-2)", textAlign: "center" }}>{g.as}</span>
              <span style={{ fontFamily: "var(--f-display)", fontSize: 18, fontWeight: 700, color: g.as > g.hs ? "var(--hot)" : "var(--fg-1)", letterSpacing: -0.3, paddingLeft: 16 }}>{g.a}</span>
              <span style={{ textAlign: "center" }}>
                <span className={`cv-tag ${g.mode === "LIVE" ? "hot" : "cool"}`} style={{ fontSize: 9 }}>{g.mode}</span>
              </span>
              <span style={{ fontFamily: "var(--f-mono)", fontSize: 10, color: g.st.includes("LIVE") ? "var(--bad)" : "var(--good)", textAlign: "right", letterSpacing: 1, fontWeight: 700 }}>
                {g.st.includes("LIVE") && "● "}{g.st}
              </span>
            </a>
          ))}
        </EdPanel>
      </div>
    </div>
  );
}

function FilterPill({ label, options, value, onChange }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
      <span style={{ fontFamily: "var(--f-mono)", fontSize: 9, color: "var(--fg-3)", letterSpacing: 1, marginRight: 4 }}>{label}</span>
      {options.map(o => (
        <button key={o} onClick={() => onChange(o)}
          className={`cv-btn ${value === o ? "primary" : "ghost"}`}
          style={{ height: 24, fontSize: 9, padding: "0 8px", letterSpacing: 1 }}>
          {o}
        </button>
      ))}
    </div>
  );
}

window.CvLicenseScreen = CvLicenseScreen;
window.CvCalibrateScreen = CvCalibrateScreen;
window.CvSettingsScreen = CvSettingsScreen;
window.CvResultScreen = CvResultScreen;
