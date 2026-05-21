// =============================================================================
// COURTVIEW — Analysis screen (dense / operator mode)
// One option, applies the new system. Camera grid + control panel.
// =============================================================================

function CvAnalysisScreen() {
  const d = window.cvData;
  const [selectedCam, setSelectedCam] = React.useState(0);
  const [tab, setTab] = React.useState("control");

  return (
    <div style={{ background: "var(--bg-1)", color: "var(--fg-0)", height: "100%", display: "flex", flexDirection: "column", overflow: "hidden" }}>
      <TopNav active="analysis" />

      {/* Mini live HUD — always-visible game state */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr auto 1fr auto auto auto", alignItems: "center", padding: "8px 16px",
                    background: "var(--bg-0)", borderBottom: "1px solid var(--line-2)", gap: 16 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12, justifyContent: "flex-end" }}>
          <span style={{ fontFamily: "var(--f-display)", fontSize: 20, fontWeight: 700 }}>VOLTS</span>
          <span style={{ fontFamily: "var(--f-mono)", fontSize: 32, fontWeight: 700, color: "var(--hot)", letterSpacing: -1 }}>41</span>
        </div>
        <div style={{ fontFamily: "var(--f-display)", fontSize: 16, color: "var(--fg-3)", fontWeight: 700 }}>:</div>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <span style={{ fontFamily: "var(--f-mono)", fontSize: 32, fontWeight: 700, color: "var(--cool)", letterSpacing: -1 }}>38</span>
          <span style={{ fontFamily: "var(--f-display)", fontSize: 20, fontWeight: 700 }}>BLAZERS</span>
        </div>
        <span className="cv-tag live"><span style={{ width: 6, height: 6, background: "var(--bad)", borderRadius: "50%" }}></span> Q3</span>
        <span style={{ fontFamily: "var(--f-mono)", fontSize: 18, fontWeight: 700, color: "var(--warn)" }}>07:24</span>
        <span style={{ fontFamily: "var(--f-mono)", fontSize: 14, fontWeight: 700, color: "var(--bad)" }}>SC 14</span>
      </div>

      <div style={{ flex: 1, display: "grid", gridTemplateColumns: "minmax(0, 1.4fr) 380px", gap: 1, background: "var(--line-2)", overflow: "hidden" }}>

        {/* Camera section */}
        <div style={{ background: "var(--bg-1)", padding: 12, display: "flex", flexDirection: "column", gap: 8, minHeight: 0 }}>
          <div style={{ flex: 1, background: "var(--bg-0)", border: "1px solid var(--line-2)", position: "relative", display: "flex", alignItems: "center", justifyContent: "center", overflow: "hidden", minHeight: 0 }}>
            {/* Placeholder feed */}
            <div style={{ position: "absolute", inset: 0,
              background: `repeating-linear-gradient(45deg, transparent 0 18px, rgba(255,255,255,0.015) 18px 19px),
                           radial-gradient(ellipse at 50% 60%, rgba(255,90,31,0.08), transparent 60%)` }}></div>
            <div style={{ textAlign: "center", color: "var(--fg-3)", fontFamily: "var(--f-mono)", fontSize: 11 }}>
              <Pict.Camera size={36} stroke="var(--fg-3)" strokeWidth={1.2} />
              <div style={{ marginTop: 12 }}>CAM{selectedCam + 1} · {d.cameras[selectedCam].name}</div>
              <div style={{ marginTop: 4, color: "var(--fg-2)" }}>1920 × 1080 · {d.cameras[selectedCam].fps}FPS · {d.cameras[selectedCam].ms}MS</div>
            </div>
            {/* Corner labels */}
            <div style={{ position: "absolute", top: 10, left: 10, padding: "3px 8px", background: "rgba(0,0,0,0.7)", border: "1px solid var(--line-3)", fontFamily: "var(--f-mono)", fontSize: 10, fontWeight: 700, letterSpacing: 1, color: "var(--fg-0)" }}>
              CAM{selectedCam + 1} · {d.cameras[selectedCam].name}
            </div>
            <div style={{ position: "absolute", top: 10, right: 10, padding: "3px 8px", background: "rgba(0,0,0,0.7)", fontFamily: "var(--f-mono)", fontSize: 10, color: "var(--bad)", letterSpacing: 1 }}>
              ● REC · 00:42:18
            </div>
            <div style={{ position: "absolute", bottom: 10, left: 10, fontFamily: "var(--f-mono)", fontSize: 10, color: "var(--fg-2)" }}>
              T+ 14253.012 · 60FPS · 12.4ms
            </div>
            <div style={{ position: "absolute", bottom: 10, right: 10, fontFamily: "var(--f-mono)", fontSize: 10, color: "var(--good)" }}>
              TRACKING: 10 PLAYERS · BALL OK
            </div>
          </div>
          {/* Thumbnails */}
          <div style={{ display: "grid", gridTemplateColumns: "repeat(8, 1fr)", gap: 4, flexShrink: 0 }}>
            {d.cameras.map((c, i) => (
              <div key={i} onClick={() => setSelectedCam(i)} style={{
                aspectRatio: "16/9", background: "var(--bg-0)",
                border: i === selectedCam ? "2px solid var(--hot)" : "1px solid var(--line-2)",
                position: "relative", cursor: "pointer", overflow: "hidden",
                opacity: c.status === "live" ? 1 : 0.4
              }}>
                <div style={{ position: "absolute", inset: 0,
                  background: `repeating-linear-gradient(45deg, transparent 0 8px, rgba(255,255,255,0.02) 8px 9px)` }}></div>
                <div style={{ position: "absolute", top: 3, left: 4, fontFamily: "var(--f-mono)", fontSize: 9, fontWeight: 700, color: "var(--fg-1)" }}>
                  CAM{c.id}
                </div>
                <div style={{ position: "absolute", bottom: 3, right: 4, fontFamily: "var(--f-mono)", fontSize: 8,
                              color: c.status === "live" ? "var(--good)" : "var(--bad)" }}>
                  {c.status === "live" ? "●" : "✕"}
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Right control panel */}
        <div style={{ background: "var(--bg-1)", display: "flex", flexDirection: "column", overflow: "hidden", minHeight: 0 }}>
          {/* Tabs */}
          <div style={{ display: "flex", borderBottom: "1px solid var(--line-2)" }}>
            {[["control", "CONTROL"], ["lineup", "LINEUP"], ["events", "EVENTS"], ["stats", "STATS"]].map(([id, label]) => (
              <button key={id} onClick={() => setTab(id)} style={{
                flex: 1, padding: "10px 0", background: tab === id ? "var(--bg-2)" : "transparent",
                border: "none", borderBottom: tab === id ? "2px solid var(--hot)" : "2px solid transparent",
                fontFamily: "var(--f-mono)", fontSize: 11, fontWeight: 600, letterSpacing: 1,
                color: tab === id ? "var(--fg-0)" : "var(--fg-2)", cursor: "pointer"
              }}>{label}</button>
            ))}
          </div>

          <div style={{ flex: 1, overflow: "auto", padding: 14 }}>
            {tab === "control" && <ControlPanel />}
            {tab === "lineup" && <LineupPanel />}
            {tab === "events" && <EventsPanel events={d.events} />}
            {tab === "stats" && <StatsPanel />}
          </div>
        </div>
      </div>

      <Ticker items={d.ticker} />
    </div>
  );
}

function ControlPanel() {
  const [home, setHome] = React.useState(41);
  const [away, setAway] = React.useState(38);
  return (
    <div>
      {/* Score editor */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
        <ScoreCol label="HOME · VOLTS" score={home} setScore={setHome} color="var(--hot)" />
        <ScoreCol label="AWAY · BLAZERS" score={away} setScore={setAway} color="var(--cool)" />
      </div>

      {/* Clock controls */}
      <div style={{ marginTop: 14, padding: 12, background: "var(--bg-2)", border: "1px solid var(--line-2)" }}>
        <div style={{ fontFamily: "var(--f-mono)", fontSize: 10, color: "var(--fg-2)", letterSpacing: 1 }}>GAME CLOCK</div>
        <div style={{ fontFamily: "var(--f-mono)", fontSize: 36, fontWeight: 700, color: "var(--warn)", textAlign: "center", marginTop: 4 }}>07:24</div>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 4, marginTop: 8 }}>
          <button className="cv-btn" style={{ height: 36 }}>START</button>
          <button className="cv-btn primary" style={{ height: 36 }}>PAUSE</button>
          <button className="cv-btn" style={{ height: 36 }}>RESET</button>
        </div>
      </div>

      {/* Shot clock */}
      <div style={{ marginTop: 8, padding: 12, background: "var(--bg-2)", border: "1px solid var(--line-2)" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
          <span style={{ fontFamily: "var(--f-mono)", fontSize: 10, color: "var(--fg-2)", letterSpacing: 1 }}>SHOT CLOCK</span>
          <span style={{ fontFamily: "var(--f-mono)", fontSize: 10, color: "var(--fg-3)" }}>14s · 24s · POSS</span>
        </div>
        <div style={{ fontFamily: "var(--f-mono)", fontSize: 36, fontWeight: 700, color: "var(--bad)", textAlign: "center", marginTop: 4 }}>14</div>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 4, marginTop: 8 }}>
          <button className="cv-btn">14</button>
          <button className="cv-btn">24</button>
          <button className="cv-btn">FLIP</button>
        </div>
      </div>

      {/* Quarter / period */}
      <div style={{ marginTop: 8, padding: 12, background: "var(--bg-2)", border: "1px solid var(--line-2)" }}>
        <div style={{ fontFamily: "var(--f-mono)", fontSize: 10, color: "var(--fg-2)", letterSpacing: 1, marginBottom: 6 }}>QUARTER</div>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(5, 1fr)", gap: 4 }}>
          {["Q1", "Q2", "Q3", "Q4", "OT"].map(q => (
            <button key={q} className="cv-btn" style={{
              background: q === "Q3" ? "var(--hot)" : "var(--bg-3)",
              color: q === "Q3" ? "#0A0B0D" : "var(--fg-0)",
              borderColor: q === "Q3" ? "var(--hot)" : "var(--line-3)"
            }}>{q}</button>
          ))}
        </div>
      </div>

      <div style={{ marginTop: 14, display: "grid", gridTemplateColumns: "1fr 1fr", gap: 4 }}>
        <button className="cv-btn primary" style={{ height: 38 }}>BROADCAST →</button>
        <button className="cv-btn">EXPORT CSV</button>
      </div>
    </div>
  );
}

