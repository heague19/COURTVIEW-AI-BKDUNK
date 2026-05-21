// =============================================================================
// COURTVIEW — Game result DETAIL (mirror of game_result.html#view-detail)
// Editorial visual skin. All data sections preserved:
//   scoreboard · 쿼터별 · 팀스탯 비교 · 베스트/워스트 · 부문별 1위
//   18+ col 박스스코어 (1차+2차) · 슛 히트맵 · 득점 흐름 + 하이라이트
// =============================================================================

function CvResultDetailScreen() {
  const [quarter, setQuarter] = React.useState("all");

  const meta = {
    date: "2026-05-07 · 19:30 KST",
    venue: "Court 03 · SMC Gym · Seoul",
    league: "SMC SPRING-26 · SEMIFINAL",
  };
  const home = { name: "FALCONS", short: "FAL", final: 78, q: [22, 18, 21, 17] };
  const away = { name: "TITANS",  short: "TIT", final: 64, q: [16, 19, 14, 15] };
  const winner = home.final > away.final ? "home" : "away";
  const margin = Math.abs(home.final - away.final);

  // 팀 통계 비교
  const teamStats = [
    { k: "FG%",  h: 47.8, a: 41.2, fmt: v => `${v}%` },
    { k: "3P%",  h: 38.5, a: 31.0, fmt: v => `${v}%` },
    { k: "FT%",  h: 78.6, a: 70.4, fmt: v => `${v}%` },
    { k: "REB",  h: 42,   a: 36,   fmt: v => v },
    { k: "AST",  h: 19,   a: 14,   fmt: v => v },
    { k: "STL",  h: 8,    a: 5,    fmt: v => v },
    { k: "BLK",  h: 4,    a: 6,    fmt: v => v },
    { k: "TO",   h: 11,   a: 16,   fmt: v => v, lowerBetter: true },
    { k: "PACE", h: 96.4, a: 96.4, fmt: v => v },
  ];

  // 부문별 리더
  const leaders = [
    { cat: "PTS", name: "K. PARK",  team: "FAL · #11", v: 24 },
    { cat: "REB", name: "M. HAN",   team: "TIT · #07", v: 11 },
    { cat: "AST", name: "S. RYU",   team: "FAL · #23", v: 9  },
    { cat: "STL", name: "K. AHN",   team: "TIT · #21", v: 4  },
  ];
  const best = { name: "K. PARK", team: "FALCONS · #11 · PG", line: [{ k: "PTS", v: 24 }, { k: "AST", v: 6 }, { k: "FG%", v: "57%" }, { k: "EFF", v: 31 }] };
  const worst = { name: "K. AHN", team: "TITANS · #21 · SG",  line: [{ k: "PTS", v: 2 }, { k: "FG%", v: "25%" }, { k: "TO", v: 4 }, { k: "EFF", v: -2 }] };

  // 박스스코어 — 1차 + 2차 스탯
  const homePlayers = [
    { num: 11, name: "K. PARK",  pos: "PG", min: 32, pts: 24, fg: "8/14", fgp: 57, tp: "3/6",  tpp: 50, ft: "5/6", ftp: 83,  oreb: 1, dreb: 4, reb: 5,  ast: 6, stl: 2, blk: 0, to: 2, pf: 2, pm: "+15", eff: 31, ts: 73, efg: 67, at: 3.0 },
    { num: 23, name: "S. RYU",   pos: "SG", min: 28, pts: 14, fg: "5/9",  fgp: 56, tp: "2/4",  tpp: 50, ft: "2/2", ftp: 100, oreb: 0, dreb: 3, reb: 3,  ast: 9, stl: 1, blk: 0, to: 1, pf: 1, pm: "+12", eff: 22, ts: 66, efg: 67, at: 9.0 },
    { num: 7,  name: "J. OH",    pos: "SF", min: 26, pts: 6,  fg: "2/5",  fgp: 40, tp: "1/3",  tpp: 33, ft: "1/2", ftp: 50,  oreb: 1, dreb: 3, reb: 4,  ast: 1, stl: 0, blk: 1, to: 0, pf: 3, pm: "+4",  eff: 9,  ts: 50, efg: 50, at: "—" },
    { num: 4,  name: "D. LEE",   pos: "PF", min: 25, pts: 4,  fg: "2/4",  fgp: 50, tp: "0/0",  tpp: 0,  ft: "0/0", ftp: 0,   oreb: 3, dreb: 5, reb: 8,  ast: 2, stl: 1, blk: 2, to: 1, pf: 2, pm: "+9",  eff: 14, ts: 50, efg: 50, at: 2.0 },
    { num: 15, name: "H. JANG",  pos: "C",  min: 27, pts: 9,  fg: "4/7",  fgp: 57, tp: "0/0",  tpp: 0,  ft: "1/2", ftp: 50,  oreb: 4, dreb: 7, reb: 11, ast: 1, stl: 0, blk: 3, to: 1, pf: 1, pm: "+11", eff: 23, ts: 60, efg: 57, at: 1.0 },
    { num: 9,  name: "M. SHIN",  pos: "G",  min: 12, pts: 8,  fg: "3/4",  fgp: 75, tp: "2/3",  tpp: 67, ft: "0/0", ftp: 0,   oreb: 0, dreb: 1, reb: 1,  ast: 2, stl: 1, blk: 0, to: 0, pf: 1, pm: "+5",  eff: 12, ts: 100, efg: 100, at: "—" },
    { num: 33, name: "B. CHO",   pos: "F",  min: 10, pts: 7,  fg: "3/5",  fgp: 60, tp: "0/0",  tpp: 0,  ft: "1/2", ftp: 50,  oreb: 2, dreb: 1, reb: 3,  ast: 0, stl: 1, blk: 0, to: 1, pf: 0, pm: "+3",  eff: 10, ts: 64, efg: 60, at: 0.0 },
    { num: 21, name: "T. WOO",   pos: "G",  min: 8,  pts: 6,  fg: "2/3",  fgp: 67, tp: "1/2",  tpp: 50, ft: "1/2", ftp: 50,  oreb: 0, dreb: 2, reb: 2,  ast: 1, stl: 0, blk: 0, to: 0, pf: 1, pm: "+1",  eff: 8,  ts: 71, efg: 83, at: "—" },
  ];
  const awayPlayers = [
    { num: 7,  name: "M. HAN",   pos: "C",  min: 30, pts: 18, fg: "7/12", fgp: 58, tp: "0/0",  tpp: 0,  ft: "4/4", ftp: 100, oreb: 4, dreb: 7, reb: 11, ast: 2, stl: 0, blk: 2, to: 1, pf: 3, pm: "-7",  eff: 24, ts: 64, efg: 58, at: 2.0 },
    { num: 3,  name: "T. KO",    pos: "PF", min: 28, pts: 12, fg: "5/11", fgp: 45, tp: "1/3",  tpp: 33, ft: "1/2", ftp: 50,  oreb: 2, dreb: 4, reb: 6,  ast: 4, stl: 1, blk: 1, to: 2, pf: 2, pm: "-9",  eff: 16, ts: 47, efg: 50, at: 2.0 },
    { num: 12, name: "Y. KIM",   pos: "SF", min: 24, pts: 8,  fg: "3/9",  fgp: 33, tp: "1/4",  tpp: 25, ft: "1/2", ftp: 50,  oreb: 1, dreb: 2, reb: 3,  ast: 1, stl: 1, blk: 0, to: 0, pf: 2, pm: "-6",  eff: 7,  ts: 39, efg: 39, at: "—" },
    { num: 21, name: "K. AHN",   pos: "SG", min: 26, pts: 2,  fg: "1/4",  fgp: 25, tp: "0/2",  tpp: 0,  ft: "0/0", ftp: 0,   oreb: 0, dreb: 1, reb: 1,  ast: 5, stl: 4, blk: 0, to: 4, pf: 4, pm: "-12", eff: -2, ts: 25, efg: 25, at: 1.25 },
    { num: 5,  name: "P. HEO",   pos: "PG", min: 27, pts: 6,  fg: "2/8",  fgp: 25, tp: "0/3",  tpp: 0,  ft: "2/2", ftp: 100, oreb: 1, dreb: 3, reb: 4,  ast: 2, stl: 0, blk: 0, to: 3, pf: 1, pm: "-11", eff: 4,  ts: 33, efg: 25, at: 0.67 },
    { num: 17, name: "S. NA",    pos: "G",  min: 9,  pts: 8,  fg: "3/4",  fgp: 75, tp: "2/3",  tpp: 67, ft: "0/0", ftp: 0,   oreb: 0, dreb: 1, reb: 1,  ast: 0, stl: 0, blk: 0, to: 1, pf: 0, pm: "-3",  eff: 8,  ts: 100, efg: 100, at: 0.0 },
    { num: 8,  name: "O. CHA",   pos: "F",  min: 14, pts: 6,  fg: "2/5",  fgp: 40, tp: "0/1",  tpp: 0,  ft: "2/2", ftp: 100, oreb: 1, dreb: 2, reb: 3,  ast: 0, stl: 0, blk: 1, to: 1, pf: 1, pm: "-2",  eff: 8,  ts: 57, efg: 40, at: 0.0 },
    { num: 14, name: "D. JUN",   pos: "PF", min: 6,  pts: 4,  fg: "1/2",  fgp: 50, tp: "0/0",  tpp: 0,  ft: "2/2", ftp: 100, oreb: 0, dreb: 1, reb: 1,  ast: 0, stl: 0, blk: 1, to: 1, pf: 0, pm: "+1",  eff: 5,  ts: 86, efg: 50, at: 0.0 },
  ];

  // 하이라이트 (득점 흐름)
  const highlights = [
    { q: 1, t: "08:42", team: "FAL", text: "K. PARK · 3PT from corner", pts: 3 },
    { q: 1, t: "03:11", team: "TIT", text: "M. HAN · putback dunk",     pts: 2 },
    { q: 2, t: "07:30", team: "FAL", text: "S. RYU · steal + fastbreak", pts: 2 },
    { q: 2, t: "01:48", team: "FAL", text: "H. JANG · and-one",          pts: 3 },
    { q: 3, t: "06:22", team: "TIT", text: "T. KO · pull-up midrange",   pts: 2 },
    { q: 3, t: "02:04", team: "FAL", text: "K. PARK · step-back 3",      pts: 3 },
    { q: 4, t: "05:15", team: "FAL", text: "D. LEE · block + assist",    pts: 0 },
    { q: 4, t: "00:42", team: "FAL", text: "K. PARK · sealing free throws", pts: 2 },
  ];

  return (
    <div data-print-root="result-detail" style={{ background: "var(--bg-1)", color: "var(--fg-0)", height: "100%", display: "flex", flexDirection: "column", overflow: "hidden" }}>
      <TopNav active="result" />
      <div style={{ flex: 1, overflow: "auto" }}>

        {/* Back nav */}
        <div style={{ padding: "16px 48px 0", display: "flex", alignItems: "center", gap: 14 }}>
          <a href="#result" style={{ fontFamily: "var(--f-mono)", fontSize: 11, color: "var(--fg-2)", letterSpacing: 1, textDecoration: "none", borderBottom: "1px solid var(--line-3)", paddingBottom: 2 }}>← BACK TO RESULTS</a>
          <span style={{ flex: 1, height: 1, background: "var(--line-2)" }}></span>
          <span style={{ fontFamily: "var(--f-mono)", fontSize: 10, color: "var(--fg-3)", letterSpacing: 1.5 }}>{meta.league}</span>
        </div>

        {/* HERO scoreboard */}
        <div style={{ padding: "32px 48px 28px", borderBottom: "1px solid var(--line-2)" }}>
          <div style={{ display: "flex", gap: 18, marginBottom: 18, fontFamily: "var(--f-mono)", fontSize: 10, color: "var(--fg-2)", letterSpacing: 1.5 }}>
            <span><span style={{ color: "var(--fg-3)" }}>DATE — </span>{meta.date}</span>
            <span><span style={{ color: "var(--fg-3)" }}>VENUE — </span>{meta.venue}</span>
            <span className="cv-tag" style={{ fontSize: 9 }}>FINAL</span>
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr auto 1fr", alignItems: "center", gap: 32 }}>
            <div style={{ textAlign: "right" }}>
              <div style={{ fontFamily: "var(--f-mono)", fontSize: 11, color: "var(--fg-3)", letterSpacing: 2, marginBottom: 6 }}>HOME</div>
              <div style={{ fontFamily: "var(--f-display)", fontSize: 36, fontWeight: 700, color: winner === "home" ? "var(--hot)" : "var(--fg-1)", letterSpacing: -0.5, lineHeight: 1 }}>{home.name}</div>
              <div style={{ fontFamily: "var(--f-display)", fontSize: 96, fontWeight: 800, color: winner === "home" ? "var(--hot)" : "var(--fg-2)", letterSpacing: -3, lineHeight: 1, marginTop: 8, fontVariantNumeric: "tabular-nums" }}>{home.final}</div>
              {winner === "home" && <div style={{ fontFamily: "var(--f-mono)", fontSize: 10, color: "var(--hot)", letterSpacing: 2, marginTop: 8 }}>● WIN · +{margin}</div>}
            </div>
            <div style={{ width: 1, height: 130, background: "var(--line-2)" }}></div>
            <div>
              <div style={{ fontFamily: "var(--f-mono)", fontSize: 11, color: "var(--fg-3)", letterSpacing: 2, marginBottom: 6 }}>AWAY</div>
              <div style={{ fontFamily: "var(--f-display)", fontSize: 36, fontWeight: 700, color: winner === "away" ? "var(--hot)" : "var(--fg-1)", letterSpacing: -0.5, lineHeight: 1 }}>{away.name}</div>
              <div style={{ fontFamily: "var(--f-display)", fontSize: 96, fontWeight: 800, color: winner === "away" ? "var(--hot)" : "var(--fg-2)", letterSpacing: -3, lineHeight: 1, marginTop: 8, fontVariantNumeric: "tabular-nums" }}>{away.final}</div>
              {winner === "away" && <div style={{ fontFamily: "var(--f-mono)", fontSize: 10, color: "var(--hot)", letterSpacing: 2, marginTop: 8 }}>● WIN · +{margin}</div>}
            </div>
          </div>
        </div>

        {/* 쿼터별 점수 */}
        <EdPanel kicker="01 · QUARTER BREAKDOWN" title="쿼터별 점수" padding="28px 48px">
          <table style={{ width: "100%", borderCollapse: "collapse", fontFamily: "var(--f-mono)" }}>
            <thead>
              <tr>
                <th style={qThStyle({ left: true })}>팀</th>
                {[1,2,3,4].map(q => <th key={q} style={qThStyle()}>{q}Q</th>)}
                <th style={qThStyle({ accent: true })}>합계</th>
              </tr>
            </thead>
            <tbody>
              {[home, away].map((t, ti) => (
                <tr key={ti}>
                  <td style={qTdStyle({ left: true })}>
                    <span style={{ fontFamily: "var(--f-display)", fontSize: 16, fontWeight: 700, color: ti === 0 ? "var(--hot)" : "var(--cool)", letterSpacing: -0.3 }}>{t.name}</span>
                  </td>
                  {t.q.map((s, qi) => {
                    const opp = (ti === 0 ? away.q : home.q)[qi];
                    const won = s > opp;
                    return (
                      <td key={qi} style={qTdStyle({ winner: won })}>{s}</td>
                    );
                  })}
                  <td style={qTdStyle({ accent: true })}>{t.final}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </EdPanel>

        {/* 팀 통계 비교 */}
        <EdPanel kicker="02 · TEAM STATS" title="팀 통계 비교" padding="28px 48px">
          <div style={{ display: "grid", gap: 14 }}>
            {teamStats.map((s, i) => {
              const total = s.h + s.a;
              const hPct = total === 0 ? 50 : (s.h / total) * 100;
              const aPct = 100 - hPct;
              const hWin = s.lowerBetter ? s.h < s.a : s.h > s.a;
              return (
                <div key={i} style={{ display: "grid", gridTemplateColumns: "70px 1fr 90px 1fr 70px", alignItems: "center", gap: 14 }}>
                  <span style={{ fontFamily: "var(--f-display)", fontSize: 18, fontWeight: 700, color: hWin ? "var(--hot)" : "var(--fg-1)", textAlign: "right", fontVariantNumeric: "tabular-nums" }}>{s.fmt(s.h)}</span>
                  <div style={{ height: 6, background: "var(--bg-2)", display: "flex", justifyContent: "flex-end", border: "1px solid var(--line-1)" }}>
                    <div style={{ width: `${hPct}%`, height: "100%", background: hWin ? "var(--hot)" : "var(--fg-3)" }}></div>
                  </div>
                  <span style={{ fontFamily: "var(--f-mono)", fontSize: 11, color: "var(--fg-2)", letterSpacing: 1.5, textAlign: "center" }}>{s.k}</span>
                  <div style={{ height: 6, background: "var(--bg-2)", border: "1px solid var(--line-1)" }}>
                    <div style={{ width: `${aPct}%`, height: "100%", background: !hWin ? "var(--hot)" : "var(--fg-3)" }}></div>
                  </div>
                  <span style={{ fontFamily: "var(--f-display)", fontSize: 18, fontWeight: 700, color: !hWin ? "var(--hot)" : "var(--fg-1)", fontVariantNumeric: "tabular-nums" }}>{s.fmt(s.a)}</span>
                </div>
              );
            })}
          </div>
        </EdPanel>

        {/* 베스트 / 워스트 */}
        <div style={{ padding: "0 48px" }}>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 1, background: "var(--line-2)", border: "1px solid var(--line-2)" }}>
            <FeatureCard kind="best" player={best} />
            <FeatureCard kind="worst" player={worst} />
          </div>
        </div>

        {/* 부문별 1위 */}
        <EdPanel kicker="03 · CATEGORY LEADERS" title="부문별 1위" padding="28px 48px">
          <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 1, background: "var(--line-2)", border: "1px solid var(--line-2)" }}>
            {leaders.map((l, i) => (
              <div key={i} style={{ background: "var(--bg-1)", padding: 18 }}>
                <div style={{ fontFamily: "var(--f-mono)", fontSize: 10, color: "var(--fg-2)", letterSpacing: 2, marginBottom: 6 }}>{l.cat} LEADER</div>
                <div style={{ fontFamily: "var(--f-display)", fontSize: 38, fontWeight: 700, color: "var(--hot)", letterSpacing: -1, lineHeight: 1, fontVariantNumeric: "tabular-nums" }}>{l.v}</div>
                <div style={{ fontFamily: "var(--f-display)", fontSize: 14, fontWeight: 700, marginTop: 8 }}>{l.name}</div>
                <div style={{ fontFamily: "var(--f-mono)", fontSize: 10, color: "var(--fg-3)", letterSpacing: 1, marginTop: 2 }}>{l.team}</div>
              </div>
            ))}
          </div>
        </EdPanel>

        {/* 박스스코어 */}
        <EdPanel kicker="04 · BOX SCORE" title="선수 기록지" padding="28px 48px"
          right={
            <div style={{ display: "flex", gap: 14, fontFamily: "var(--f-mono)", fontSize: 9, color: "var(--fg-3)", letterSpacing: 1 }}>
              <span><span style={{ color: "var(--hot)" }}>●</span> 1차 (직접 기록)</span>
              <span><span style={{ color: "var(--warn)" }}>●</span> 2차 (계산)</span>
            </div>
          }>
          <BoxScoreTable title="FALCONS" color="var(--hot)" players={homePlayers} />
          <div style={{ height: 22 }}></div>
          <BoxScoreTable title="TITANS"  color="var(--cool)" players={awayPlayers} />

          {/* Stat legend */}
          <details style={{ marginTop: 18, padding: "14px 16px", background: "var(--bg-2)", border: "1px solid var(--line-2)" }}>
            <summary style={{ fontFamily: "var(--f-mono)", fontSize: 10, color: "var(--fg-2)", letterSpacing: 1.5, cursor: "pointer" }}>STAT GLOSSARY — click to expand</summary>
            <div style={{ marginTop: 12, fontFamily: "var(--f-mono)", fontSize: 10, color: "var(--fg-2)", lineHeight: 1.7 }}>
              <div style={{ color: "var(--hot)", letterSpacing: 1.5, marginBottom: 6 }}>1차 — 기록원 직접 기록</div>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", columnGap: 24, rowGap: 2 }}>
                <span><b style={{ color: "var(--fg-0)" }}>MIN</b> — 출전 시간 (분)</span>
                <span><b style={{ color: "var(--fg-0)" }}>PTS</b> — 득점</span>
                <span><b style={{ color: "var(--fg-0)" }}>FG</b> — 야투 (성공/시도)</span>
                <span><b style={{ color: "var(--fg-0)" }}>3P</b> — 3점 (성공/시도)</span>
                <span><b style={{ color: "var(--fg-0)" }}>FT</b> — 자유투 (성공/시도)</span>
                <span><b style={{ color: "var(--fg-0)" }}>OREB/DREB</b> — 공/수 리바운드</span>
                <span><b style={{ color: "var(--fg-0)" }}>AST</b> — 어시스트</span>
                <span><b style={{ color: "var(--fg-0)" }}>STL</b> — 스틸</span>
                <span><b style={{ color: "var(--fg-0)" }}>BLK</b> — 블록</span>
                <span><b style={{ color: "var(--fg-0)" }}>TO</b> — 턴오버</span>
                <span><b style={{ color: "var(--fg-0)" }}>PF</b> — 개인 파울</span>
              </div>
              <div style={{ color: "var(--warn)", letterSpacing: 1.5, marginTop: 12, marginBottom: 6 }}>2차 — 계산</div>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(2, 1fr)", columnGap: 24, rowGap: 2 }}>
                <span><b style={{ color: "var(--fg-0)" }}>+/-</b> — 출전 중 팀 득실점 차</span>
                <span><b style={{ color: "var(--fg-0)" }}>EFF</b> — PTS+REB+AST+STL+BLK−TO−미스</span>
                <span><b style={{ color: "var(--fg-0)" }}>TS%</b> — PTS÷(2×(FGA+0.44×FTA))</span>
                <span><b style={{ color: "var(--fg-0)" }}>eFG%</b> — (FGM+0.5×3PM)÷FGA</span>
                <span><b style={{ color: "var(--fg-0)" }}>A/T</b> — AST 대 TO 비율</span>
              </div>
            </div>
          </details>
        </EdPanel>

        {/* 슛 히트맵 */}
        <EdPanel kicker="05 · SHOT CHART" title="슛 히트맵" padding="28px 48px"
          right={
            <div style={{ display: "flex", gap: 14, fontFamily: "var(--f-mono)", fontSize: 9, letterSpacing: 1 }}>
              <span style={{ color: "var(--good)" }}>● MADE</span>
              <span style={{ color: "var(--bad)" }}>● MISS</span>
              <span style={{ color: "var(--fg-3)" }}>● 3PT ZONE</span>
            </div>
          }>
          <ShotChart />
        </EdPanel>

        {/* 득점 흐름 + 하이라이트 */}
        <EdPanel kicker="06 · MOMENTUM" title="득점 흐름 · 하이라이트" padding="28px 48px"
          right={
            <div style={{ display: "flex", gap: 4 }}>
              {["all", 1, 2, 3, 4].map(q => (
                <button key={q} onClick={() => setQuarter(q)}
                  className={`cv-btn ${quarter === q ? "primary" : "ghost"}`}
                  style={{ height: 26, fontSize: 10, padding: "0 10px" }}>
                  {q === "all" ? "ALL" : `${q}Q`}
                </button>
              ))}
            </div>
          }>
          <MomentumChart home={home} away={away} />

          <div style={{ marginTop: 24 }}>
            <div style={{ fontFamily: "var(--f-mono)", fontSize: 10, color: "var(--fg-2)", letterSpacing: 1.5, marginBottom: 10 }}>HIGHLIGHTS — {(quarter === "all" ? highlights : highlights.filter(h => h.q === quarter)).length} CLIPS</div>
            <div style={{ display: "grid", gap: 0 }}>
              {(quarter === "all" ? highlights : highlights.filter(h => h.q === quarter)).map((h, i, arr) => (
                <div key={i} style={{
                  display: "grid", gridTemplateColumns: "44px 56px 56px 1fr 60px 90px",
                  alignItems: "center", gap: 14,
                  padding: "12px 0",
                  borderBottom: i < arr.length - 1 ? "1px solid var(--line-1)" : "none",
                }}>
                  <span style={{ fontFamily: "var(--f-mono)", fontSize: 10, color: "var(--fg-3)", letterSpacing: 1 }}>Q{h.q}</span>
                  <span style={{ fontFamily: "var(--f-mono)", fontSize: 11, color: "var(--fg-2)", fontVariantNumeric: "tabular-nums" }}>{h.t}</span>
                  <span className={`cv-tag ${h.team === "FAL" ? "hot" : "cool"}`} style={{ fontSize: 9, justifySelf: "start" }}>{h.team}</span>
                  <span style={{ fontFamily: "var(--f-display)", fontSize: 14, fontWeight: 600, color: "var(--fg-0)" }}>{h.text}</span>
                  <span style={{ fontFamily: "var(--f-display)", fontSize: 16, fontWeight: 700, color: h.pts > 0 ? "var(--hot)" : "var(--fg-3)", textAlign: "right" }}>
                    {h.pts > 0 ? `+${h.pts}` : "—"}
                  </span>
                  <button className="cv-btn ghost" style={{ height: 24, fontSize: 9, padding: "0 8px" }}>▶ PLAY CLIP</button>
                </div>
              ))}
            </div>
          </div>
        </EdPanel>

        {/* Actions */}
        <div style={{ padding: "24px 48px 48px", display: "flex", gap: 8, borderTop: "1px solid var(--line-2)", marginTop: 14 }}>
          <button className="cv-btn primary" style={{ height: 36 }} data-no-print>↓ JSON 다운로드</button>
          <button className="cv-btn" style={{ height: 36 }} data-no-print>↓ EXPORT CSV</button>
          <button className="cv-btn" style={{ height: 36 }} data-no-print onClick={() => { document.body.classList.add("cv-print-mode"); setTimeout(() => { window.print(); document.body.classList.remove("cv-print-mode"); }, 50); }}>🖨 PRINT BOX SCORE</button>
          <button className="cv-btn" style={{ height: 36 }} data-no-print>📤 SHARE</button>
          <span style={{ flex: 1 }}></span>
          <a href="#result" className="cv-btn" style={{ height: 36, display: "inline-flex", alignItems: "center", padding: "0 14px", textDecoration: "none" }}>← BACK TO RESULTS</a>
        </div>
      </div>
    </div>
  );
}

