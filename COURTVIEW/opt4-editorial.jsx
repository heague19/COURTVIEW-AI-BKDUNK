// =============================================================================
// OPTION 4 — EDITORIAL
// Big editorial layout. Hero typography, generous spacing, magazine grid.
// =============================================================================

function Opt4Editorial() {
  const d = window.cvData;
  return (
    <div style={{ background: "var(--bg-1)", color: "var(--fg-0)", height: "100%", display: "flex", flexDirection: "column", overflow: "hidden" }}>
      <TopNav active="home" />

      <div style={{ flex: 1, overflow: "auto" }}>
        {/* Hero */}
        <div style={{ padding: "40px 56px 28px", borderBottom: "1px solid var(--line-2)", position: "relative", overflow: "hidden" }}>
          <div style={{ position: "absolute", top: 30, right: 56, fontFamily: "var(--f-mono)", fontSize: 11, color: "var(--fg-3)", letterSpacing: 1.4, textAlign: "right" }}>
            <div>ISSUE · 026</div>
            <div style={{ marginTop: 4 }}>05 · 07 · 2026</div>
          </div>
          <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
            <span className="cv-tag hot">{d.tournament.code}</span>
            <span style={{ fontFamily: "var(--f-mono)", fontSize: 11, color: "var(--fg-2)", letterSpacing: 1 }}>DAY 7 · 12 TEAMS · KO STAGE</span>
          </div>
          <h1 style={{ fontFamily: "var(--f-display)", fontSize: 92, fontWeight: 700, letterSpacing: -3, lineHeight: 0.92, marginTop: 14, maxWidth: 1100 }}>
            {d.tournament.name.split(" ").slice(0, 2).join(" ")}<br />
            <span style={{ color: "var(--hot)" }}>{d.tournament.name.split(" ").slice(2).join(" ")}</span>
          </h1>
          <div style={{ display: "flex", gap: 32, marginTop: 18, fontFamily: "var(--f-mono)", fontSize: 12, color: "var(--fg-1)" }}>
            <span><span style={{ color: "var(--fg-3)" }}>WHEN —</span> {d.tournament.dates}</span>
            <span><span style={{ color: "var(--fg-3)" }}>WHERE —</span> {d.tournament.venue}</span>
            <span><span style={{ color: "var(--fg-3)" }}>FORMAT —</span> {d.tournament.format}</span>
          </div>
        </div>

        {/* C11 Headlines slot */}
        <div style={{ borderBottom: "1px solid var(--line-2)", padding: "0 56px" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 14, padding: "18px 0 14px", borderBottom: "1px solid var(--line-1)" }}>
            <span style={{ fontFamily: "var(--f-mono)", fontSize: 10, color: "var(--bad)", letterSpacing: 2, fontWeight: 700 }}>● HEADLINES</span>
            <span style={{ flex: 1, height: 1, background: "var(--line-1)" }}></span>
            <span style={{ fontFamily: "var(--f-mono)", fontSize: 10, color: "var(--fg-3)", letterSpacing: 1.2 }}>AUTO-CURATED · UPDATED 14s AGO</span>
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "1.6fr 1fr 1fr", gap: 0, padding: "20px 0 24px" }}>
            {/* Lead headline */}
            <a href="#analysis" style={{ paddingRight: 32, borderRight: "1px solid var(--line-1)", textDecoration: "none", color: "inherit", display: "block" }}>
              <div style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 8 }}>
                <span className="cv-tag hot" style={{ fontSize: 9 }}>BREAKING</span>
                <span style={{ fontFamily: "var(--f-mono)", fontSize: 10, color: "var(--bad)", letterSpacing: 1.5 }}>● Q3 · LIVE</span>
              </div>
              <div style={{ fontFamily: "var(--f-display)", fontSize: 44, fontWeight: 700, lineHeight: 0.95, letterSpacing: -1.4, textWrap: "pretty" }}>
                VOLTS LEAD <span style={{ color: "var(--hot)" }}>BLAZERS</span> AT THE BREAK,
                <span style={{ color: "var(--fg-3)" }}> PARK ON A 14-PT QUARTER.</span>
              </div>
              <div style={{ fontFamily: "var(--f-mono)", fontSize: 11, color: "var(--fg-2)", marginTop: 12, letterSpacing: 0.4 }}>
                Semifinal · Group B leaders trade runs in second half · Park 24 PTS on 9/12 FG, 31 EFF
              </div>
            </a>

            {/* Two stacked headlines */}
            <div style={{ paddingLeft: 28, paddingRight: 24, borderRight: "1px solid var(--line-1)", display: "flex", flexDirection: "column", gap: 18 }}>
              <a href="#result" style={{ textDecoration: "none", color: "inherit" }}>
                <div style={{ fontFamily: "var(--f-mono)", fontSize: 9, color: "var(--good)", letterSpacing: 1.5, marginBottom: 6 }}>● FINAL · 06.05</div>
                <div style={{ fontFamily: "var(--f-display)", fontSize: 22, fontWeight: 700, lineHeight: 1.05, letterSpacing: -0.5 }}>
                  <span style={{ color: "var(--hot)" }}>FALCONS</span> CRUSH PHANTOMS BY 21 — 4-0 IN GROUP A.
                </div>
                <div style={{ fontFamily: "var(--f-mono)", fontSize: 10, color: "var(--fg-3)", marginTop: 8 }}>91-70 · LARGEST MARGIN OF DAY</div>
              </a>
              <a href="#data" style={{ textDecoration: "none", color: "inherit" }}>
                <div style={{ fontFamily: "var(--f-mono)", fontSize: 9, color: "var(--cool)", letterSpacing: 1.5, marginBottom: 6 }}>◆ TREND</div>
                <div style={{ fontFamily: "var(--f-display)", fontSize: 22, fontWeight: 700, lineHeight: 1.05, letterSpacing: -0.5 }}>
                  3PT VOLUME UP <span style={{ color: "var(--cool)" }}>+18%</span> WEEK-OVER-WEEK ACROSS THE TOURNAMENT.
                </div>
                <div style={{ fontFamily: "var(--f-mono)", fontSize: 10, color: "var(--fg-3)", marginTop: 8 }}>34.2 ATTEMPTS / GAME · LEAGUE-HIGH PACE</div>
              </a>
            </div>

            {/* Watch list */}
            <div style={{ paddingLeft: 24 }}>
              <div style={{ fontFamily: "var(--f-mono)", fontSize: 9, color: "var(--fg-2)", letterSpacing: 1.5, marginBottom: 10 }}>WATCH LIST —</div>
              {[
                { tag: "10 PTS · 4Q", txt: "Storm down 8 with 6:00 left vs Riders" },
                { tag: "MILESTONE", txt: "K. Park 1pt from 100 in tournament" },
                { tag: "BACK-TO-BACK", txt: "Crusaders 3rd game in 4 days · fatigue watch" },
              ].map((w, i) => (
                <div key={i} style={{ paddingBottom: 10, marginBottom: 10, borderBottom: i < 2 ? "1px solid var(--line-1)" : "none" }}>
                  <div style={{ fontFamily: "var(--f-mono)", fontSize: 9, color: "var(--hot)", letterSpacing: 1.2, fontWeight: 700 }}>{w.tag}</div>
                  <div style={{ fontFamily: "var(--f-display)", fontSize: 14, fontWeight: 600, color: "var(--fg-1)", marginTop: 3, lineHeight: 1.2, letterSpacing: -0.2 }}>{w.txt}</div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Stat bar */}
        <div style={{ display: "grid", gridTemplateColumns: "repeat(5, 1fr)", borderBottom: "1px solid var(--line-2)" }}>
          {[
            ["TEAMS", d.tournament.teams],
            ["TOTAL GAMES", d.tournament.total],
            ["COMPLETED", d.tournament.done, "var(--good)"],
            ["IN-PLAY", "1", "var(--bad)"],
            ["REMAINING", d.tournament.left, "var(--cool)"],
          ].map(([k, v, c], i) => (
            <div key={i} style={{ padding: "20px 24px", borderRight: i < 4 ? "1px solid var(--line-1)" : "none" }}>
              <div style={{ fontFamily: "var(--f-mono)", fontSize: 10, color: "var(--fg-2)", letterSpacing: 1.2 }}>{k}</div>
              <div style={{ fontFamily: "var(--f-display)", fontSize: 44, fontWeight: 700, color: c || "var(--fg-0)", lineHeight: 1, marginTop: 4, letterSpacing: -1 }}>{v}</div>
            </div>
          ))}
        </div>

        {/* Featured live + schedule */}
        <div style={{ display: "grid", gridTemplateColumns: "1.4fr 1fr", gap: 1, background: "var(--line-2)" }}>
          {/* Featured live game */}
          <div style={{ background: "var(--bg-1)", padding: "28px 40px" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 16 }}>
              <span style={{ fontFamily: "var(--f-mono)", fontSize: 10, color: "var(--fg-2)", letterSpacing: 2 }}>FEATURED · LIVE</span>
              <span style={{ flex: 1, height: 1, background: "var(--line-2)" }}></span>
              <span className="cv-tag live"><span style={{ width: 6, height: 6, background: "var(--bad)", borderRadius: "50%" }}></span> Q3 · 07:24</span>
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "1fr auto 1fr", gap: 28, alignItems: "start" }}>
              <div>
                <div style={{ fontFamily: "var(--f-mono)", fontSize: 10, color: "var(--fg-2)", letterSpacing: 1 }}>HOME · GROUP B · 3-0</div>
                <div style={{ fontFamily: "var(--f-display)", fontSize: 44, fontWeight: 700, letterSpacing: -1, lineHeight: 1, marginTop: 4 }}>VOLTS</div>
                <div style={{ fontFamily: "var(--f-display)", fontSize: 110, fontWeight: 700, color: "var(--hot)", lineHeight: 0.85, letterSpacing: -5, marginTop: 8 }}>41</div>
              </div>
              <div style={{ paddingTop: 30, textAlign: "center" }}>
                <div style={{ fontFamily: "var(--f-mono)", fontSize: 10, color: "var(--fg-3)", letterSpacing: 2 }}>SEMIFINAL</div>
                <div style={{ fontFamily: "var(--f-display)", fontSize: 32, color: "var(--fg-3)", fontWeight: 700, marginTop: 6 }}>—</div>
                <div style={{ fontFamily: "var(--f-mono)", fontSize: 11, color: "var(--hot)", marginTop: 6, fontWeight: 700 }}>+3 LEAD</div>
              </div>
              <div style={{ textAlign: "right" }}>
                <div style={{ fontFamily: "var(--f-mono)", fontSize: 10, color: "var(--fg-2)", letterSpacing: 1 }}>AWAY · GROUP B · 2-2</div>
                <div style={{ fontFamily: "var(--f-display)", fontSize: 44, fontWeight: 700, letterSpacing: -1, lineHeight: 1, marginTop: 4 }}>BLAZERS</div>
                <div style={{ fontFamily: "var(--f-display)", fontSize: 110, fontWeight: 700, color: "var(--cool)", lineHeight: 0.85, letterSpacing: -5, marginTop: 8 }}>38</div>
              </div>
            </div>

            {/* Mini stat bar */}
            <div style={{ marginTop: 24, display: "grid", gridTemplateColumns: "repeat(4, 1fr)", border: "1px solid var(--line-2)" }}>
              {[
                ["FG%", "50.0", "32.1"],
                ["3PT%", "41.7", "30.0"],
                ["AST", "12", "9"],
                ["REB", "22", "26"],
              ].map(([k, h, a], i) => (
                <div key={i} style={{ padding: "10px 14px", borderRight: i < 3 ? "1px solid var(--line-2)" : "none" }}>
                  <div style={{ fontFamily: "var(--f-mono)", fontSize: 10, color: "var(--fg-2)", letterSpacing: 1, textAlign: "center" }}>{k}</div>
                  <div style={{ display: "flex", justifyContent: "space-between", marginTop: 4, fontFamily: "var(--f-mono)", fontSize: 13, fontWeight: 600 }}>
                    <span style={{ color: parseFloat(h) > parseFloat(a) ? "var(--hot)" : "var(--fg-1)" }}>{h}</span>
                    <span style={{ color: parseFloat(a) > parseFloat(h) ? "var(--cool)" : "var(--fg-1)" }}>{a}</span>
                  </div>
                </div>
              ))}
            </div>

            {/* Top performer headline */}
            <div style={{ marginTop: 24, padding: "20px 24px", background: "var(--bg-2)", borderLeft: "3px solid var(--hot)" }}>
              <div style={{ fontFamily: "var(--f-mono)", fontSize: 10, color: "var(--fg-2)", letterSpacing: 1.5 }}>GAME LEADER · ON COURT NOW</div>
              <div style={{ fontFamily: "var(--f-display)", fontSize: 28, fontWeight: 700, marginTop: 4, letterSpacing: -0.5 }}>
                K. PARK <span style={{ color: "var(--fg-3)" }}>· #11 · VOLTS</span>
              </div>
              <div style={{ display: "flex", gap: 24, marginTop: 8, fontFamily: "var(--f-mono)", fontSize: 13 }}>
                <span><b style={{ color: "var(--hot)", fontSize: 18 }}>24</b> <span style={{ color: "var(--fg-2)" }}>PTS</span></span>
                <span><b style={{ color: "var(--fg-0)", fontSize: 18 }}>8</b> <span style={{ color: "var(--fg-2)" }}>REB</span></span>
                <span><b style={{ color: "var(--fg-0)", fontSize: 18 }}>6</b> <span style={{ color: "var(--fg-2)" }}>AST</span></span>
                <span><b style={{ color: "var(--good)", fontSize: 18 }}>31</b> <span style={{ color: "var(--fg-2)" }}>EFF</span></span>
              </div>
            </div>
          </div>

          {/* Schedule rail */}
          <div style={{ background: "var(--bg-1)", padding: "28px 32px" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 14 }}>
              <span style={{ fontFamily: "var(--f-mono)", fontSize: 10, color: "var(--fg-2)", letterSpacing: 2 }}>TODAY · 05.07</span>
              <span style={{ flex: 1, height: 1, background: "var(--line-2)" }}></span>
              <span style={{ fontFamily: "var(--f-mono)", fontSize: 10, color: "var(--fg-3)" }}>{d.todayMatches.length} GAMES</span>
            </div>
            {d.todayMatches.map((m, i) => (
              <div key={i} style={{ padding: "14px 0", borderBottom: i < d.todayMatches.length - 1 ? "1px solid var(--line-1)" : "none" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6 }}>
                  <span style={{ fontFamily: "var(--f-mono)", fontSize: 11, color: "var(--fg-1)" }}>{m.time} · GRP {m.group}</span>
                  {m.status === "live" && <span className="cv-tag live" style={{ fontSize: 9, padding: "1px 6px" }}>LIVE</span>}
                  {m.status === "done" && <span style={{ fontFamily: "var(--f-mono)", fontSize: 10, color: "var(--fg-3)", letterSpacing: 1 }}>FINAL</span>}
                  {m.status === "scheduled" && <span style={{ fontFamily: "var(--f-mono)", fontSize: 10, color: "var(--cool)", letterSpacing: 1 }}>SCHED</span>}
                </div>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
                  <span style={{ fontFamily: "var(--f-display)", fontSize: 18, fontWeight: 700,
                                 color: m.hs > m.as ? "var(--hot)" : "var(--fg-0)" }}>{m.home}</span>
                  <span style={{ fontFamily: "var(--f-mono)", fontSize: 16, fontWeight: 700,
                                 color: m.status === "live" ? "var(--hot)" : "var(--fg-0)" }}>
                    {m.hs != null ? m.hs : "—"}
                  </span>
                </div>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginTop: 2 }}>
                  <span style={{ fontFamily: "var(--f-display)", fontSize: 18, fontWeight: 700,
                                 color: m.as > m.hs ? "var(--hot)" : "var(--fg-0)" }}>{m.away}</span>
                  <span style={{ fontFamily: "var(--f-mono)", fontSize: 16, fontWeight: 700,
                                 color: m.status === "live" ? "var(--hot)" : "var(--fg-0)" }}>
                    {m.as != null ? m.as : "—"}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Standings + bracket */}
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 1, background: "var(--line-2)" }}>
          {Object.entries(d.groups).map(([g, rows]) => (
            <div key={g} style={{ background: "var(--bg-1)", padding: "28px 32px" }}>
              <div style={{ display: "flex", alignItems: "baseline", gap: 12, marginBottom: 14 }}>
                <span style={{ fontFamily: "var(--f-display)", fontSize: 28, fontWeight: 700, letterSpacing: -0.5 }}>GROUP {g}</span>
                <span style={{ fontFamily: "var(--f-mono)", fontSize: 10, color: "var(--fg-2)", letterSpacing: 1 }}>TOP 2 ADVANCE</span>
              </div>
              {rows.map((r, i) => (
                <div key={i} style={{ display: "grid", gridTemplateColumns: "20px 1fr 50px 50px 60px", padding: "12px 0",
                                      borderBottom: "1px solid var(--line-1)", alignItems: "center" }}>
                  <span style={{ fontFamily: "var(--f-mono)", fontSize: 11, color: i < 2 ? "var(--hot)" : "var(--fg-3)", fontWeight: 700 }}>0{i + 1}</span>
                  <span style={{ fontFamily: "var(--f-display)", fontSize: 16, fontWeight: 700, color: i < 2 ? "var(--fg-0)" : "var(--fg-1)" }}>{r.team}</span>
                  <span style={{ fontFamily: "var(--f-mono)", fontSize: 12, color: "var(--good)", textAlign: "center" }}>{r.w}W</span>
                  <span style={{ fontFamily: "var(--f-mono)", fontSize: 12, color: r.l ? "var(--bad)" : "var(--fg-2)", textAlign: "center" }}>{r.l}L</span>
                  <span style={{ fontFamily: "var(--f-mono)", fontSize: 12, fontWeight: 600,
                                 color: r.diff > 0 ? "var(--good)" : r.diff < 0 ? "var(--bad)" : "var(--fg-1)", textAlign: "right" }}>
                    {r.diff > 0 ? "+" : ""}{r.diff}
                  </span>
                </div>
              ))}
            </div>
          ))}
          <div style={{ background: "var(--bg-1)", padding: "28px 32px" }}>
            <div style={{ display: "flex", alignItems: "baseline", gap: 12, marginBottom: 14 }}>
              <span style={{ fontFamily: "var(--f-display)", fontSize: 28, fontWeight: 700, letterSpacing: -0.5 }}>FINALS</span>
              <span style={{ fontFamily: "var(--f-mono)", fontSize: 10, color: "var(--fg-2)", letterSpacing: 1 }}>KO STAGE</span>
            </div>
            <BcastBracket />
          </div>
        </div>

        {/* Footer engine */}
        <div style={{ display: "grid", gridTemplateColumns: "repeat(6, 1fr)", borderTop: "1px solid var(--line-2)" }}>
          {Object.entries(d.systemHealth).map(([k, v], i) => (
            <div key={i} style={{ padding: "14px 18px", borderRight: i < 5 ? "1px solid var(--line-1)" : "none" }}>
              <div style={{ fontFamily: "var(--f-mono)", fontSize: 10, color: "var(--fg-2)", letterSpacing: 1.2, textTransform: "uppercase" }}>{k}</div>
              <div style={{ fontFamily: "var(--f-mono)", fontSize: 13, color: "var(--fg-0)", marginTop: 4, fontWeight: 600 }}>{v}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// Inline bracket — three tidy KO rows
function BcastBracket() {
  const rows = [
    { round: "QF", a: "FALCONS", as: 78, b: "TITANS",   bs: 64, done: true },
    { round: "QF", a: "VOLTS",   as: 41, b: "BLAZERS",  bs: 38, live: true },
    { round: "SF", a: "STORM",   as: null, b: "—",      bs: null },
    { round: "F",  a: "TBD",     as: null, b: "TBD",    bs: null },
  ];
  return (
    <div>
      {rows.map((r, i) => (
        <div key={i} style={{ padding: "12px 0", borderBottom: i < rows.length - 1 ? "1px solid var(--line-1)" : "none" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6 }}>
            <span style={{ fontFamily: "var(--f-mono)", fontSize: 10, color: "var(--fg-2)", letterSpacing: 1.5 }}>{r.round}</span>
            {r.live && <span className="cv-tag live" style={{ fontSize: 9, padding: "1px 6px" }}>LIVE</span>}
            {r.done && <span style={{ fontFamily: "var(--f-mono)", fontSize: 10, color: "var(--fg-3)", letterSpacing: 1 }}>FINAL</span>}
          </div>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
            <span style={{ fontFamily: "var(--f-display)", fontSize: 16, fontWeight: 700,
                            color: r.as != null && r.as > r.bs ? "var(--hot)" : "var(--fg-1)" }}>{r.a}</span>
            <span style={{ fontFamily: "var(--f-mono)", fontSize: 14, fontWeight: 700,
                            color: r.live ? "var(--hot)" : r.as != null ? "var(--fg-0)" : "var(--fg-3)" }}>{r.as != null ? r.as : "—"}</span>
          </div>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginTop: 2 }}>
            <span style={{ fontFamily: "var(--f-display)", fontSize: 16, fontWeight: 700,
                            color: r.bs != null && r.bs > r.as ? "var(--hot)" : "var(--fg-1)" }}>{r.b}</span>
            <span style={{ fontFamily: "var(--f-mono)", fontSize: 14, fontWeight: 700,
                            color: r.live ? "var(--hot)" : r.bs != null ? "var(--fg-0)" : "var(--fg-3)" }}>{r.bs != null ? r.bs : "—"}</span>
          </div>
        </div>
      ))}
    </div>
  );
}

window.Opt4Editorial = Opt4Editorial;
window.BcastBracket = BcastBracket;