function ScoreCol({ label, score, setScore, color }) {
  return (
    <div style={{ padding: 10, background: "var(--bg-2)", border: "1px solid var(--line-2)" }}>
      <div style={{ fontFamily: "var(--f-mono)", fontSize: 10, color: "var(--fg-2)", letterSpacing: 1 }}>{label}</div>
      <div style={{ fontFamily: "var(--f-mono)", fontSize: 44, fontWeight: 700, color, textAlign: "center", lineHeight: 1, marginTop: 6 }}>{score}</div>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 3, marginTop: 8 }}>
        {[1, 2, 3].map(n => (
          <button key={n} className="cv-btn" style={{ height: 28, padding: 0, fontSize: 12, color }}
                  onClick={() => setScore(score + n)}>+{n}</button>
        ))}
      </div>
      <button className="cv-btn ghost" style={{ width: "100%", marginTop: 4, height: 24, fontSize: 10 }} onClick={() => setScore(Math.max(0, score - 1))}>−1 UNDO</button>
    </div>
  );
}

function LineupPanel() {
  const home = [
    { num: 11, name: "K. PARK", pos: "PG", pts: 24, on: true },
    { num: 23, name: "S. RYU", pos: "SG", pts: 14, on: true },
    { num: 7, name: "J. OH", pos: "SF", pts: 6, on: true },
    { num: 4, name: "D. LEE", pos: "PF", pts: 4, on: true },
    { num: 15, name: "H. JANG", pos: "C", pts: 9, on: true },
  ];
  const bench = [
    { num: 9, name: "M. SHIN", pos: "G", pts: 0 },
    { num: 33, name: "B. CHO", pos: "F", pts: 0 },
    { num: 21, name: "K. AHN", pos: "C", pts: 0 },
  ];
  return (
    <div>
      <div style={{ fontFamily: "var(--f-mono)", fontSize: 10, color: "var(--hot)", letterSpacing: 1.2, marginBottom: 6 }}>ON COURT · VOLTS</div>
      {home.map((p, i) => <PlayerRow key={i} p={p} on />)}
      <div style={{ fontFamily: "var(--f-mono)", fontSize: 10, color: "var(--fg-2)", letterSpacing: 1.2, marginTop: 14, marginBottom: 6 }}>BENCH</div>
      {bench.map((p, i) => <PlayerRow key={i} p={p} />)}
      <button className="cv-btn primary" style={{ width: "100%", marginTop: 14, height: 36 }}>SUBSTITUTE →</button>
    </div>
  );
}