// ---- helpers ----
function qThStyle({ left, accent } = {}) {
  return {
    padding: "8px 10px",
    textAlign: left ? "left" : "center",
    fontFamily: "var(--f-mono)",
    fontSize: 10,
    color: accent ? "var(--hot)" : "var(--fg-2)",
    letterSpacing: 1.5,
    fontWeight: 700,
    borderBottom: "1px solid var(--line-2)",
  };
}
function qTdStyle({ left, accent, winner } = {}) {
  return {
    padding: "14px 10px",
    textAlign: left ? "left" : "center",
    fontFamily: "var(--f-mono)",
    fontSize: accent ? 22 : 18,
    fontWeight: 700,
    color: accent ? "var(--hot)" : winner ? "var(--fg-0)" : "var(--fg-2)",
    borderBottom: "1px solid var(--line-1)",
    fontVariantNumeric: "tabular-nums",
  };
}

function FeatureCard({ kind, player }) {
  const isBest = kind === "best";
  return (
    <div style={{ background: "var(--bg-1)", padding: 22 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 12 }}>
        <span className={`cv-tag ${isBest ? "" : "ghost"}`} style={{
          fontSize: 9, letterSpacing: 1.5,
          background: isBest ? "var(--good)" : "var(--bad)",
          color: "#0A0B0D",
        }}>
          {isBest ? "★ BEST PLAYER" : "↓ STRUGGLED"}
        </span>
        <span style={{ flex: 1, height: 1, background: "var(--line-2)" }}></span>
      </div>
      <div style={{ fontFamily: "var(--f-display)", fontSize: 32, fontWeight: 700, letterSpacing: -0.5, color: isBest ? "var(--fg-0)" : "var(--fg-1)", lineHeight: 1 }}>{player.name}</div>
      <div style={{ fontFamily: "var(--f-mono)", fontSize: 11, color: "var(--fg-2)", letterSpacing: 1, marginTop: 4 }}>{player.team}</div>
      <div style={{ display: "flex", gap: 22, marginTop: 18, flexWrap: "wrap" }}>
        {player.line.map((s, i) => (
          <div key={i}>
            <div style={{ fontFamily: "var(--f-mono)", fontSize: 9, color: "var(--fg-3)", letterSpacing: 1.5 }}>{s.k}</div>
            <div style={{ fontFamily: "var(--f-display)", fontSize: 22, fontWeight: 700, color: isBest ? "var(--hot)" : "var(--fg-1)", marginTop: 2, fontVariantNumeric: "tabular-nums" }}>{s.v}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

function BoxScoreTable({ title, color, players }) {
  const cols1 = ["", "#", "이름", "MIN", "PTS", "FG", "FG%", "3P", "3P%", "FT", "FT%", "OREB", "DREB", "REB", "AST", "STL", "BLK", "TO", "PF"];
  const cols2 = ["+/-", "EFF", "TS%", "eFG%", "A/T"];
  const totals = players.reduce((a, p) => ({
    pts: a.pts + p.pts, reb: a.reb + p.reb, ast: a.ast + p.ast, stl: a.stl + p.stl, blk: a.blk + p.blk, to: a.to + p.to, pf: a.pf + p.pf,
  }), { pts: 0, reb: 0, ast: 0, stl: 0, blk: 0, to: 0, pf: 0 });
  const [expanded, setExpanded] = React.useState(null);
  return (
    <div>
      <div style={{ display: "flex", alignItems: "baseline", gap: 10, marginBottom: 8, paddingBottom: 6, borderBottom: `1px solid ${color}` }}>
        <span style={{ fontFamily: "var(--f-display)", fontSize: 16, fontWeight: 700, color, letterSpacing: -0.3 }}>{title}</span>
        <span style={{ fontFamily: "var(--f-mono)", fontSize: 10, color: "var(--fg-3)", letterSpacing: 1 }}>{players.length} PLAYERS</span>
      </div>
      <div style={{ overflowX: "auto" }}>
        <table style={{ width: "100%", borderCollapse: "collapse", fontFamily: "var(--f-mono)", fontSize: 10, whiteSpace: "nowrap" }}>
          <thead>
            <tr>
              {cols1.map((c, i) => (
                <th key={c} style={{ padding: "6px 8px", textAlign: i === 1 ? "left" : "center", color: "var(--fg-2)", fontWeight: 700, fontSize: 9, letterSpacing: 1, borderBottom: "1px solid var(--line-2)" }}>{c}</th>
              ))}
              <th style={{ padding: "6px 8px", borderLeft: "2px solid var(--warn)", borderBottom: "1px solid var(--line-2)" }}></th>
              {cols2.map(c => (
                <th key={c} style={{ padding: "6px 8px", textAlign: "center", color: "var(--warn)", fontWeight: 700, fontSize: 9, letterSpacing: 1, borderBottom: "1px solid var(--line-2)" }}>{c}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {players.map((p, i) => {
              const open = expanded === i;
              return (
              <React.Fragment key={i}>
              <tr onClick={() => setExpanded(open ? null : i)} style={{ cursor: "pointer", background: open ? "var(--bg-2)" : "transparent" }}>
                <td style={bsTd({ center: true, color: open ? color : "var(--fg-3)", bold: true, fontSize: 11 })}>{open ? "▾" : "▸"}</td>
                <td style={bsTd({ center: true, color, bold: true })}>{p.num}</td>
                <td style={bsTd({ left: true, font: "var(--f-display)", bold: true, fontSize: 12 })}>{p.name} <span style={{ color: "var(--fg-3)", fontFamily: "var(--f-mono)", fontSize: 9, marginLeft: 3 }}>{p.pos}</span></td>
                <td style={bsTd({ center: true })}>{p.min}</td>
                <td style={bsTd({ center: true, color: "var(--fg-0)", bold: true })}>{p.pts}</td>
                <td style={bsTd({ center: true })}>{p.fg}</td>
                <td style={bsTd({ center: true, color: "var(--fg-2)" })}>{p.fgp}</td>
                <td style={bsTd({ center: true })}>{p.tp}</td>
                <td style={bsTd({ center: true, color: "var(--fg-2)" })}>{p.tpp}</td>
                <td style={bsTd({ center: true })}>{p.ft}</td>
                <td style={bsTd({ center: true, color: "var(--fg-2)" })}>{p.ftp}</td>
                <td style={bsTd({ center: true })}>{p.oreb}</td>
                <td style={bsTd({ center: true })}>{p.dreb}</td>
                <td style={bsTd({ center: true, bold: true })}>{p.reb}</td>
                <td style={bsTd({ center: true })}>{p.ast}</td>
                <td style={bsTd({ center: true })}>{p.stl}</td>
                <td style={bsTd({ center: true })}>{p.blk}</td>
                <td style={bsTd({ center: true })}>{p.to}</td>
                <td style={bsTd({ center: true, color: p.pf >= 4 ? "var(--bad)" : p.pf >= 3 ? "var(--warn)" : "var(--fg-1)", bold: p.pf >= 4 })}>{p.pf}</td>
                <td style={{ borderLeft: "2px solid var(--warn)", borderBottom: "1px solid var(--line-1)" }}></td>
                <td style={bsTd({ center: true, color: p.pm.startsWith("+") ? "var(--good)" : "var(--bad)", bold: true })}>{p.pm}</td>
                <td style={bsTd({ center: true, color: "var(--warn)", bold: true })}>{p.eff}</td>
                <td style={bsTd({ center: true, color: "var(--good)" })}>{p.ts}</td>
                <td style={bsTd({ center: true, color: "var(--cool)" })}>{p.efg}</td>
                <td style={bsTd({ center: true })}>{p.at}</td>
              </tr>
              {open && (
                <tr>
                  <td colSpan={cols1.length + cols2.length + 1} style={{ padding: 0, background: "var(--bg-2)", borderBottom: `2px solid ${color}` }}>
                    <PlayerMiniDetail player={p} color={color} />
                  </td>
                </tr>
              )}
              </React.Fragment>
              );
            })}
            {/* Totals row */}
            <tr style={{ borderTop: `1px solid ${color}` }}>
              <td style={bsTd({ center: true })}></td>
              <td style={bsTd({ center: true })}></td>
              <td style={bsTd({ left: true, color: "var(--fg-2)", bold: true, fontSize: 10 })}>TOTAL</td>
              <td style={bsTd({ center: true })}></td>
              <td style={bsTd({ center: true, color, bold: true, fontSize: 12 })}>{totals.pts}</td>
              <td style={bsTd({ center: true })}></td>
              <td style={bsTd({ center: true })}></td>
              <td style={bsTd({ center: true })}></td>
              <td style={bsTd({ center: true })}></td>
              <td style={bsTd({ center: true })}></td>
              <td style={bsTd({ center: true })}></td>
              <td style={bsTd({ center: true })}></td>
              <td style={bsTd({ center: true })}></td>
              <td style={bsTd({ center: true, color: "var(--fg-1)", bold: true })}>{totals.reb}</td>
              <td style={bsTd({ center: true, color: "var(--fg-1)", bold: true })}>{totals.ast}</td>
              <td style={bsTd({ center: true, color: "var(--fg-1)" })}>{totals.stl}</td>
              <td style={bsTd({ center: true, color: "var(--fg-1)" })}>{totals.blk}</td>
              <td style={bsTd({ center: true, color: "var(--fg-1)" })}>{totals.to}</td>
              <td style={bsTd({ center: true, color: "var(--fg-1)" })}>{totals.pf}</td>
              <td style={{ borderLeft: "2px solid var(--warn)" }}></td>
              <td style={bsTd({ center: true })}></td>
              <td style={bsTd({ center: true })}></td>
              <td style={bsTd({ center: true })}></td>
              <td style={bsTd({ center: true })}></td>
              <td style={bsTd({ center: true })}></td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  );
}

function bsTd({ left, center, color, bold, font, fontSize }) {
  return {
    padding: "8px 8px",
    textAlign: left ? "left" : center ? "center" : "right",
    borderBottom: "1px solid var(--line-1)",
    color: color || "var(--fg-1)",
    fontWeight: bold ? 700 : 400,
    fontFamily: font || "var(--f-mono)",
    fontSize: fontSize || 10,
  };
}

// ---- Player mini detail (B6) — pseudo-random shot map + quarter splits + zone distribution ----
function PlayerMiniDetail({ player, color }) {
  // deterministic shot generation seeded by player number+name
  const seed = (player.num * 31 + player.name.length * 7) % 100;
  const shots = React.useMemo(() => {
    const fgMatch = String(player.fg).match(/(\d+)\s*\/\s*(\d+)/);
    const tpMatch = String(player.tp).match(/(\d+)\s*\/\s*(\d+)/);
    const fgM = fgMatch ? +fgMatch[1] : 0;
    const fgA = fgMatch ? +fgMatch[2] : 0;
    const tpM = tpMatch ? +tpMatch[1] : 0;
    const tpA = tpMatch ? +tpMatch[2] : 0;
    // half-court canvas 500 × 480 (basket at (60, 240), arc ~ r=180)
    const out = [];
    let r = seed;
    const rand = () => { r = (r * 1103515245 + 12345) & 0x7fffffff; return (r % 1000) / 1000; };
    // 3-pointers — outside arc
    for (let i = 0; i < tpA; i++) {
      const ang = (rand() - 0.5) * Math.PI * 0.85; // -0.42π → 0.42π
      const dist = 200 + rand() * 60;
      const x = 60 + Math.cos(ang) * dist;
      const y = 240 + Math.sin(ang) * dist;
      out.push({ x, y, made: i < tpM, type: 3 });
    }
    // 2-pointers — inside arc / paint
    const twoA = fgA - tpA, twoM = fgM - tpM;
    for (let i = 0; i < twoA; i++) {
      const inPaint = rand() < 0.55;
      let x, y;
      if (inPaint) {
        x = 60 + rand() * 130;
        y = 240 + (rand() - 0.5) * 140;
      } else {
        const ang = (rand() - 0.5) * Math.PI * 0.85;
        const dist = 80 + rand() * 100;
        x = 60 + Math.cos(ang) * dist;
        y = 240 + Math.sin(ang) * dist;
      }
      out.push({ x, y, made: i < twoM, type: 2 });
    }
    return out;
  }, [player]);

  // quarter splits — split PTS unevenly using seed
  const qSplits = React.useMemo(() => {
    const total = player.pts;
    if (!total) return [0, 0, 0, 0];
    let r = seed + 17;
    const rand = () => { r = (r * 1103515245 + 12345) & 0x7fffffff; return (r % 1000) / 1000; };
    const w = [0.25 + rand() * 0.3, 0.15 + rand() * 0.25, 0.15 + rand() * 0.25, 0.15 + rand() * 0.25];
    const sum = w.reduce((a, b) => a + b, 0);
    const norm = w.map(x => x / sum);
    const raw = norm.map(x => Math.round(x * total));
    const diff = total - raw.reduce((a, b) => a + b, 0);
    raw[0] += diff;
    return raw;
  }, [player]);

  const fgM = parseInt(String(player.fg).split("/")[0]) || 0;
  const fgA = parseInt(String(player.fg).split("/")[1]) || 0;
  const made = shots.filter(s => s.made).length;
  const att = shots.length;

  return (
    <div style={{ padding: "20px 24px 24px", display: "grid", gridTemplateColumns: "auto 1fr 280px", gap: 28, alignItems: "start" }}>
      {/* LEFT — half court shot map */}
      <div>
        <div style={{ fontFamily: "var(--f-mono)", fontSize: 9, color: "var(--fg-3)", letterSpacing: 1.5, marginBottom: 6 }}>
          SHOT MAP · {made}/{att} · {att ? Math.round(made/att*100) : 0}%
        </div>
        <svg viewBox="0 0 500 480" style={{ width: 360, height: 346, background: "var(--bg-1)", border: "1px solid var(--line-2)" }}>
          {/* half-court — basket at left */}
          <rect x="0" y="0" width="500" height="480" fill="var(--bg-1)" />
          {/* paint */}
          <rect x="0" y="150" width="190" height="180" fill="none" stroke="var(--line-3)" strokeWidth="1.5" />
          {/* free throw circle */}
          <circle cx="190" cy="240" r="60" fill="none" stroke="var(--line-3)" strokeWidth="1.5" strokeDasharray="4 4" />
          {/* 3pt arc */}
          <path d="M 0,40 L 60,40 A 220,220 0 0 1 60,440 L 0,440" fill="none" stroke="var(--line-3)" strokeWidth="1.5" />
          {/* basket + restricted */}
          <circle cx="60" cy="240" r="6" fill="none" stroke={color} strokeWidth="2" />
          <path d="M 60,200 A 40,40 0 0 1 60,280" fill="none" stroke="var(--line-3)" strokeWidth="1" />
          {/* baseline / sideline */}
          <line x1="0" y1="0" x2="500" y2="0" stroke="var(--line-3)" strokeWidth="1" />
          <line x1="0" y1="480" x2="500" y2="480" stroke="var(--line-3)" strokeWidth="1" />
          {/* shots */}
          {shots.map((s, i) => (
            s.made ? (
              <g key={i}>
                <circle cx={s.x} cy={s.y} r={s.type === 3 ? 7 : 6} fill={color} fillOpacity={0.85} />
                <circle cx={s.x} cy={s.y} r={s.type === 3 ? 7 : 6} fill="none" stroke="#fff" strokeWidth="1" strokeOpacity="0.4" />
              </g>
            ) : (
              <g key={i}>
                <line x1={s.x - 5} y1={s.y - 5} x2={s.x + 5} y2={s.y + 5} stroke="var(--fg-3)" strokeWidth="2" />
                <line x1={s.x - 5} y1={s.y + 5} x2={s.x + 5} y2={s.y - 5} stroke="var(--fg-3)" strokeWidth="2" />
              </g>
            )
          ))}
        </svg>
        <div style={{ display: "flex", gap: 14, marginTop: 6, fontFamily: "var(--f-mono)", fontSize: 9, color: "var(--fg-3)", letterSpacing: 1 }}>
          <span><span style={{ display: "inline-block", width: 8, height: 8, background: color, borderRadius: "50%", verticalAlign: "middle", marginRight: 4 }}></span>MADE</span>
          <span><span style={{ display: "inline-block", width: 8, height: 8, verticalAlign: "middle", marginRight: 4, color: "var(--fg-3)" }}>✕</span>MISSED</span>
        </div>
      </div>

      {/* MIDDLE — quarter splits + zone breakdown */}
      <div style={{ display: "flex", flexDirection: "column", gap: 18 }}>
        <div>
          <div style={{ fontFamily: "var(--f-mono)", fontSize: 9, color: "var(--fg-3)", letterSpacing: 1.5, marginBottom: 8 }}>SCORING BY QUARTER</div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 10 }}>
            {qSplits.map((pts, i) => {
              const max = Math.max(...qSplits, 1);
              const pct = (pts / max) * 100;
              return (
                <div key={i}>
                  <div style={{ fontFamily: "var(--f-mono)", fontSize: 9, color: "var(--fg-3)", letterSpacing: 1, marginBottom: 4 }}>Q{i+1}</div>
                  <div style={{ height: 60, background: "var(--bg-3)", position: "relative", border: "1px solid var(--line-2)" }}>
                    <div style={{ position: "absolute", bottom: 0, left: 0, right: 0, height: `${pct}%`, background: color, opacity: 0.7 }}></div>
                    <div style={{ position: "absolute", bottom: 4, left: 0, right: 0, textAlign: "center", fontFamily: "var(--f-display)", fontSize: 16, fontWeight: 700, color: pts > 0 ? "#fff" : "var(--fg-3)" }}>{pts}</div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        <div>
          <div style={{ fontFamily: "var(--f-mono)", fontSize: 9, color: "var(--fg-3)", letterSpacing: 1.5, marginBottom: 8 }}>SHOT ZONES</div>
          <ZoneBar label="PAINT"     color={color} made={shots.filter(s => s.x < 190 && s.made).length} att={shots.filter(s => s.x < 190).length} />
          <ZoneBar label="MID-RANGE" color={color} made={shots.filter(s => s.x >= 190 && s.type === 2 && s.made).length} att={shots.filter(s => s.x >= 190 && s.type === 2).length} />
          <ZoneBar label="3PT"       color={color} made={shots.filter(s => s.type === 3 && s.made).length} att={shots.filter(s => s.type === 3).length} />
        </div>
      </div>

      {/* RIGHT — efficiency callouts */}
      <div style={{ display: "flex", flexDirection: "column", gap: 10, padding: "0 0 0 24px", borderLeft: "1px solid var(--line-2)" }}>
        <div style={{ fontFamily: "var(--f-mono)", fontSize: 9, color: "var(--fg-3)", letterSpacing: 1.5 }}>EFFICIENCY</div>
        <Stat label="EFF"   value={player.eff} accent="var(--warn)" />
        <Stat label="TS%"   value={`${player.ts}%`} accent="var(--good)" />
        <Stat label="eFG%"  value={`${player.efg}%`} accent="var(--cool)" />
        <Stat label="A/T"   value={player.at} accent="var(--fg-1)" />
        <Stat label="+/-"   value={player.pm} accent={player.pm.startsWith("+") ? "var(--good)" : "var(--bad)"} />
        <div style={{ height: 1, background: "var(--line-2)", margin: "4px 0" }}></div>
        <div style={{ fontFamily: "var(--f-mono)", fontSize: 9, color: "var(--fg-3)", letterSpacing: 1.5 }}>ON-COURT</div>
        <div style={{ display: "flex", gap: 8 }}>
          <button className="cv-btn" style={{ height: 26, fontSize: 9, padding: "0 10px", flex: 1 }}>▶ HIGHLIGHT REEL</button>
          <button className="cv-btn" style={{ height: 26, fontSize: 9, padding: "0 10px", flex: 1 }}>↗ FULL PROFILE</button>
        </div>
      </div>
    </div>
  );
}

function ZoneBar({ label, color, made, att }) {
  const pct = att ? Math.round(made / att * 100) : 0;
  return (
    <div style={{ marginBottom: 8 }}>
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 3, fontFamily: "var(--f-mono)", fontSize: 9, color: "var(--fg-2)", letterSpacing: 1 }}>
        <span>{label}</span>
        <span><span style={{ color: "var(--fg-1)", fontWeight: 700 }}>{made}/{att}</span> · <span style={{ color: pct >= 50 ? "var(--good)" : pct >= 35 ? "var(--warn)" : "var(--bad)" }}>{pct}%</span></span>
      </div>
      <div style={{ height: 6, background: "var(--bg-3)", border: "1px solid var(--line-2)", position: "relative" }}>
        <div style={{ position: "absolute", left: 0, top: 0, bottom: 0, width: `${pct}%`, background: color, opacity: 0.85 }}></div>
      </div>
    </div>
  );
}

function Stat({ label, value, accent }) {
  return (
    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
      <span style={{ fontFamily: "var(--f-mono)", fontSize: 10, color: "var(--fg-2)", letterSpacing: 1 }}>{label}</span>
      <span style={{ fontFamily: "var(--f-display)", fontSize: 18, fontWeight: 700, color: accent, fontVariantNumeric: "tabular-nums" }}>{value}</span>
    </div>
  );
}

// ---- Shot chart (full court) ----
function ShotChart() {
  // Made / miss markers (court is 1000 × 480, half-court mirrored). x: 0-1000, y: 0-480
  const shots = [
    // Falcons (hot)
    { x: 180, y: 240, made: true,  team: "h" }, { x: 165, y: 200, made: true,  team: "h" },
    { x: 220, y: 290, made: true,  team: "h" }, { x: 110, y: 230, made: false, team: "h" },
    { x: 155, y: 320, made: true,  team: "h" }, { x: 280, y: 240, made: true,  team: "h" },
    { x: 70,  y: 240, made: false, team: "h" }, { x: 50,  y: 110, made: true,  team: "h" },
    { x: 50,  y: 370, made: false, team: "h" }, { x: 200, y: 180, made: true,  team: "h" },
    { x: 200, y: 310, made: true,  team: "h" }, { x: 260, y: 130, made: false, team: "h" },
    // Titans (cool, mirrored)
    { x: 820, y: 240, made: true,  team: "a" }, { x: 835, y: 200, made: false, team: "a" },
    { x: 780, y: 290, made: false, team: "a" }, { x: 890, y: 230, made: true,  team: "a" },
    { x: 845, y: 320, made: true,  team: "a" }, { x: 720, y: 240, made: false, team: "a" },
    { x: 930, y: 240, made: true,  team: "a" }, { x: 950, y: 110, made: false, team: "a" },
    { x: 950, y: 370, made: true,  team: "a" }, { x: 800, y: 180, made: false, team: "a" },
    { x: 800, y: 310, made: false, team: "a" }, { x: 740, y: 130, made: true,  team: "a" },
  ];

  return (
    <div style={{ position: "relative", width: "100%", aspectRatio: "1000/480", background: "var(--bg-2)", border: "1px solid var(--line-2)" }}>
      <svg viewBox="0 0 1000 480" style={{ width: "100%", height: "100%" }}>
        {/* Court outline */}
        <rect x="6" y="6" width="988" height="468" fill="none" stroke="var(--fg-3)" strokeOpacity="0.5" strokeWidth="2" />
        {/* Center line */}
        <line x1="500" y1="6" x2="500" y2="474" stroke="var(--fg-3)" strokeOpacity="0.4" strokeWidth="2" />
        {/* Center circle */}
        <circle cx="500" cy="240" r="58" fill="none" stroke="var(--fg-3)" strokeOpacity="0.4" strokeWidth="2" />
        {/* Left key */}
        <rect x="6" y="160" width="170" height="160" fill="none" stroke="var(--fg-3)" strokeOpacity="0.4" strokeWidth="2" />
        <circle cx="176" cy="240" r="58" fill="none" stroke="var(--fg-3)" strokeOpacity="0.4" strokeWidth="2" />
        {/* Right key */}
        <rect x="824" y="160" width="170" height="160" fill="none" stroke="var(--fg-3)" strokeOpacity="0.4" strokeWidth="2" />
        <circle cx="824" cy="240" r="58" fill="none" stroke="var(--fg-3)" strokeOpacity="0.4" strokeWidth="2" />
        {/* Left 3pt */}
        <path d="M 6 60 L 90 60 A 230 230 0 0 1 90 420 L 6 420" fill="none" stroke="var(--fg-3)" strokeOpacity="0.5" strokeWidth="2" strokeDasharray="4,4" />
        {/* Right 3pt */}
        <path d="M 994 60 L 910 60 A 230 230 0 0 0 910 420 L 994 420" fill="none" stroke="var(--fg-3)" strokeOpacity="0.5" strokeWidth="2" strokeDasharray="4,4" />
        {/* Hoops */}
        <circle cx="40" cy="240" r="8" fill="none" stroke="var(--hot)" strokeWidth="2" />
        <circle cx="960" cy="240" r="8" fill="none" stroke="var(--cool)" strokeWidth="2" />

        {/* Shots */}
        {shots.map((s, i) => (
          <g key={i}>
            {s.made ? (
              <circle cx={s.x} cy={s.y} r="9" fill="var(--good)" fillOpacity="0.85" stroke="var(--bg-0)" strokeWidth="1" />
            ) : (
              <g stroke="var(--bad)" strokeOpacity="0.9" strokeWidth="2.5" strokeLinecap="round">
                <line x1={s.x - 6} y1={s.y - 6} x2={s.x + 6} y2={s.y + 6} />
                <line x1={s.x + 6} y1={s.y - 6} x2={s.x - 6} y2={s.y + 6} />
              </g>
            )}
          </g>
        ))}
      </svg>
      <div style={{ position: "absolute", top: 10, left: 14, fontFamily: "var(--f-mono)", fontSize: 9, color: "var(--hot)", letterSpacing: 1.5 }}>← FALCONS</div>
      <div style={{ position: "absolute", top: 10, right: 14, fontFamily: "var(--f-mono)", fontSize: 9, color: "var(--cool)", letterSpacing: 1.5 }}>TITANS →</div>
    </div>
  );
}

// ---- Momentum / scoring run chart ----
function MomentumChart({ home, away }) {
  // Build cumulative score over 32 ticks (8 per quarter)
  const ticks = 32;
  const homeRun = []; const awayRun = [];
  let hAcc = 0, aAcc = 0;
  for (let q = 0; q < 4; q++) {
    const hQ = home.q[q], aQ = away.q[q];
    for (let i = 1; i <= 8; i++) {
      hAcc = (q === 0 ? 0 : home.q.slice(0, q).reduce((s,v)=>s+v,0)) + (hQ * i / 8);
      aAcc = (q === 0 ? 0 : away.q.slice(0, q).reduce((s,v)=>s+v,0)) + (aQ * i / 8);
      homeRun.push(hAcc);
      awayRun.push(aAcc);
    }
  }
  const maxScore = Math.max(...homeRun, ...awayRun);
  const W = 1000, H = 220;
  const xAt = i => 20 + (i / (ticks - 1)) * (W - 40);
  const yAt = v => H - 20 - (v / maxScore) * (H - 40);
  const homePath = homeRun.map((v, i) => `${i === 0 ? "M" : "L"}${xAt(i)},${yAt(v)}`).join(" ");
  const awayPath = awayRun.map((v, i) => `${i === 0 ? "M" : "L"}${xAt(i)},${yAt(v)}`).join(" ");
  const leadPath = homeRun.map((v, i) => `${i === 0 ? "M" : "L"}${xAt(i)},${yAt(Math.abs(v - awayRun[i]))}`).join(" ");

  return (
    <div style={{ background: "var(--bg-2)", border: "1px solid var(--line-2)", padding: 16 }}>
      <svg viewBox={`0 0 ${W} ${H}`} style={{ width: "100%", height: "auto", display: "block" }}>
        {/* Quarter dividers */}
        {[1,2,3].map(q => (
          <line key={q} x1={xAt(q * 8)} y1={20} x2={xAt(q * 8)} y2={H - 20} stroke="var(--line-2)" strokeWidth="1" strokeDasharray="3,3" />
        ))}
        {[1,2,3,4].map(q => (
          <text key={q} x={xAt((q - 1) * 8 + 4)} y={14} fill="var(--fg-3)" fontFamily="var(--f-mono)" fontSize="9" textAnchor="middle" letterSpacing="1.5">Q{q}</text>
        ))}
        {/* Lead area (faint) */}
        <path d={`${homeRun.map((v, i) => `${i === 0 ? "M" : "L"}${xAt(i)},${yAt(v)}`).join(" ")} L${xAt(ticks-1)},${H - 20} L${xAt(0)},${H - 20} Z`} fill="var(--hot)" fillOpacity="0.06" />
        {/* Lines */}
        <path d={awayPath} fill="none" stroke="var(--cool)" strokeWidth="2" />
        <path d={homePath} fill="none" stroke="var(--hot)"  strokeWidth="2.5" />

        {/* End labels */}
        <text x={W - 6} y={yAt(homeRun[ticks - 1]) - 6} fill="var(--hot)" fontFamily="var(--f-display)" fontSize="14" fontWeight="700" textAnchor="end">{home.final}</text>
        <text x={W - 6} y={yAt(awayRun[ticks - 1]) + 16} fill="var(--cool)" fontFamily="var(--f-display)" fontSize="14" fontWeight="700" textAnchor="end">{away.final}</text>
      </svg>
      <div style={{ display: "flex", gap: 18, marginTop: 8, fontFamily: "var(--f-mono)", fontSize: 10, color: "var(--fg-2)", letterSpacing: 1 }}>
        <span><span style={{ color: "var(--hot)" }}>━</span> {home.name}</span>
        <span><span style={{ color: "var(--cool)" }}>━</span> {away.name}</span>
        <span style={{ flex: 1 }}></span>
        <span style={{ color: "var(--fg-3)" }}>BIGGEST LEAD · FAL +18 (Q4 04:12)</span>
      </div>
    </div>
  );
}

window.CvResultDetailScreen = CvResultDetailScreen;
