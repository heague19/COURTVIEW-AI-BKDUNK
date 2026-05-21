// =============================================================================
// COURTVIEW — Editorial supporting screens (set 1)
// Database, Equipment, Court, Referee
// =============================================================================

// ---------- DATABASE ----------
function CvDatabaseScreen() {
  const teams = [
    { num: "01", name: "FALCONS",   reg: "SEOUL · KR",   gp: 4, w: 4, l: 0, ppg: 78.0, opp: 62.0, league: "FIBA" },
    { num: "02", name: "VOLTS",     reg: "BUSAN · KR",   gp: 3, w: 3, l: 0, ppg: 80.3, opp: 66.0, league: "FIBA" },
    { num: "03", name: "STORM",     reg: "INCHEON · KR", gp: 3, w: 2, l: 1, ppg: 78.0, opp: 73.0, league: "KBL" },
    { num: "04", name: "BLAZERS",   reg: "DAEGU · KR",   gp: 4, w: 2, l: 2, ppg: 72.0, opp: 70.5, league: "FIBA" },
    { num: "05", name: "RIDERS",    reg: "GWANGJU · KR", gp: 3, w: 1, l: 2, ppg: 69.7, opp: 73.3, league: "KBL" },
    { num: "06", name: "TITANS",    reg: "DAEJEON · KR", gp: 4, w: 1, l: 3, ppg: 67.0, opp: 72.5, league: "NBL" },
    { num: "07", name: "CRUSADERS", reg: "ULSAN · KR",   gp: 4, w: 1, l: 3, ppg: 64.0, opp: 73.5, league: "FIBA" },
    { num: "08", name: "PHANTOMS",  reg: "JEJU · KR",    gp: 3, w: 0, l: 3, ppg: 66.0, opp: 85.0, league: "NBL" },
  ];
  const players = [
    { num: "#11", name: "K. PARK",  team: "VOLTS",   pos: "PG", ht: "188", pts: 24.3, reb: 5.7, ast: 8.1 },
    { num: "#7",  name: "M. HAN",   team: "BLAZERS", pos: "C",  ht: "204", pts: 18.5, reb: 11.2, ast: 1.9 },
    { num: "#23", name: "S. RYU",   team: "VOLTS",   pos: "SG", ht: "194", pts: 14.4, reb: 3.0, ast: 6.4 },
    { num: "#3",  name: "T. KO",    team: "BLAZERS", pos: "PF", ht: "201", pts: 12.1, reb: 8.4, ast: 2.1 },
    { num: "#9",  name: "M. SHIN",  team: "FALCONS", pos: "G",  ht: "184", pts: 11.8, reb: 2.8, ast: 5.1 },
    { num: "#33", name: "B. CHO",   team: "STORM",   pos: "F",  ht: "198", pts: 10.5, reb: 6.4, ast: 1.4 },
  ];
  return (
    <div style={{ background: "var(--bg-1)", color: "var(--fg-0)", height: "100%", display: "flex", flexDirection: "column", overflow: "hidden" }}>
      <TopNav active="database" />
      <div style={{ flex: 1, overflow: "auto" }}>
        <EdHero
          issue="DB · 014"
          tag="cool" tagText="DATABASE"
          kicker="ROSTERS · TEAMS · OFFICIALS · ALL-TIME RECORDS"
          title={{ primary: "ONE LIBRARY,", accent: "EVERY ROSTER." }}
          subline={[
            { k: "TEAMS", v: "84 active" },
            { k: "PLAYERS", v: "1,247" },
            { k: "REFS", v: "62" },
            { k: "VENUES", v: "31" },
          ]}
          right={
            <div style={{ display: "flex", gap: 8 }}>
              <button className="cv-btn">IMPORT CSV</button>
              <button className="cv-btn primary">+ NEW TEAM</button>
            </div>
          }
        />

        <EdStatStrip items={[
          { k: "ROSTER UPDATES · 7D", v: "23", c: "var(--good)" },
          { k: "PENDING APPROVAL", v: "4", c: "var(--warn)" },
          { k: "FREE AGENTS", v: "112", sub: "across 7 leagues" },
          { k: "AVG. ROSTER SIZE", v: "14.8", sub: "12-min, 18-max" },
          { k: "DATA QUALITY", v: "98.2%", c: "var(--good)", sub: "verified" },
        ]} />

        {/* Filters */}
        <div style={{ display: "flex", gap: 0, padding: "16px 48px", borderBottom: "1px solid var(--line-2)", alignItems: "center" }}>
          <span style={{ fontFamily: "var(--f-mono)", fontSize: 10, color: "var(--fg-2)", letterSpacing: 1.5, marginRight: 16 }}>FILTER —</span>
          {["ALL", "FIBA", "KBL", "NBL", "ARCHIVED"].map((f, i) => (
            <button key={i} className={`cv-btn ${i === 0 ? "primary" : "ghost"}`} style={{ marginRight: 6, height: 28 }}>{f}</button>
          ))}
          <span style={{ flex: 1 }}></span>
          <input placeholder="SEARCH TEAMS, PLAYERS, REFS…" style={{
            width: 320, height: 32, background: "var(--bg-2)", border: "1px solid var(--line-2)",
            color: "var(--fg-0)", padding: "0 12px", fontFamily: "var(--f-mono)", fontSize: 11, letterSpacing: 0.5
          }} />
        </div>

        {/* Two-pane: teams + players */}
        <div style={{ display: "grid", gridTemplateColumns: "1.3fr 1fr", gap: 1, background: "var(--line-2)" }}>
          <EdPanel kicker="TEAMS · 84 TOTAL" title="ROSTER INDEX" right={<span style={{ fontFamily: "var(--f-mono)", fontSize: 10, color: "var(--fg-3)" }}>SHOWING 8</span>}>
            <EdTable
              cols={[
                { k: "#", w: "32px" },
                { k: "TEAM", w: "1.2fr" },
                { k: "REGION", w: "1.4fr" },
                { k: "GP", w: "40px", align: "center" },
                { k: "W·L", w: "70px", align: "center" },
                { k: "PPG", w: "60px", align: "right" },
                { k: "OPP", w: "60px", align: "right" },
                { k: "LG", w: "50px", align: "right" },
              ]}
              rows={teams.map(t => [
                <span style={{ color: "var(--fg-3)", fontFamily: "var(--f-mono)", fontSize: 11 }}>{t.num}</span>,
                t.name,
                <span style={{ color: "var(--fg-2)", fontFamily: "var(--f-mono)", fontSize: 11 }}>{t.reg}</span>,
                t.gp,
                <span style={{ color: t.w > t.l ? "var(--good)" : t.l > t.w ? "var(--bad)" : "var(--fg-1)" }}>{t.w}·{t.l}</span>,
                t.ppg.toFixed(1),
                t.opp.toFixed(1),
                <span style={{ color: "var(--cool)" }}>{t.league}</span>,
              ])}
            />
          </EdPanel>

          <EdPanel kicker="PLAYERS · TOP 6 BY PPG" title="LEADERBOARD">
            {players.map((p, i) => (
              <PlayerRowHover key={i} p={p} i={i} />
            ))}
          </EdPanel>
        </div>
      </div>
    </div>
  );
}

