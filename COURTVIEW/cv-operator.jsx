// =============================================================================
// COURTVIEW — Operator console (full-screen, no top nav)
// FAITHFUL to operator.html structure: header → [controller | stats | sub] body
// Editorial visual skin only. NO layout/feature changes from original operator.
// =============================================================================

function CvOperatorScreen() {
  const [home, setHome] = React.useState(41);
  const [away, setAway] = React.useState(38);
  const [homeFoul, setHomeFoul] = React.useState(4);
  const [awayFoul, setAwayFoul] = React.useState(3);
  const [homeTO, setHomeTO] = React.useState(2); // used out of 5
  const [awayTO, setAwayTO] = React.useState(1);
  const [quarter, setQuarter] = React.useState(3);
  const [running, setRunning] = React.useState(true);
  const [shotOn, setShotOn] = React.useState(true);
  const [autoDead, setAutoDead] = React.useState(true);
  const [shotClock, setShotClock] = React.useState(14);
  const [possession, setPossession] = React.useState("home"); // "home" | "away"
  const [buzzing, setBuzzing] = React.useState(false);
  const [ruleset, setRuleset] = React.useState("FIBA"); // "FIBA" | "NBA"

  // Rule presets — bonus = 5번째 팀파울부터 자유투
  // FIBA: 5팀파울 → 보너스 (쿼터별 리셋)
  // NBA:  5팀파울 → 보너스 (쿼터별 리셋), 추가로 마지막 2분에 별도 룰이 있지만 단순화
  const rules = ruleset === "FIBA"
    ? { bonusAt: 5, totalTO: 5, label: "FIBA · KBL · 학원" }
    : { bonusAt: 5, totalTO: 7, label: "NBA · 7 timeouts" };
  const homeBonus = homeFoul >= rules.bonusAt;
  const awayBonus = awayFoul >= rules.bonusAt;

  // Operator hotkeys — keep hands on the keyboard, eyes on the court
  const flash = window.flashHotkey || (() => {});
  const bumpHome = (n) => { setHome(s => Math.max(0, s + n)); flash(`VOLTS ${n > 0 ? "+" : ""}${n}`); };
  const bumpAway = (n) => { setAway(s => Math.max(0, s + n)); flash(`BLAZERS ${n > 0 ? "+" : ""}${n}`); };
  const triggerBuzzer = () => { setBuzzing(true); flash("🔊 부저"); setTimeout(() => setBuzzing(false), 600); };

  // Hook always fires; no-op fallback when cv-hotkeys.jsx hasn't registered yet
  const useHK = window.useHotkeys || ((m, o) => React.useEffect(() => {}, []));
  useHK({
    // VOLTS scoring (left hand)
    "q": () => bumpHome(1),
    "w": () => bumpHome(2),
    "e": () => bumpHome(3),
    "shift+q": () => bumpHome(-1),
    "shift+w": () => bumpHome(-2),
    "shift+e": () => bumpHome(-3),
    // BLAZERS scoring (right hand)
    "o": () => bumpAway(1),
    "p": () => bumpAway(2),
    "[": () => bumpAway(3),
    "shift+o": () => bumpAway(-1),
    "shift+p": () => bumpAway(-2),
    "shift+[": () => bumpAway(-3),
    "{": () => bumpAway(-3), // shift+[ on some layouts
    // Clock
    " ": () => { setRunning(r => !r); flash(running ? "■ STOP" : "▶ START"); },
    "space": () => { setRunning(r => !r); flash(running ? "■ STOP" : "▶ START"); },
    "r": () => { setShotClock(24); setShotOn(true); flash("SHOT 24"); },
    "t": () => { setShotClock(14); setShotOn(true); flash("SHOT 14"); },
    "b": () => triggerBuzzer(),
    // Quarter
    // Quarter — changing quarter resets team fouls automatically (FIBA/NBA)
    "1": () => { setQuarter(1); setHomeFoul(0); setAwayFoul(0); flash("Q1 · 팀파울 리셋"); },
    "2": () => { setQuarter(2); setHomeFoul(0); setAwayFoul(0); flash("Q2 · 팀파울 리셋"); },
    "3": () => { setQuarter(3); setHomeFoul(0); setAwayFoul(0); flash("Q3 · 팀파울 리셋"); },
    "4": () => { setQuarter(4); setHomeFoul(0); setAwayFoul(0); flash("Q4 · 팀파울 리셋"); },
    "5": () => { setQuarter(5); setHomeFoul(0); setAwayFoul(0); flash("OT · 팀파울 리셋"); },
    // Possession (h / l — vim style, avoid arrow conflict with design canvas)
    "h": () => { setPossession("home"); flash("◀ VOLTS 공격권"); },
    "l": () => { setPossession("away"); flash("BLAZERS 공격권 ▶"); },
    // Fouls
    "f": () => { setHomeFoul(f => f + 1); flash("VOLTS 파울 +1"); },
    "shift+f": () => { setHomeFoul(f => Math.max(0, f - 1)); flash("VOLTS 파울 −1"); },
    "j": () => { setAwayFoul(f => f + 1); flash("BLAZERS 파울 +1"); },
    "shift+j": () => { setAwayFoul(f => Math.max(0, f - 1)); flash("BLAZERS 파울 −1"); },
    // Timeouts (limit by ruleset — FIBA 5 / NBA 7)
    "d": () => { setHomeTO(t => Math.min(rules.totalTO, t + 1)); flash("VOLTS 작전 요청"); },
    "k": () => { setAwayTO(t => Math.min(rules.totalTO, t + 1)); flash("BLAZERS 작전 요청"); },
  });

  const homePlayers = [
    { num: 11, name: "K. PARK", pos: "PG", on: true,  min: 24, pts: 24, fg: "8/14", fgp: 57, tp: "3/6",  tpp: 50, ft: "5/6", ftp: 83, oreb: 1, dreb: 4, reb: 5,  ast: 6, stl: 2, blk: 0, to: 2, pf: 2 },
    { num: 23, name: "S. RYU",  pos: "SG", on: true,  min: 22, pts: 14, fg: "5/9",  fgp: 56, tp: "2/4",  tpp: 50, ft: "2/2", ftp: 100,oreb: 0, dreb: 3, reb: 3,  ast: 9, stl: 1, blk: 0, to: 1, pf: 1 },
    { num: 7,  name: "J. OH",   pos: "SF", on: true,  min: 18, pts: 6,  fg: "2/5",  fgp: 40, tp: "1/3",  tpp: 33, ft: "1/2", ftp: 50, oreb: 1, dreb: 3, reb: 4,  ast: 1, stl: 0, blk: 1, to: 0, pf: 3 },
    { num: 4,  name: "D. LEE",  pos: "PF", on: true,  min: 19, pts: 4,  fg: "2/4",  fgp: 50, tp: "0/0",  tpp: 0,  ft: "0/0", ftp: 0,  oreb: 3, dreb: 5, reb: 8,  ast: 2, stl: 1, blk: 2, to: 1, pf: 2 },
    { num: 15, name: "H. JANG", pos: "C",  on: true,  min: 21, pts: 9,  fg: "4/7",  fgp: 57, tp: "0/0",  tpp: 0,  ft: "1/2", ftp: 50, oreb: 4, dreb: 7, reb: 11, ast: 1, stl: 0, blk: 3, to: 1, pf: 1 },
    { num: 9,  name: "M. SHIN", pos: "G",  on: false, min: 4,  pts: 0,  fg: "0/1",  fgp: 0,  tp: "0/1",  tpp: 0,  ft: "0/0", ftp: 0,  oreb: 0, dreb: 0, reb: 0,  ast: 0, stl: 0, blk: 0, to: 0, pf: 0 },
    { num: 33, name: "B. CHO",  pos: "F",  on: false, min: 6,  pts: 2,  fg: "1/2",  fgp: 50, tp: "0/0",  tpp: 0,  ft: "0/0", ftp: 0,  oreb: 1, dreb: 1, reb: 2,  ast: 0, stl: 0, blk: 0, to: 0, pf: 1 },
  ];
  const awayPlayers = [
    { num: 7,  name: "M. HAN", pos: "C",  on: true,  min: 23, pts: 18, fg: "7/12", fgp: 58, tp: "0/0", tpp: 0,  ft: "4/4", ftp: 100, oreb: 4, dreb: 7, reb: 11, ast: 2, stl: 0, blk: 2, to: 1, pf: 3 },
    { num: 3,  name: "T. KO",  pos: "PF", on: true,  min: 20, pts: 12, fg: "5/11", fgp: 45, tp: "1/3", tpp: 33, ft: "1/2", ftp: 50,  oreb: 2, dreb: 4, reb: 6,  ast: 4, stl: 1, blk: 1, to: 2, pf: 2 },
    { num: 12, name: "Y. KIM", pos: "SF", on: true,  min: 17, pts: 4,  fg: "2/6",  fgp: 33, tp: "0/2", tpp: 0,  ft: "0/0", ftp: 0,   oreb: 1, dreb: 2, reb: 3,  ast: 1, stl: 1, blk: 0, to: 0, pf: 2 },
    { num: 21, name: "K. AHN", pos: "SG", on: true,  min: 19, pts: 2,  fg: "1/4",  fgp: 25, tp: "0/2", tpp: 0,  ft: "0/0", ftp: 0,   oreb: 0, dreb: 1, reb: 1,  ast: 5, stl: 2, blk: 0, to: 1, pf: 4 },
    { num: 5,  name: "P. HEO", pos: "PG", on: true,  min: 22, pts: 2,  fg: "1/5",  fgp: 20, tp: "0/2", tpp: 0,  ft: "0/0", ftp: 0,   oreb: 1, dreb: 3, reb: 4,  ast: 2, stl: 0, blk: 0, to: 1, pf: 1 },
    { num: 17, name: "S. NA",  pos: "G",  on: false, min: 5,  pts: 0,  fg: "0/0",  fgp: 0,  tp: "0/0", tpp: 0,  ft: "0/0", ftp: 0,   oreb: 0, dreb: 0, reb: 0,  ast: 0, stl: 0, blk: 0, to: 0, pf: 0 },
    { num: 8,  name: "O. CHA", pos: "F",  on: false, min: 8,  pts: 0,  fg: "0/2",  fgp: 0,  tp: "0/1", tpp: 0,  ft: "0/0", ftp: 0,   oreb: 0, dreb: 1, reb: 1,  ast: 0, stl: 0, blk: 0, to: 1, pf: 0 },
  ];

  return (
    <div style={{ background: "var(--bg-0)", color: "var(--fg-0)", height: "100%", display: "flex", flexDirection: "column", overflow: "hidden", fontFamily: "var(--f-sans)" }}>
      {/* Op header — minimal, mirrors original op-header */}
      <div style={{ height: 38, display: "grid", gridTemplateColumns: "auto 1fr auto", alignItems: "center", padding: "0 16px", borderBottom: "1px solid var(--line-2)", background: "var(--bg-0)" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <span style={{ fontFamily: "var(--f-display)", fontSize: 13, fontWeight: 700, letterSpacing: 1 }}>COURT<span style={{ color: "var(--hot)" }}>VIEW</span> · OPERATOR</span>
          <span style={{ width: 1, height: 14, background: "var(--line-2)" }}></span>
          <span style={{ fontFamily: "var(--f-mono)", fontSize: 10, color: "var(--fg-2)", letterSpacing: 1 }}>전광판 컨트롤러 · 기록지 · 교체</span>
        </div>
        <div></div>
        <div style={{ display: "flex", alignItems: "center", gap: 14, fontFamily: "var(--f-mono)", fontSize: 10, color: "var(--fg-2)" }}>
          <span className="cv-onair sm" style={{ display: "inline-flex", alignItems: "center", gap: 6, padding: "3px 9px", border: "1px solid var(--bad)", color: "var(--bad)", fontFamily: "var(--f-display)", fontSize: 9, fontWeight: 700, letterSpacing: 2 }}>
            <span className="cv-onair-dot" style={{ width: 6, height: 6, background: "var(--bad)", borderRadius: "50%" }}></span>
            ON AIR
          </span>
          <span style={{ color: "var(--fg-3)" }}>|</span>
          <span><span style={{ color: "var(--good)" }}>●</span> 엔진 동기화</span>
          <span style={{ color: "var(--fg-3)" }}>|</span>
          <span>21:34:08</span>
        </div>
      </div>

      {/* Body — 3 columns: controller (left) | stats (center top) + sub (center bottom) | (no right column — original is 2-col) */}
      {/* Original op-body is grid-template-columns: 1fr 1fr; with stats on top and sub below on the right. We mirror that. */}
      <div style={{ flex: 1, display: "grid", gridTemplateColumns: "560px 1fr", gridTemplateRows: "1fr auto", gap: 1, background: "var(--line-2)", overflow: "hidden", minHeight: 0 }}>

        {/* ═══════════════════════════════════════════════════════════
             좌측: 전광판 컨트롤러 (operator.html의 popup-controller 구조)
             ═══════════════════════════════════════════════════════════ */}
        <div style={{ gridColumn: 1, gridRow: "1 / 3", background: "var(--bg-1)", padding: 16, overflow: "auto" }}>
          <div style={{ display: "flex", alignItems: "baseline", gap: 10, marginBottom: 14 }}>
            <span style={{ fontFamily: "var(--f-mono)", fontSize: 10, color: "var(--fg-2)", letterSpacing: 2 }}>01</span>
            <span style={{ fontFamily: "var(--f-display)", fontSize: 14, fontWeight: 700, letterSpacing: 0.5 }}>전광판 컨트롤러</span>
            <span style={{ flex: 1, height: 1, background: "var(--line-2)" }}></span>
            {/* Ruleset toggle — FIBA / NBA */}
            <div style={{ display: "flex", border: "1px solid var(--line-3)", overflow: "hidden" }}>
              {["FIBA", "NBA"].map((r, i) => (
                <button key={r} onClick={() => { setRuleset(r); flash(`RULES · ${r}`); }}
                  title={r === "FIBA" ? "FIBA · KBL · 학원농구 · 5팀파울 보너스 · 5타임아웃" : "NBA · 5팀파울 보너스 · 7타임아웃"}
                  style={{
                    fontFamily: "var(--f-mono)", fontSize: 9, fontWeight: 700, letterSpacing: 1,
                    padding: "4px 9px", height: 22, cursor: "pointer",
                    background: ruleset === r ? "var(--hot)" : "transparent",
                    color: ruleset === r ? "#0A0B0D" : "var(--fg-2)",
                    border: "none",
                    borderLeft: i > 0 ? "1px solid var(--line-3)" : "none",
                  }}>{r}</button>
              ))}
            </div>
          </div>

          {/* 타이머 제어 (start/reset/finalize) */}
          <div style={{ display: "flex", justifyContent: "center", gap: 8, marginBottom: 14 }}>
            <button className={`cv-btn ${running ? "" : "primary"}`} onClick={() => setRunning(!running)}
              style={{ width: 150, height: 44, fontSize: 14, fontWeight: 700,
                       background: running ? "var(--bad)" : "var(--good)", color: "#0A0B0D", borderColor: "transparent" }}>
              {running ? "■ STOP" : "▶ START"}
            </button>
            <button className="cv-btn" style={{ width: 80, height: 44, fontSize: 11 }}>↻ 리셋</button>
            <button className="cv-btn" style={{ width: 110, height: 44, fontSize: 11, fontWeight: 700, color: "var(--bad)", borderColor: "var(--bad)" }}>🏁 경기 종료</button>
          </div>

          {/* 게임 클락 + 샷 클락 (가로 배치) */}
          <div style={{ display: "flex", justifyContent: "center", gap: 28, marginBottom: 14 }}>
            <div style={{ textAlign: "center" }}>
              <div style={{ fontFamily: "var(--f-mono)", fontSize: 9, color: "var(--fg-2)", letterSpacing: 1.5, marginBottom: 2 }}>TIME</div>
              <div style={{ fontFamily: "var(--f-display)", fontSize: 44, fontWeight: 700, color: "var(--fg-0)", letterSpacing: -1, fontVariantNumeric: "tabular-nums", lineHeight: 1 }}>07:24</div>
              <div style={{ display: "flex", gap: 3, justifyContent: "center", marginTop: 5 }}>
                <button className="cv-btn" style={{ width: 38, height: 26, fontSize: 9, padding: 0 }}>−1m</button>
                <button className="cv-btn" style={{ width: 34, height: 26, fontSize: 9, padding: 0 }}>−1s</button>
                <button className="cv-btn" style={{ width: 34, height: 26, fontSize: 9, padding: 0 }}>+1s</button>
                <button className="cv-btn" style={{ width: 38, height: 26, fontSize: 9, padding: 0 }}>+1m</button>
              </div>
            </div>
            <div style={{ width: 1, background: "var(--line-2)" }}></div>
            <div style={{ textAlign: "center" }}>
              <div style={{ fontFamily: "var(--f-mono)", fontSize: 9, color: "var(--fg-2)", letterSpacing: 1.5, marginBottom: 2 }}>SHOT</div>
              <div style={{ fontFamily: "var(--f-display)", fontSize: 44, fontWeight: 700, color: shotOn ? "var(--warn)" : "var(--fg-3)", letterSpacing: -1, fontVariantNumeric: "tabular-nums", lineHeight: 1 }}>
                {shotOn ? "14" : "—"}
              </div>
              <div style={{ display: "flex", gap: 3, justifyContent: "center", marginTop: 5 }}>
                <button className="cv-btn" style={{ width: 36, height: 26, fontSize: 9, padding: 0, color: "var(--hot)", borderColor: "var(--hot)" }}>24</button>
                <button className="cv-btn" style={{ width: 36, height: 26, fontSize: 9, padding: 0, color: "var(--hot)", borderColor: "var(--hot)" }}>14</button>
                <button className="cv-btn" style={{ width: 30, height: 26, fontSize: 10, padding: 0 }}>−</button>
                <button className="cv-btn" style={{ width: 30, height: 26, fontSize: 10, padding: 0 }}>+</button>
              </div>
              <button className="cv-btn" onClick={() => setShotOn(!shotOn)} style={{ width: "100%", height: 24, fontSize: 9, marginTop: 4, color: "var(--warn)", borderColor: "var(--warn)" }}>
                {shotOn ? "⏸ SHOT 정지" : "▶ SHOT 시작"}
              </button>
            </div>
          </div>

          {/* 팀별 스코어 + 파울 + 타임아웃 (HOME · 중앙 쿼터/부저 · AWAY) */}
          <div style={{ display: "grid", gridTemplateColumns: "1fr auto 1fr", gap: 12, alignItems: "start" }}>
            {/* 홈팀 */}
            <TeamControlPanel
              side="home" name="VOLTS" color="var(--hot)"
              score={home} setScore={setHome}
              foul={homeFoul} setFoul={setHomeFoul}
              timeoutsUsed={homeTO} setTimeouts={setHomeTO}
              bonus={homeBonus} bonusAt={rules.bonusAt} totalTO={rules.totalTO}
            />

            {/* 중앙: 쿼터 + 부저 */}
            <div style={{ textAlign: "center", paddingTop: 12, minWidth: 110 }}>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 3 }}>
                {[1,2,3,4,5].map(q => (
                  <button key={q} onClick={() => setQuarter(q)}
                    style={{
                      width: 50, height: 28, fontSize: 11, fontFamily: "var(--f-display)", fontWeight: 700,
                      background: quarter === q ? "var(--hot)" : "var(--bg-3)",
                      color: quarter === q ? "#0A0B0D" : "var(--fg-1)",
                      border: `1px solid ${quarter === q ? "var(--hot)" : "var(--line-3)"}`,
                      cursor: "pointer", padding: 0,
                    }}>
                    {q === 5 ? "OT" : `${q}Q`}
                  </button>
                ))}
                <div></div>
              </div>
              <div style={{ fontFamily: "var(--f-mono)", fontSize: 9, color: "var(--fg-3)", letterSpacing: 1, marginTop: 8 }}>
                {quarter <= 2 ? "전반" : quarter <= 4 ? "후반" : "연장"}
              </div>
              <div style={{ marginTop: 10 }}>
                <button style={{
                  width: 100, height: 38, fontSize: 11, fontWeight: 700, fontFamily: "var(--f-display)",
                  background: "var(--bad)", color: "#0A0B0D", border: "none", cursor: "pointer", letterSpacing: 0.5, userSelect: "none",
                }}>🔊 부저</button>
                <div style={{ fontFamily: "var(--f-mono)", fontSize: 8, color: "var(--fg-3)", marginTop: 4, letterSpacing: 0.5, lineHeight: 1.3 }}>
                  눌러서 작동<br/>샷·종료 자동
                </div>
              </div>
            </div>

            {/* 어웨이팀 */}
            <TeamControlPanel
              side="away" name="BLAZERS" color="var(--cool)"
              score={away} setScore={setAway}
              foul={awayFoul} setFoul={setAwayFoul}
              timeoutsUsed={awayTO} setTimeouts={setAwayTO}
              bonus={awayBonus} bonusAt={rules.bonusAt} totalTO={rules.totalTO}
            />
          </div>

          {/* Possession + 송출 */}
          <div style={{ marginTop: 16, paddingTop: 14, borderTop: "1px solid var(--line-2)" }}>
            <div style={{ fontFamily: "var(--f-mono)", fontSize: 10, color: "var(--fg-2)", letterSpacing: 1.5, marginBottom: 8 }}>POSSESSION & BROADCAST</div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 6 }}>
              <button className="cv-btn primary" style={{ height: 34 }}>◀ VOLTS 공격권</button>
              <button className="cv-btn" style={{ height: 34 }}>BLAZERS 공격권 ▶</button>
            </div>
            <button className="cv-btn primary" style={{ width: "100%", marginTop: 8, height: 38, fontSize: 12, letterSpacing: 1 }}>전광판 송출 →</button>
          </div>
        </div>

        {/* ═══════════════════════════════════════════════════════════
             우측 상단: 실시간 기록지 (편집 가능) - 원본 op-stats
             ═══════════════════════════════════════════════════════════ */}
        <div style={{ gridColumn: 2, gridRow: 1, background: "var(--bg-1)", padding: "16px 20px", overflow: "auto", minWidth: 0 }}>
          <div style={{ display: "flex", alignItems: "baseline", gap: 12, marginBottom: 12 }}>
            <span style={{ fontFamily: "var(--f-mono)", fontSize: 10, color: "var(--fg-2)", letterSpacing: 2 }}>02</span>
            <span style={{ fontFamily: "var(--f-display)", fontSize: 16, fontWeight: 700, letterSpacing: -0.3 }}>실시간 기록지</span>
            <span style={{ fontFamily: "var(--f-mono)", fontSize: 9, color: "var(--fg-3)", letterSpacing: 1 }}>셀 클릭하여 편집</span>
            <span style={{ flex: 1, height: 1, background: "var(--line-2)" }}></span>
            <span className="cv-tag live" style={{ fontSize: 9 }}>LIVE</span>
          </div>

          <StatsTable title="VOLTS" color="var(--hot)" players={homePlayers} />
          <div style={{ height: 16 }}></div>
          <StatsTable title="BLAZERS" color="var(--cool)" players={awayPlayers} />
        </div>

        {/* ═══════════════════════════════════════════════════════════
             우측 하단: 선수 교체 - 원본 op-substitute
             ═══════════════════════════════════════════════════════════ */}
        <div style={{ gridColumn: 2, gridRow: 2, background: "var(--bg-1)", padding: "14px 20px", overflow: "auto", minWidth: 0, maxHeight: 280 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 10 }}>
            <span style={{ fontFamily: "var(--f-mono)", fontSize: 10, color: "var(--fg-2)", letterSpacing: 2 }}>03</span>
            <span style={{ fontFamily: "var(--f-display)", fontSize: 16, fontWeight: 700, letterSpacing: -0.3 }}>선수 교체</span>
            <span style={{ flex: 1, height: 1, background: "var(--line-2)" }}></span>
            <label style={{ display: "flex", gap: 6, alignItems: "center", fontFamily: "var(--f-mono)", fontSize: 10, color: "var(--fg-2)", letterSpacing: 0.5, cursor: "pointer" }}>
              <input type="checkbox" checked={autoDead} onChange={e => setAutoDead(e.target.checked)} />
              <span>볼 데드 시 자동 적용</span>
            </label>
          </div>

          {/* Pending alert */}
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "8px 12px", background: "var(--bg-2)", border: "1px solid var(--line-2)", borderLeft: "3px solid var(--warn)", marginBottom: 10 }}>
            <span style={{ fontFamily: "var(--f-mono)", fontSize: 11, color: "var(--warn)" }}>⏳ 대기 중인 교체 1건 (VOLTS · #9 IN, #4 OUT)</span>
            <div style={{ display: "flex", gap: 4 }}>
              <button className="cv-btn primary" style={{ height: 24, fontSize: 10, padding: "0 10px" }}>⚡ 강제 적용</button>
              <button className="cv-btn ghost" style={{ height: 24, fontSize: 10, padding: "0 10px" }}>취소</button>
            </div>
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
            <SubColumn title="VOLTS" color="var(--hot)" players={homePlayers} />
            <SubColumn title="BLAZERS" color="var(--cool)" players={awayPlayers} />
          </div>
        </div>
      </div>

      {/* Footer ticker */}
      <Ticker items={window.cvData.ticker} />
    </div>
  );
}

