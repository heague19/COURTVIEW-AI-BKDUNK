// =============================================================================
// COURTVIEW — Pre-game setup screen
// 경기 시작 전 양 팀 정보, 선수 명단, 스타팅 5명을 등록하는 화면.
// Editorial system. Two columns (HOME / AWAY) + start gate at bottom.
// =============================================================================

function CvAnalysisSetupScreen() {
  // Static-but-realistic seed roster — mirrors uploads/game_analysis.html intent
  const seedHome = [
    { num: 11, name: "K. PARK",  pos: "PG" },
    { num: 23, name: "S. RYU",   pos: "SG" },
    { num:  7, name: "J. OH",    pos: "SF" },
    { num:  4, name: "D. LEE",   pos: "PF" },
    { num: 15, name: "H. JANG",  pos: "C"  },
    { num:  9, name: "M. SHIN",  pos: "G"  },
    { num: 33, name: "B. CHO",   pos: "F"  },
    { num: 21, name: "K. AHN",   pos: "C"  },
    { num: 17, name: "T. KIM",   pos: "G"  },
    { num:  3, name: "Y. SEO",   pos: "F"  },
  ];
  const seedAway = [
    { num: 32, name: "M. KIM",   pos: "PG" },
    { num: 10, name: "C. JUNG",  pos: "SG" },
    { num: 22, name: "R. HAN",   pos: "SF" },
    { num:  8, name: "G. CHOI",  pos: "PF" },
    { num: 44, name: "P. NAM",   pos: "C"  },
    { num:  5, name: "L. YOO",   pos: "G"  },
    { num: 14, name: "S. BAE",   pos: "F"  },
    { num: 25, name: "K. LIM",   pos: "C"  },
  ];

  const [homeName, setHomeName] = React.useState("VOLTS");
  const [awayName, setAwayName] = React.useState("BLAZERS");
  const [homeRoster] = React.useState(seedHome);
  const [awayRoster] = React.useState(seedAway);
  const [homeStarters, setHomeStarters] = React.useState(new Set([0, 1, 2, 3, 4]));
  const [awayStarters, setAwayStarters] = React.useState(new Set([0, 1, 2]));
  const [ruleset, setRuleset] = React.useState("FIBA"); // FIBA | NBA | KBL | YOUTH
  const [periods, setPeriods] = React.useState(4);
  const [periodLen, setPeriodLen] = React.useState("10:00");
  const [venue, setVenue] = React.useState("강남구민 체육관 · COURT 1");

  const ready = homeStarters.size === 5 && awayStarters.size === 5;

  function toggleStarter(team, idx) {
    const setter = team === "home" ? setHomeStarters : setAwayStarters;
    const set = team === "home" ? homeStarters : awayStarters;
    const next = new Set(set);
    if (next.has(idx)) next.delete(idx);
    else if (next.size < 5) next.add(idx);
    setter(next);
  }

  return (
    <div style={{ background: "var(--bg-1)", color: "var(--fg-0)", height: "100%", display: "flex", flexDirection: "column", overflow: "hidden" }}>
      <TopNav active="analysis" />

      {/* Setup banner */}
      <div style={{ padding: "14px 24px", borderBottom: "1px solid var(--line-2)", background: "var(--bg-0)",
                    display: "flex", alignItems: "baseline", gap: 18 }}>
        <span className="cv-tag" style={{ background: "var(--warn)", color: "#0A0B0D", border: "none" }}>SETUP</span>
        <span style={{ fontFamily: "var(--f-display)", fontSize: 22, fontWeight: 700, letterSpacing: -0.3 }}>
          경기 등록 <span style={{ color: "var(--fg-3)", fontWeight: 400, fontSize: 14, marginLeft: 8 }}>Pre-game registration</span>
        </span>
        <span style={{ flex: 1 }}></span>
        <span style={{ fontFamily: "var(--f-mono)", fontSize: 10, color: "var(--fg-2)", letterSpacing: 1.5 }}>
          STEP 1 / 2 · TEAM & ROSTER
        </span>
      </div>

      {/* Body */}
      <div style={{ flex: 1, display: "grid", gridTemplateColumns: "1fr 1fr", gap: 1, background: "var(--line-2)", overflow: "hidden", minHeight: 0 }}>
        <TeamSetupColumn
          accent="var(--hot)"
          side="home"
          sideLabel="홈 / HOME"
          name={homeName}
          setName={setHomeName}
          roster={homeRoster}
          starters={homeStarters}
          onToggle={(i) => toggleStarter("home", i)}
        />
        <TeamSetupColumn
          accent="var(--cool)"
          side="away"
          sideLabel="원정 / AWAY"
          name={awayName}
          setName={setAwayName}
          roster={awayRoster}
          starters={awayStarters}
          onToggle={(i) => toggleStarter("away", i)}
        />
      </div>

      {/* Game settings + start gate */}
      <div style={{ borderTop: "1px solid var(--line-2)", background: "var(--bg-0)", padding: "14px 24px",
                    display: "grid", gridTemplateColumns: "auto auto auto auto 1fr auto", gap: 24, alignItems: "center" }}>
        <SettingPicker
          label="RULESET"
          options={["FIBA", "KBL", "NBA", "YOUTH"]}
          value={ruleset}
          onChange={setRuleset}
        />
        <SettingNumber label="PERIODS" value={periods} onChange={setPeriods} min={2} max={4} />
        <SettingPicker
          label="LENGTH"
          options={["08:00", "10:00", "12:00"]}
          value={periodLen}
          onChange={setPeriodLen}
        />
        <SettingText label="VENUE" value={venue} onChange={setVenue} width={260} />

        <div style={{ textAlign: "right", fontFamily: "var(--f-mono)", fontSize: 10, color: "var(--fg-2)", letterSpacing: 1 }}>
          {ready
            ? <span style={{ color: "var(--good)" }}>READY · 양 팀 스타팅 등록 완료</span>
            : <span style={{ color: "var(--warn)" }}>
                NEED ·{" "}
                {homeStarters.size < 5 && <>HOME {5 - homeStarters.size}명{awayStarters.size < 5 ? " · " : ""}</>}
                {awayStarters.size < 5 && <>AWAY {5 - awayStarters.size}명</>}
              </span>}
        </div>

        <button className="cv-btn primary" disabled={!ready}
          style={{ height: 48, padding: "0 28px", fontSize: 14, opacity: ready ? 1 : 0.4, cursor: ready ? "pointer" : "not-allowed" }}>
          경기 시작 →
        </button>
      </div>
    </div>
  );
}