// ---------- EQUIPMENT (CAMERAS) ----------
function CvEquipmentScreen() {
  const d = window.cvData;
  const cams = d.cameras;
  const live = cams.filter(c => c.status === "live").length;
  return (
    <div style={{ background: "var(--bg-1)", color: "var(--fg-0)", height: "100%", display: "flex", flexDirection: "column", overflow: "hidden" }}>
      <TopNav active="equipment" />
      <div style={{ flex: 1, overflow: "auto" }}>
        <EdHero
          size="md"
          issue="RIG · 008"
          tag="good" tagText="EQUIPMENT"
          kicker={`${cams.length} CAMERA RIG · OLYMPIC PARK · COURT 03`}
          title={{ primary: "EIGHT EYES,", accent: "ONE COURT." }}
          subline={[
            { k: "ENGINE", v: "tracker.gpu0 · RTX 4090" },
            { k: "STREAM", v: "RTSP · 60 FPS · 8 ch" },
            { k: "RECORD", v: "142 / 2000 GB" },
          ]}
          right={
            <div style={{ display: "flex", gap: 8 }}>
              <button className="cv-btn">DIAGNOSTIC</button>
              <button className="cv-btn primary">+ ADD CAMERA</button>
            </div>
          }
        />

        <EdStatStrip items={[
          { k: "LIVE STREAMS", v: `${live}/${cams.length}`, c: "var(--good)" },
          { k: "AVG. LATENCY", v: "10.6", sub: "ms · 60FPS" },
          { k: "TRACKING ERR", v: "0.31", c: "var(--good)", sub: "px / m" },
          { k: "GPU LOAD", v: "62%", c: "var(--warn)", sub: "RTX 4090 · 24GB" },
          { k: "VRAM", v: "14.2", sub: "/ 24 GB" },
          { k: "STORAGE", v: "7%", sub: "142 / 2000 GB" },
        ]} />

        {/* Camera grid */}
        <EdPanel kicker="LIVE FEEDS · CAMERA GRID" title="ALL CAMERAS"
          right={<span style={{ fontFamily: "var(--f-mono)", fontSize: 10, color: "var(--fg-3)" }}>CLICK TO CALIBRATE</span>}
          padding="28px 48px">
          <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 16 }}>
            {cams.map(c => (
              <div key={c.id} style={{ background: "var(--bg-2)", border: "1px solid var(--line-2)" }}>
                <div style={{ aspectRatio: "16/9", position: "relative", overflow: "hidden", background: "#000" }}>
                  <div style={{ position: "absolute", inset: 0,
                    background: c.status === "live"
                      ? `repeating-linear-gradient(45deg, transparent 0 14px, rgba(255,255,255,0.02) 14px 15px),
                         radial-gradient(ellipse at 50% 60%, rgba(255,90,31,0.06), transparent 60%)`
                      : "none",
                    opacity: c.status === "live" ? 1 : 0.25 }}></div>
                  <div style={{ position: "absolute", top: 8, left: 8, padding: "2px 6px", background: "rgba(0,0,0,0.7)",
                                fontFamily: "var(--f-mono)", fontSize: 10, fontWeight: 700, color: "var(--fg-0)", letterSpacing: 1 }}>
                    CAM{c.id} · {c.name}
                  </div>
                  <div style={{ position: "absolute", top: 8, right: 8, fontFamily: "var(--f-mono)", fontSize: 10,
                                color: c.status === "live" ? "var(--good)" : "var(--bad)", letterSpacing: 1 }}>
                    {c.status === "live" ? "● LIVE" : "✕ STALL"}
                  </div>
                  {c.status !== "live" && (
                    <div style={{ position: "absolute", inset: 0, display: "flex", alignItems: "center", justifyContent: "center",
                                  fontFamily: "var(--f-display)", fontSize: 22, fontWeight: 700, color: "var(--bad)", letterSpacing: 1 }}>
                      OFFLINE
                    </div>
                  )}
                </div>
                <div style={{ padding: "10px 12px", display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 8, borderTop: "1px solid var(--line-2)" }}>
                  <div><div style={{ fontFamily: "var(--f-mono)", fontSize: 9, color: "var(--fg-3)", letterSpacing: 1 }}>FPS</div>
                       <div style={{ fontFamily: "var(--f-mono)", fontSize: 13, fontWeight: 600, color: c.fps ? "var(--fg-0)" : "var(--fg-3)" }}>{c.fps || "—"}</div></div>
                  <div><div style={{ fontFamily: "var(--f-mono)", fontSize: 9, color: "var(--fg-3)", letterSpacing: 1 }}>MS</div>
                       <div style={{ fontFamily: "var(--f-mono)", fontSize: 13, fontWeight: 600, color: c.ms < 12 ? "var(--good)" : c.ms < 16 ? "var(--warn)" : "var(--fg-3)" }}>{c.ms || "—"}</div></div>
                  <div style={{ textAlign: "right" }}>
                    <button className="cv-btn ghost" style={{ height: 22, fontSize: 9, padding: "0 8px" }}>CALIB</button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </EdPanel>

        {/* System health */}
        <div style={{ display: "grid", gridTemplateColumns: "repeat(6, 1fr)", borderTop: "1px solid var(--line-2)" }}>
          {Object.entries(d.systemHealth).map(([k, v], i) => (
            <div key={i} style={{ padding: "16px 22px", borderRight: i < 5 ? "1px solid var(--line-1)" : "none" }}>
              <div style={{ fontFamily: "var(--f-mono)", fontSize: 10, color: "var(--fg-2)", letterSpacing: 1.2, textTransform: "uppercase" }}>{k}</div>
              <div style={{ fontFamily: "var(--f-mono)", fontSize: 14, color: "var(--fg-0)", marginTop: 6, fontWeight: 600 }}>{v}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// ---------- COURT (VENUES) ----------
function CvCourtScreen() {
  const venues = [
    { num: "01", name: "OLYMPIC PARK", city: "SEOUL", ct: 4, cap: 15000, std: "FIBA", live: true },
    { num: "02", name: "GOCHEOK SKY", city: "SEOUL", ct: 2, cap: 8000, std: "KBL", live: false },
    { num: "03", name: "BUSAN ASIAD", city: "BUSAN", ct: 3, cap: 12000, std: "FIBA", live: false },
    { num: "04", name: "INCHEON ARENA", city: "INCHEON", ct: 2, cap: 9500, std: "KBL", live: false },
    { num: "05", name: "JEJU MUNICIPAL", city: "JEJU", ct: 1, cap: 4200, std: "NBL", live: false },
  ];
  return (
    <div style={{ background: "var(--bg-1)", color: "var(--fg-0)", height: "100%", display: "flex", flexDirection: "column", overflow: "hidden" }}>
      <TopNav active="court" />
      <div style={{ flex: 1, overflow: "auto" }}>
        <EdHero
          size="md"
          issue="VEN · 005"
          tag="cool" tagText="VENUES"
          kicker="EVERY COURT, EVERY STANDARD, EVERY DIMENSION"
          title={{ primary: "FIVE VENUES.", accent: "TWELVE COURTS." }}
          subline={[
            { k: "STANDARDS", v: "FIBA · KBL · NBL · NBA" },
            { k: "ACTIVE", v: "1 venue · 1 court live" },
            { k: "ALL-TIME GAMES", v: "1,284" },
          ]}
        />
        <EdStatStrip items={[
          { k: "VENUES", v: 5, sub: "active" },
          { k: "TOTAL COURTS", v: 12 },
          { k: "CALIBRATED", v: "10/12", c: "var(--good)" },
          { k: "AVG. CAPACITY", v: "9,740", sub: "seats" },
          { k: "REGIONS", v: 5, sub: "KR · domestic" },
        ]} />

        <div style={{ display: "grid", gridTemplateColumns: "1.4fr 1fr", gap: 1, background: "var(--line-2)" }}>
          <EdPanel kicker="VENUE INDEX" title="ALL FACILITIES"
            right={<button className="cv-btn primary" style={{ height: 26, fontSize: 10 }}>+ ADD VENUE</button>}>
            <EdTable
              cols={[
                { k: "#", w: "32px" },
                { k: "VENUE", w: "1.5fr" },
                { k: "CITY", w: "1fr" },
                { k: "COURTS", w: "60px", align: "center" },
                { k: "CAPACITY", w: "80px", align: "right" },
                { k: "STANDARD", w: "70px", align: "right" },
                { k: "STATUS", w: "80px", align: "right" },
              ]}
              rows={venues.map(v => [
                <span style={{ color: "var(--fg-3)", fontFamily: "var(--f-mono)" }}>{v.num}</span>,
                v.name,
                <span style={{ color: "var(--fg-2)", fontFamily: "var(--f-mono)", fontSize: 11 }}>{v.city}</span>,
                v.ct,
                v.cap.toLocaleString(),
                <span style={{ color: "var(--cool)" }}>{v.std}</span>,
                v.live
                  ? <span className="cv-tag live" style={{ fontSize: 9 }}>LIVE</span>
                  : <span style={{ fontFamily: "var(--f-mono)", fontSize: 10, color: "var(--fg-3)", letterSpacing: 1 }}>STANDBY</span>,
              ])}
            />
          </EdPanel>

          {/* Featured venue + court diagram */}
          <EdPanel kicker="FEATURED · LIVE NOW" title="OLYMPIC PARK · COURT 03">
            {/* Court diagram */}
            <div style={{ aspectRatio: "16/9", background: "var(--bg-2)", border: "1px solid var(--line-2)", position: "relative", overflow: "hidden", padding: 24 }}>
              <svg viewBox="0 0 280 150" style={{ width: "100%", height: "100%", display: "block" }}>
                <rect x="2" y="2" width="276" height="146" stroke="var(--hot)" strokeWidth="1.5" fill="none" />
                <line x1="140" y1="2" x2="140" y2="148" stroke="var(--hot)" strokeWidth="1" />
                <circle cx="140" cy="75" r="14" stroke="var(--hot)" strokeWidth="1" fill="none" />
                <rect x="2" y="48" width="56" height="54" stroke="var(--hot)" strokeWidth="1" fill="none" opacity="0.7" />
                <rect x="222" y="48" width="56" height="54" stroke="var(--hot)" strokeWidth="1" fill="none" opacity="0.7" />
                <path d="M 2 30 A 50 50 0 0 1 2 120" stroke="var(--hot)" strokeWidth="1" fill="none" opacity="0.5" />
                <path d="M 278 30 A 50 50 0 0 0 278 120" stroke="var(--hot)" strokeWidth="1" fill="none" opacity="0.5" />
                {/* Camera positions */}
                {[[10,10,"C1"],[270,10,"C2"],[10,140,"C3"],[270,140,"C4"],[140,4,"C5"],[140,146,"C6"]].map(([x,y,n], i) => (
                  <g key={i}>
                    <rect x={x-5} y={y-5} width="10" height="10" fill="var(--cool)" />
                    <text x={x+8} y={y+3} fill="var(--cool)" fontFamily="var(--f-mono)" fontSize="7">{n}</text>
                  </g>
                ))}
              </svg>
              <div style={{ position: "absolute", top: 12, left: 16, fontFamily: "var(--f-mono)", fontSize: 10, color: "var(--fg-2)", letterSpacing: 1 }}>
                FIBA · 28m × 15m · 6 CAM PERIMETER
              </div>
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 1, background: "var(--line-2)", marginTop: 16 }}>
              {[
                ["LENGTH", "28.0 m"],
                ["WIDTH", "15.0 m"],
                ["3PT LINE", "6.75 m"],
                ["FREE THROW", "5.80 m"],
                ["RIM HEIGHT", "3.05 m"],
                ["KEY ZONE", "4.90 m²"],
              ].map(([k, v], i) => (
                <div key={i} style={{ background: "var(--bg-1)", padding: "10px 12px" }}>
                  <div style={{ fontFamily: "var(--f-mono)", fontSize: 9, color: "var(--fg-3)", letterSpacing: 1 }}>{k}</div>
                  <div style={{ fontFamily: "var(--f-display)", fontSize: 16, fontWeight: 700, color: "var(--fg-0)", marginTop: 2 }}>{v}</div>
                </div>
              ))}
            </div>
          </EdPanel>
        </div>
      </div>
    </div>
  );
}

// ---------- REFEREE (OFFICIALS) ----------
function CvRefereeScreen() {
  const refs = [
    { num: "01", name: "J. KANG",  cert: "FIBA · L1", yrs: 14, gms: 287, last: "2026-05-06", rating: 4.9 },
    { num: "02", name: "P. CHOI",  cert: "FIBA · L2", yrs: 9,  gms: 162, last: "2026-05-05", rating: 4.7 },
    { num: "03", name: "H. LEE",   cert: "KBL",      yrs: 18, gms: 412, last: "2026-05-04", rating: 4.8 },
    { num: "04", name: "D. SONG",  cert: "FIBA · L1", yrs: 11, gms: 234, last: "2026-05-06", rating: 4.6 },
    { num: "05", name: "Y. JEONG", cert: "NBL",      yrs: 6,  gms: 98,  last: "2026-04-28", rating: 4.4 },
    { num: "06", name: "E. NOH",   cert: "KBL",      yrs: 12, gms: 251, last: "2026-05-07", rating: 4.7 },
  ];
  return (
    <div style={{ background: "var(--bg-1)", color: "var(--fg-0)", height: "100%", display: "flex", flexDirection: "column", overflow: "hidden" }}>
      <TopNav active="referee" />
      <div style={{ flex: 1, overflow: "auto" }}>
        <EdHero
          size="md"
          issue="OFF · 003"
          tag="cool" tagText="OFFICIALS"
          kicker="CERTIFIED REFEREES · RATING & SCHEDULE"
          title={{ primary: "EVERY CALL,", accent: "EVERY GAME." }}
          subline={[
            { k: "OFFICIALS", v: "62 active" },
            { k: "TODAY", v: "12 assigned" },
            { k: "AVG. RATING", v: "4.7 / 5.0" },
          ]}
          right={<button className="cv-btn primary">+ NEW OFFICIAL</button>}
        />

        <EdStatStrip items={[
          { k: "ACTIVE", v: 62, sub: "certified" },
          { k: "TODAY ASSIGNED", v: 12, c: "var(--good)" },
          { k: "FIBA L1/L2", v: "28", sub: "international" },
          { k: "AVG. EXPERIENCE", v: "11.4", sub: "years" },
          { k: "FLAGGED", v: "2", c: "var(--warn)", sub: "review pending" },
        ]} />

        <EdPanel kicker="OFFICIALS DIRECTORY · TOP 6" title="REGISTRY" padding="28px 48px">
          <EdTable
            cols={[
              { k: "#", w: "40px" },
              { k: "NAME", w: "1.4fr" },
              { k: "CERTIFICATION", w: "1.2fr" },
              { k: "YRS", w: "60px", align: "center" },
              { k: "GAMES", w: "80px", align: "right" },
              { k: "LAST CALLED", w: "120px", align: "right" },
              { k: "RATING", w: "100px", align: "right" },
              { k: "ACTION", w: "80px", align: "right" },
            ]}
            rows={refs.map(r => [
              <span style={{ fontFamily: "var(--f-mono)", color: "var(--fg-3)" }}>{r.num}</span>,
              r.name,
              <span style={{ color: r.cert.startsWith("FIBA") ? "var(--cool)" : "var(--fg-1)", fontFamily: "var(--f-mono)", fontSize: 11 }}>{r.cert}</span>,
              r.yrs,
              r.gms,
              <span style={{ color: "var(--fg-2)", fontFamily: "var(--f-mono)", fontSize: 11 }}>{r.last}</span>,
              <span style={{ color: r.rating >= 4.7 ? "var(--good)" : "var(--fg-1)", fontWeight: 700 }}>★ {r.rating.toFixed(1)}</span>,
              <button className="cv-btn ghost" style={{ height: 22, fontSize: 9 }}>EDIT →</button>,
            ])}
          />
        </EdPanel>
      </div>
    </div>
  );
}

// ---------- Player row with hover card (B7) ----------
function PlayerRowHover({ p, i }) {
  const [hover, setHover] = React.useState(false);
  // deterministic last-5 game line based on player number
  const seed = (p.num * 7 + (p.name?.length || 0) * 3) % 100;
  const last5 = React.useMemo(() => {
    let r = seed + 11;
    const rand = () => { r = (r * 1103515245 + 12345) & 0x7fffffff; return (r % 1000) / 1000; };
    return [0, 1, 2, 3, 4].map(() => Math.round(p.pts * (0.65 + rand() * 0.55)));
  }, [p]);
  const last5Max = Math.max(...last5, 1);
  const initials = (p.name || "").split(/[ .]+/).filter(Boolean).slice(0, 2).map(x => x[0]).join("");

  return (
    <div
      style={{ position: "relative" }}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
    >
      <div style={{
        display: "grid", gridTemplateColumns: "32px 56px 1fr 70px 50px 50px 50px",
        padding: "14px 0", borderBottom: "1px solid var(--line-1)", alignItems: "center",
        background: hover ? "var(--bg-2)" : "transparent",
        transition: "background 120ms ease",
        cursor: "pointer"
      }}>
        <span style={{ fontFamily: "var(--f-mono)", fontSize: 11, color: i < 3 ? "var(--hot)" : "var(--fg-3)", fontWeight: 700, paddingLeft: hover ? 6 : 0, transition: "padding 120ms ease" }}>0{i + 1}</span>
        <span style={{ fontFamily: "var(--f-display)", fontSize: 14, color: "var(--hot)", fontWeight: 700 }}>{p.num}</span>
        <span>
          <div style={{ fontFamily: "var(--f-display)", fontSize: 15, fontWeight: 700, letterSpacing: -0.2 }}>{p.name}</div>
          <div style={{ fontFamily: "var(--f-mono)", fontSize: 10, color: "var(--fg-3)", marginTop: 2, letterSpacing: 0.8 }}>{p.team} · {p.pos} · {p.ht}cm</div>
        </span>
        <span style={{ fontFamily: "var(--f-display)", fontSize: 22, fontWeight: 700, color: "var(--hot)", textAlign: "right", letterSpacing: -0.5 }}>{p.pts}</span>
        <span style={{ fontFamily: "var(--f-mono)", fontSize: 11, color: "var(--fg-1)", textAlign: "right" }}>{p.reb}r</span>
        <span style={{ fontFamily: "var(--f-mono)", fontSize: 11, color: "var(--fg-1)", textAlign: "right" }}>{p.ast}a</span>
        <span style={{ textAlign: "right" }}>
          <button className="cv-btn ghost" style={{ height: 24, fontSize: 10 }}>VIEW</button>
        </span>
      </div>

      {hover && (
        <div style={{
          position: "absolute",
          top: "100%", right: 0,
          marginTop: -1,
          width: 420,
          zIndex: 30,
          background: "var(--bg-1)",
          border: "1px solid var(--hot)",
          boxShadow: "0 24px 60px -10px rgba(0,0,0,0.7), 0 0 0 1px rgba(255,90,31,0.15)",
          padding: 18,
          animation: "cvCardIn 140ms ease-out",
          pointerEvents: "none",
        }}>
          {/* Top — portrait swatch + identity */}
          <div style={{ display: "flex", gap: 14, alignItems: "stretch", marginBottom: 14 }}>
            <div style={{
              width: 72, height: 92, flexShrink: 0,
              background: `linear-gradient(165deg, rgba(255,90,31,0.4), rgba(255,90,31,0.05) 60%, var(--bg-3))`,
              border: "1px solid var(--line-2)",
              display: "flex", alignItems: "flex-end", justifyContent: "center",
              fontFamily: "var(--f-display)", fontSize: 30, fontWeight: 700, color: "rgba(255,255,255,0.9)",
              letterSpacing: -1, paddingBottom: 6, position: "relative", overflow: "hidden",
            }}>
              <span style={{ position: "absolute", top: 6, right: 6, fontFamily: "var(--f-mono)", fontSize: 9, color: "var(--hot)", letterSpacing: 1 }}>#{p.num}</span>
              {initials}
            </div>
            <div style={{ flex: 1, display: "flex", flexDirection: "column", justifyContent: "space-between" }}>
              <div>
                <div style={{ fontFamily: "var(--f-mono)", fontSize: 9, color: "var(--fg-3)", letterSpacing: 1.5 }}>PLAYER PROFILE</div>
                <div style={{ fontFamily: "var(--f-display)", fontSize: 22, fontWeight: 700, letterSpacing: -0.5, marginTop: 2, lineHeight: 1.05 }}>{p.name}</div>
                <div style={{ fontFamily: "var(--f-mono)", fontSize: 10, color: "var(--fg-2)", marginTop: 4, letterSpacing: 0.8 }}>{p.team} · {p.pos} · {p.ht} cm</div>
              </div>
              <div style={{ display: "flex", gap: 6, marginTop: 6 }}>
                <span style={{ padding: "2px 6px", border: "1px solid var(--good)", color: "var(--good)", fontFamily: "var(--f-mono)", fontSize: 9, letterSpacing: 1 }}>ACTIVE</span>
                <span style={{ padding: "2px 6px", border: "1px solid var(--line-2)", color: "var(--fg-2)", fontFamily: "var(--f-mono)", fontSize: 9, letterSpacing: 1 }}>FIBA</span>
                <span style={{ padding: "2px 6px", border: "1px solid var(--line-2)", color: "var(--fg-2)", fontFamily: "var(--f-mono)", fontSize: 9, letterSpacing: 1 }}>SR · 7Y</span>
              </div>
            </div>
          </div>

          {/* Stat row */}
          <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 1, background: "var(--line-2)", marginBottom: 14 }}>
            {[
              { k: "PTS", v: p.pts, c: "var(--hot)" },
              { k: "REB", v: p.reb, c: "var(--fg-0)" },
              { k: "AST", v: p.ast, c: "var(--fg-0)" },
              { k: "EFF", v: Math.round(p.pts * 1.1 + p.reb + p.ast * 1.5), c: "var(--warn)" },
            ].map((s, j) => (
              <div key={j} style={{ background: "var(--bg-2)", padding: "10px 8px", textAlign: "center" }}>
                <div style={{ fontFamily: "var(--f-mono)", fontSize: 9, color: "var(--fg-3)", letterSpacing: 1.2 }}>{s.k}</div>
                <div style={{ fontFamily: "var(--f-display)", fontSize: 22, fontWeight: 700, color: s.c, marginTop: 2 }}>{s.v}</div>
              </div>
            ))}
          </div>

          {/* Last 5 games */}
          <div style={{ marginBottom: 12 }}>
            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6 }}>
              <span style={{ fontFamily: "var(--f-mono)", fontSize: 9, color: "var(--fg-3)", letterSpacing: 1.5 }}>LAST 5 GAMES · PTS</span>
              <span style={{ fontFamily: "var(--f-mono)", fontSize: 9, color: "var(--fg-2)" }}>AVG {Math.round(last5.reduce((a,b)=>a+b,0)/last5.length)}</span>
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(5, 1fr)", gap: 4, alignItems: "end", height: 50 }}>
              {last5.map((v, j) => (
                <div key={j} style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 3 }}>
                  <div style={{ fontFamily: "var(--f-mono)", fontSize: 9, color: "var(--fg-2)" }}>{v}</div>
                  <div style={{ width: "100%", height: `${(v/last5Max) * 36}px`, background: "var(--hot)", opacity: 0.4 + (v/last5Max) * 0.6 }}></div>
                </div>
              ))}
            </div>
          </div>

          {/* Footer hint */}
          <div style={{ fontFamily: "var(--f-mono)", fontSize: 9, color: "var(--fg-3)", letterSpacing: 1.2, paddingTop: 8, borderTop: "1px solid var(--line-2)", display: "flex", justifyContent: "space-between" }}>
            <span>CLICK ROW · OPEN FULL PROFILE</span>
            <span style={{ color: "var(--hot)" }}>↗</span>
          </div>
        </div>
      )}
    </div>
  );
}

window.CvDatabaseScreen = CvDatabaseScreen;
window.CvEquipmentScreen = CvEquipmentScreen;
window.CvCourtScreen = CvCourtScreen;
window.CvRefereeScreen = CvRefereeScreen;