// =============================================================================
// 팀 컨트롤 패널 (홈/어웨이 — 점수 +/-, 파울, 타임아웃 점)
// =============================================================================
function TeamControlPanel({ side, name, color, score, setScore, foul, setFoul, timeoutsUsed, setTimeouts, bonus, bonusAt = 5, totalTO = 5 }) {
  return (
    <div style={{ textAlign: "center" }}>
      <div style={{ fontFamily: "var(--f-display)", fontSize: 13, fontWeight: 700, color, marginBottom: 6, letterSpacing: 0.5 }}>{name}</div>

      {/* +1 +2 +3 */}
      <div style={{ display: "flex", gap: 4, justifyContent: "center", marginBottom: 6 }}>
        {[1,2,3].map(n => (
          <button key={n} onClick={() => setScore(score + n)}
            style={{ width: 38, height: 28, fontSize: 12, fontWeight: 700, fontFamily: "var(--f-display)",
                     background: color, color: "#0A0B0D", border: "none", cursor: "pointer" }}>+{n}</button>
        ))}
      </div>

      {/* Foul · Score · (파울 표기는 원본대로 점수 옆) */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: 10 }}>
        {side === "home" && <FoulBlock foul={foul} bonus={bonus} bonusAt={bonusAt} />}
        <div style={{ fontFamily: "var(--f-display)", fontSize: 42, fontWeight: 700, color, letterSpacing: -1, fontVariantNumeric: "tabular-nums", minWidth: 60, lineHeight: 1 }}>{score}</div>
        {side === "away" && <FoulBlock foul={foul} bonus={bonus} bonusAt={bonusAt} />}
      </div>

      {/* -1 -2 -3 */}
      <div style={{ display: "flex", gap: 4, justifyContent: "center", marginTop: 6 }}>
        {[1,2,3].map(n => (
          <button key={n} onClick={() => setScore(Math.max(0, score - n))}
            className="cv-btn"
            style={{ width: 38, height: 24, fontSize: 11, padding: 0 }}>−{n}</button>
        ))}
      </div>

      {/* 파울 +1 / -1 */}
      <div style={{ display: "flex", gap: 4, justifyContent: "center", marginTop: 10 }}>
        <button onClick={() => setFoul(foul + 1)} style={{ width: 64, height: 28, fontSize: 10, fontWeight: 700, background: "transparent", color: "var(--bad)", border: "1px solid var(--bad)", cursor: "pointer", fontFamily: "var(--f-mono)", letterSpacing: 1 }}>파울 +1</button>
        <button onClick={() => setFoul(Math.max(0, foul - 1))} className="cv-btn" style={{ width: 44, height: 28, fontSize: 10, padding: 0 }}>−1</button>
      </div>

      {/* 타임아웃 — 점 표시 */}
      <div style={{ marginTop: 10, paddingTop: 10, borderTop: "1px solid var(--line-2)" }}>
        <div style={{ fontFamily: "var(--f-mono)", fontSize: 9, color: "var(--fg-2)", letterSpacing: 1, marginBottom: 5 }}>타임아웃</div>
        <div style={{ display: "flex", justifyContent: "center", gap: 4, marginBottom: 6 }}>
          {Array.from({ length: totalTO }).map((_, i) => (
            <span key={i} style={{
              width: 10, height: 10, borderRadius: "50%",
              background: i < timeoutsUsed ? "var(--fg-3)" : color,
              border: i < timeoutsUsed ? "1px solid var(--line-3)" : "none",
              opacity: i < timeoutsUsed ? 0.4 : 1,
            }}></span>
          ))}
        </div>
        <div style={{ display: "flex", gap: 3, justifyContent: "center", flexWrap: "wrap" }}>
          <button onClick={() => setTimeouts(Math.min(totalTO, timeoutsUsed + 1))} style={{ width: 70, height: 24, fontSize: 9, fontWeight: 700, background: "transparent", color: "var(--warn)", border: "1px solid var(--warn)", cursor: "pointer", fontFamily: "var(--f-mono)", letterSpacing: 0.5 }}>⏸ 작전 요청</button>
          <button onClick={() => setTimeouts(Math.max(0, timeoutsUsed - 1))} className="cv-btn" style={{ width: 36, height: 24, fontSize: 9, padding: 0 }}>−1</button>
        </div>
      </div>
    </div>
  );
}