// -----------------------------------------------------------------------------
// Team column — name, jersey, roster with starter toggle
// -----------------------------------------------------------------------------
function TeamSetupColumn({ accent, side, sideLabel, name, setName, roster, starters, onToggle }) {
  return (
    <div style={{ background: "var(--bg-1)", padding: 18, display: "flex", flexDirection: "column", minHeight: 0, overflow: "hidden" }}>
      {/* Header */}
      <div style={{ display: "flex", alignItems: "baseline", gap: 10, marginBottom: 12 }}>
        <span style={{ fontFamily: "var(--f-mono)", fontSize: 10, color: accent, letterSpacing: 2, fontWeight: 700 }}>{sideLabel}</span>
        <span style={{ flex: 1, height: 1, background: "var(--line-2)" }}></span>
        <span style={{ fontFamily: "var(--f-mono)", fontSize: 10, color: starters.size === 5 ? "var(--good)" : "var(--fg-3)", letterSpacing: 1 }}>
          STARTERS {starters.size} / 5
        </span>
      </div>

      {/* Team identity row */}
      <div style={{ display: "grid", gridTemplateColumns: "auto 1fr auto auto", gap: 10, alignItems: "center", marginBottom: 14 }}>
        {/* Jersey swatch */}
        <div style={{ width: 56, height: 56, background: accent, position: "relative", display: "flex",
                      alignItems: "center", justifyContent: "center" }}>
          <span style={{ fontFamily: "var(--f-display)", fontWeight: 800, fontSize: 22, color: "#0A0B0D",
                         letterSpacing: -0.5 }}>{name.slice(0, 1)}</span>
        </div>

        {/* Editable team name */}
        <input
          type="text" value={name} onChange={e => setName(e.target.value.toUpperCase())}
          style={{
            background: "var(--bg-2)", border: "1px solid var(--line-3)",
            padding: "10px 12px", color: "var(--fg-0)", fontFamily: "var(--f-display)",
            fontWeight: 800, fontSize: 24, letterSpacing: -0.5, outline: "none", width: "100%",
          }}
        />

        {/* Color swatch toggles (visual only) */}
        <div style={{ display: "flex", flexDirection: "column", gap: 3 }}>
          <span style={{ fontFamily: "var(--f-mono)", fontSize: 8, color: "var(--fg-3)", letterSpacing: 1 }}>JERSEY</span>
          <div style={{ display: "flex", gap: 3 }}>
            {[accent, "#0A0B0D", "#FFFFFF"].map((c, i) => (
              <span key={i} style={{ width: 18, height: 18, background: c, border: i === 0 ? "2px solid var(--fg-0)" : "1px solid var(--line-3)" }}></span>
            ))}
          </div>
        </div>

        {/* Add player */}
        <button className="cv-btn ghost" style={{ height: 38, fontSize: 10, padding: "0 12px" }}>
          + 선수 추가
        </button>
      </div>

      {/* Roster — scrollable */}
      <div style={{ flex: 1, overflow: "auto", border: "1px solid var(--line-2)", background: "var(--bg-2)", minHeight: 0 }}>
        {/* Column heads */}
        <div style={{
          display: "grid", gridTemplateColumns: "44px 50px 1fr 44px 32px",
          padding: "8px 10px", fontFamily: "var(--f-mono)", fontSize: 9,
          color: "var(--fg-3)", letterSpacing: 1.2, borderBottom: "1px solid var(--line-2)",
          position: "sticky", top: 0, background: "var(--bg-0)", zIndex: 1,
        }}>
          <span>STR</span><span>#</span><span>NAME</span><span>POS</span><span></span>
        </div>

        {roster.map((p, i) => {
          const isStarter = starters.has(i);
          return (
            <div key={i} onClick={() => onToggle(i)}
              style={{
                display: "grid", gridTemplateColumns: "44px 50px 1fr 44px 32px",
                padding: "10px 10px", alignItems: "center", cursor: "pointer",
                borderBottom: "1px solid var(--line-1)",
                background: isStarter ? `color-mix(in oklab, ${accent} 7%, transparent)` : "transparent",
              }}>
              {/* Starter checkbox */}
              <span style={{
                width: 22, height: 22, border: `1.5px solid ${isStarter ? accent : "var(--line-3)"}`,
                background: isStarter ? accent : "transparent",
                display: "inline-flex", alignItems: "center", justifyContent: "center",
                fontFamily: "var(--f-mono)", fontSize: 12, fontWeight: 800,
                color: isStarter ? "#0A0B0D" : "transparent",
              }}>{isStarter ? "✓" : ""}</span>

              <span style={{ fontFamily: "var(--f-mono)", fontWeight: 700, fontSize: 13, color: accent }}>#{p.num}</span>
              <span style={{ fontFamily: "var(--f-display)", fontWeight: 600, fontSize: 13, color: "var(--fg-0)" }}>{p.name}</span>
              <span style={{ fontFamily: "var(--f-mono)", fontSize: 10, color: "var(--fg-2)", letterSpacing: 1 }}>{p.pos}</span>
              <span style={{ fontFamily: "var(--f-mono)", fontSize: 14, color: "var(--fg-3)", textAlign: "center" }}>×</span>
            </div>
          );
        })}
      </div>

      <div style={{ marginTop: 8, fontFamily: "var(--f-mono)", fontSize: 9, color: "var(--fg-3)", letterSpacing: 1 }}>
        탭하여 스타팅 5명 선택 · click row to toggle starter
      </div>
    </div>
  );
}