function PlayerRow({ p, on }) {
  return (
    <div style={{ display: "grid", gridTemplateColumns: "30px 30px 1fr 30px 40px", padding: "6px 8px", alignItems: "center",
                  background: on ? "var(--bg-3)" : "var(--bg-2)", borderBottom: "1px solid var(--line-1)",
                  fontFamily: "var(--f-mono)", fontSize: 11 }}>
      <span style={{ color: on ? "var(--good)" : "var(--fg-3)" }}>{on ? "●" : "○"}</span>
      <span style={{ color: "var(--hot)", fontWeight: 700 }}>#{p.num}</span>
      <span style={{ fontFamily: "var(--f-display)", fontWeight: 600 }}>{p.name}</span>
      <span style={{ color: "var(--fg-2)" }}>{p.pos}</span>
      <span style={{ color: p.pts ? "var(--fg-0)" : "var(--fg-3)", textAlign: "right", fontWeight: 600 }}>{p.pts}p</span>
    </div>
  );
}

function EventsPanel({ events }) {
  return (
    <div>
      {events.map((e, i) => (
        <div key={i} style={{ display: "grid", gridTemplateColumns: "44px 36px 1fr 26px", padding: "8px 6px",
                              borderBottom: "1px solid var(--line-1)", fontFamily: "var(--f-mono)", fontSize: 11, alignItems: "center" }}>
          <span style={{ color: "var(--fg-2)" }}>{e.q} {e.t}</span>
          <span style={{ color: e.icon === "score" ? "var(--hot)" : e.icon === "foul" ? "var(--bad)" : "var(--cool)", fontWeight: 700 }}>
            {e.icon === "score" ? "SCO" : e.icon === "foul" ? "FL" : e.icon === "to" ? "TO" : "SUB"}
          </span>
          <span style={{ color: "var(--fg-1)" }}><b style={{ color: "var(--fg-0)" }}>{e.team}</b> · {e.text}</span>
          <span style={{ color: "var(--good)", textAlign: "right" }}>{e.pts || ""}</span>
        </div>
      ))}
    </div>
  );
}