function FoulBlock({ foul, bonus, bonusAt = 5 }) {
  const overLimit = foul >= bonusAt;
  const color = overLimit ? "var(--bad)" : foul >= bonusAt - 1 ? "var(--warn)" : "var(--fg-1)";
  return (
    <div style={{ textAlign: "center", minWidth: 32, position: "relative" }}>
      <div style={{ fontFamily: "var(--f-display)", fontSize: 22, fontWeight: 700, color, lineHeight: 1, fontVariantNumeric: "tabular-nums" }}>{foul}</div>
      <div style={{ fontFamily: "var(--f-mono)", fontSize: 8, color: "var(--fg-3)", letterSpacing: 1, marginTop: 2 }}>FOUL</div>
      {bonus && (
        <div style={{
          marginTop: 4, fontFamily: "var(--f-mono)", fontSize: 8, fontWeight: 700,
          color: "#0A0B0D", background: "var(--warn)", padding: "1px 4px", letterSpacing: 1.2,
          display: "inline-block", lineHeight: 1.4,
        }}>BONUS</div>
      )}
    </div>
  );
}

// =============================================================================
// 기록지 테이블 (원본 stats-table 그대로: # 이름 MIN PTS FG FG% 3P 3P% FT FT% OREB DREB REB AST STL BLK TO PF)
// =============================================================================
function StatsTable({ title, color, players }) {
  const cols = ["#", "이름", "MIN", "PTS", "FG", "FG%", "3P", "3P%", "FT", "FT%", "OREB", "DREB", "REB", "AST", "STL", "BLK", "TO", "PF"];
  return (
    <div>
      <div style={{ fontFamily: "var(--f-display)", fontSize: 13, fontWeight: 700, color, margin: "6px 0 6px", letterSpacing: 0.5 }}>{title}</div>
      <div style={{ overflowX: "auto" }}>
        <table style={{ width: "100%", borderCollapse: "collapse", fontFamily: "var(--f-mono)", fontSize: 10, whiteSpace: "nowrap" }}>
          <thead>
            <tr style={{ background: "var(--bg-2)" }}>
              {cols.map(c => (
                <th key={c} style={{
                  padding: "5px 6px", textAlign: c === "이름" ? "left" : "center",
                  color: "var(--fg-2)", fontWeight: 700, fontSize: 9, letterSpacing: 1,
                  borderBottom: "1px solid var(--line-2)",
                }}>{c}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {players.map((p, i) => (
              <tr key={i} style={{ opacity: p.on ? 1 : 0.5 }}>
                <td style={cellStyle({ center: true, color, bold: true })}>{p.num}</td>
                <td style={cellStyle({ left: true, font: "var(--f-display)", bold: true, fontSize: 11 })}>{p.name} <span style={{ color: "var(--fg-3)", fontFamily: "var(--f-mono)", fontSize: 9, marginLeft: 3 }}>{p.pos}</span></td>
                <td style={cellStyle({ center: true })}>{p.min}</td>
                <td style={cellStyle({ center: true, color: "var(--fg-0)", bold: true })}>{p.pts}</td>
                <td style={cellStyle({ center: true })}>{p.fg}</td>
                <td style={cellStyle({ center: true, color: "var(--fg-2)" })}>{p.fgp}%</td>
                <td style={cellStyle({ center: true })}>{p.tp}</td>
                <td style={cellStyle({ center: true, color: "var(--fg-2)" })}>{p.tpp}%</td>
                <td style={cellStyle({ center: true })}>{p.ft}</td>
                <td style={cellStyle({ center: true, color: "var(--fg-2)" })}>{p.ftp}%</td>
                <td style={cellStyle({ center: true })}>{p.oreb}</td>
                <td style={cellStyle({ center: true })}>{p.dreb}</td>
                <td style={cellStyle({ center: true, bold: true })}>{p.reb}</td>
                <td style={cellStyle({ center: true })}>{p.ast}</td>
                <td style={cellStyle({ center: true })}>{p.stl}</td>
                <td style={cellStyle({ center: true })}>{p.blk}</td>
                <td style={cellStyle({ center: true })}>{p.to}</td>
                <td style={cellStyle({ center: true, color: p.pf >= 4 ? "var(--bad)" : p.pf >= 3 ? "var(--warn)" : "var(--fg-1)", bold: p.pf >= 4 })}>{p.pf}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function cellStyle({ left, center, color, bold, font, fontSize }) {
  return {
    padding: "6px 6px",
    textAlign: left ? "left" : center ? "center" : "right",
    borderBottom: "1px solid var(--line-1)",
    color: color || "var(--fg-1)",
    fontWeight: bold ? 700 : 400,
    fontFamily: font || "var(--f-mono)",
    fontSize: fontSize || 10,
    cursor: "pointer",
  };
}

// =============================================================================
// 교체 컬럼 (on-court / bench)
// =============================================================================
function SubColumn({ title, color, players }) {
  const on = players.filter(p => p.on);
  const bench = players.filter(p => !p.on);
  return (
    <div style={{ background: "var(--bg-2)", border: "1px solid var(--line-2)", padding: 10 }}>
      <div style={{ fontFamily: "var(--f-display)", fontSize: 13, fontWeight: 700, color, letterSpacing: 0.5, marginBottom: 6 }}>{title}</div>
      <div style={{ fontFamily: "var(--f-mono)", fontSize: 9, color: "var(--fg-3)", letterSpacing: 1, marginBottom: 4 }}>ON COURT · {on.length}</div>
      {on.map((p, i) => (
        <div key={i} style={{ display: "grid", gridTemplateColumns: "30px 1fr 26px 44px", padding: "5px 6px", marginBottom: 2, background: "var(--bg-3)", borderLeft: `2px solid ${color}`, fontSize: 10, alignItems: "center", gap: 4 }}>
          <span style={{ color, fontWeight: 700, fontFamily: "var(--f-mono)" }}>#{p.num}</span>
          <span style={{ fontFamily: "var(--f-display)", fontWeight: 600, fontSize: 11 }}>{p.name}</span>
          <span style={{ color: "var(--fg-2)", fontSize: 9, fontFamily: "var(--f-mono)" }}>{p.pos}</span>
          <button className="cv-btn ghost" style={{ height: 18, fontSize: 8, padding: "0 5px" }}>OUT</button>
        </div>
      ))}
      <div style={{ fontFamily: "var(--f-mono)", fontSize: 9, color: "var(--fg-3)", letterSpacing: 1, marginTop: 6, marginBottom: 4 }}>벤치 · {bench.length}</div>
      {bench.map((p, i) => (
        <div key={i} style={{ display: "grid", gridTemplateColumns: "30px 1fr 26px 44px", padding: "5px 6px", marginBottom: 2, background: "var(--bg-1)", border: "1px solid var(--line-1)", fontSize: 10, alignItems: "center", opacity: 0.75, gap: 4 }}>
          <span style={{ color: "var(--fg-2)", fontWeight: 700, fontFamily: "var(--f-mono)" }}>#{p.num}</span>
          <span style={{ fontFamily: "var(--f-display)", fontWeight: 600, fontSize: 11 }}>{p.name}</span>
          <span style={{ color: "var(--fg-2)", fontSize: 9, fontFamily: "var(--f-mono)" }}>{p.pos}</span>
          <button className="cv-btn ghost" style={{ height: 18, fontSize: 8, padding: "0 5px", color: "var(--good)", borderColor: "var(--good)" }}>IN</button>
        </div>
      ))}
    </div>
  );
}

window.CvOperatorScreen = CvOperatorScreen;