// -----------------------------------------------------------------------------
// Settings — segmented picker / number / text
// -----------------------------------------------------------------------------
function SettingPicker({ label, options, value, onChange }) {
  return (
    <div>
      <div style={{ fontFamily: "var(--f-mono)", fontSize: 9, color: "var(--fg-3)", letterSpacing: 1.2, marginBottom: 4 }}>{label}</div>
      <div style={{ display: "flex", border: "1px solid var(--line-3)" }}>
        {options.map((o, i) => (
          <button key={o} onClick={() => onChange(o)}
            style={{
              fontFamily: "var(--f-mono)", fontSize: 10, fontWeight: 700, letterSpacing: 1,
              padding: "8px 10px", height: 30, cursor: "pointer", border: "none",
              borderLeft: i > 0 ? "1px solid var(--line-3)" : "none",
              background: value === o ? "var(--hot)" : "transparent",
              color: value === o ? "#0A0B0D" : "var(--fg-2)",
            }}>{o}</button>
        ))}
      </div>
    </div>
  );
}

function SettingNumber({ label, value, onChange, min = 1, max = 99 }) {
  return (
    <div>
      <div style={{ fontFamily: "var(--f-mono)", fontSize: 9, color: "var(--fg-3)", letterSpacing: 1.2, marginBottom: 4 }}>{label}</div>
      <div style={{ display: "flex", border: "1px solid var(--line-3)", height: 30, alignItems: "center" }}>
        <button className="cv-btn" style={{ height: 28, width: 26, padding: 0, border: "none" }}
          onClick={() => onChange(Math.max(min, value - 1))}>−</button>
        <span style={{ fontFamily: "var(--f-mono)", fontSize: 13, fontWeight: 700, color: "var(--fg-0)", padding: "0 14px", minWidth: 28, textAlign: "center" }}>{value}</span>
        <button className="cv-btn" style={{ height: 28, width: 26, padding: 0, border: "none" }}
          onClick={() => onChange(Math.min(max, value + 1))}>+</button>
      </div>
    </div>
  );
}

function SettingText({ label, value, onChange, width = 200 }) {
  return (
    <div>
      <div style={{ fontFamily: "var(--f-mono)", fontSize: 9, color: "var(--fg-3)", letterSpacing: 1.2, marginBottom: 4 }}>{label}</div>
      <input type="text" value={value} onChange={e => onChange(e.target.value)}
        style={{
          background: "var(--bg-2)", border: "1px solid var(--line-3)",
          height: 30, width, padding: "0 10px", color: "var(--fg-0)",
          fontFamily: "var(--f-mono)", fontSize: 11, outline: "none",
        }} />
    </div>
  );
}

window.CvAnalysisSetupScreen = CvAnalysisSetupScreen;