function StatsPanel() {
  const rows = [
    ["FG", "14/28", "12/30"],
    ["3PT", "5/12", "3/10"],
    ["FT", "8/9", "11/14"],
    ["REB", "22", "26"],
    ["AST", "12", "9"],
    ["STL", "5", "3"],
    ["BLK", "1", "2"],
    ["TO", "7", "9"],
    ["FOUL", "8", "11"],
  ];
  return (
    <div>
      <div style={{ display: "grid", gridTemplateColumns: "70px 1fr 1fr", padding: "8px 0", fontFamily: "var(--f-mono)", fontSize: 10, color: "var(--fg-2)", letterSpacing: 1, borderBottom: "1px solid var(--line-2)" }}>
        <span></span><span style={{ textAlign: "center", color: "var(--hot)" }}>VOLTS</span><span style={{ textAlign: "center", color: "var(--cool)" }}>BLAZERS</span>
      </div>
      {rows.map(([k, h, a], i) => (
        <div key={i} style={{ display: "grid", gridTemplateColumns: "70px 1fr 1fr", padding: "8px 0", borderBottom: "1px solid var(--line-1)",
                              fontFamily: "var(--f-mono)", fontSize: 12 }}>
          <span style={{ color: "var(--fg-2)" }}>{k}</span>
          <span style={{ textAlign: "center", color: "var(--fg-0)", fontWeight: 600 }}>{h}</span>
          <span style={{ textAlign: "center", color: "var(--fg-0)", fontWeight: 600 }}>{a}</span>
        </div>
      ))}
    </div>
  );
}

window.CvAnalysisScreen = CvAnalysisScreen;
