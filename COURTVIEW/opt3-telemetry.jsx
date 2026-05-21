// =============================================================================
// OPTION 3 — TELEMETRY
// Motorsport-style. Numeric channels, gauges, ranked feeds.
// =============================================================================

function Opt3Telemetry() {
  const d = window.cvData;
  return (
    <div style={{ background: "var(--bg-1)", color: "var(--fg-0)", height: "100%", display: "flex", flexDirection: "column", overflow: "hidden" }}>
      <TopNav active="home" />

      {/* Channel strip */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(6, 1fr)", borderBottom: "1px solid var(--line-2)" }}>
        {[
          ["EVENT", d.tournament.code, "var(--hot)", d.tournament.dates],
          ["FORMAT", d.tournament.format, "var(--fg-0)", d.tournament.venue],
          ["CMPLT", `${d.tournament.done}/${d.tournament.total}`, "var(--good)", `${Math.round(d.tournament.done/d.tournament.total*100)}%`],
          ["LIVE", "1 GAME", "var(--bad)", "Q3 · 07:24"],
          ["RIG", "8 CAM", "var(--cool)", "60FPS · 12.4ms"],
          ["GPU", "RTX 4090", "var(--good)", "14.2/24 GB"],
        ].map(([k, v, c, sub], i) => (
          <div key={i} style={{ padding: "12px 16px", borderRight: i < 5 ? "1px solid var(--line-1)" : "none" }}>
            <div style={{ fontFamily: "var(--f-mono)", fontSize: 9, color: "var(--fg-2)", letterSpacing: 1.2 }}>CH{String(i+1).padStart(2,"0")} · {k}</div>
            <div style={{ fontFamily: "var(--f-mono)", fontSize: 16, fontWeight: 700, color: c, marginTop: 2 }}>{v}</div>
            <div style={{ fontFamily: "var(--f-mono)", fontSize: 10, color: "var(--fg-2)", marginTop: 2 }}>{sub}</div>
          </div>
        ))}
      </div>

      <div style={{ flex: 1, display: "grid", gridTemplateColumns: "minmax(0,1.2fr) minmax(0,1fr)", gap: 1, background: "var(--line-2)", overflow: "hidden" }}>

        {/* Left: live game telemetry */}
        <div style={{ background: "var(--bg-1)", padding: 20, overflow: "auto" }}>
          <TmHead label="LIVE TELEMETRY" code="VOLTS · BLAZERS · GRP B" />

          {/* Score gauge */}
          <div style={{ marginTop: 16, padding: 16, background: "var(--bg-2)", border: "1px solid var(--line-2)" }}>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 24 }}>
              <TmTeamPanel name="VOLTS" tag="HOME" score={41} fg="14/28" tp="5/12" ft="8/9" to={7} color="var(--hot)" />
              <TmTeamPanel name="BLAZERS" tag="AWAY" score={38} fg="12/30" tp="3/10" ft="11/14" to={9} color="var(--cool)" right />
            </div>

            {/* Score-difference gauge */}
            <div style={{ marginTop: 20 }}>
              <div style={{ display: "flex", justifyContent: "space-between", fontFamily: "var(--f-mono)", fontSize: 10, color: "var(--fg-2)", letterSpacing: 0.6 }}>
                <span>−20</span><span>EVEN</span><span>+20</span>
              </div>
              <div style={{ position: "relative", height: 8, background: "var(--bg-3)", marginTop: 4 }}>
                <div style={{ position: "absolute", left: "50%", top: 0, bottom: 0, width: 1, background: "var(--fg-3)" }}></div>
                <div style={{ position: "absolute", left: "50%", top: 0, bottom: 0, width: `${Math.abs(3) / 20 * 50}%`, background: "var(--hot)" }}></div>
              </div>
              <div style={{ display: "flex", justifyContent: "center", marginTop: 6 }}>
                <span style={{ fontFamily: "var(--f-display)", fontSize: 16, fontWeight: 700, color: "var(--hot)" }}>VOLTS +3</span>
              </div>
            </div>
          </div>

          {/* Quarter-by-quarter line graph */}
          <div style={{ marginTop: 20 }}>
            <TmHead label="SCORE TRACE" code="Q1—Q4" sub />
            <div style={{ marginTop: 10, padding: 12, background: "var(--bg-2)", border: "1px solid var(--line-2)" }}>
              <ScoreTrace />
            </div>
          </div>

          {/* Leaders ranking */}
          <div style={{ marginTop: 20 }}>
            <TmHead label="LEADERBOARD" code="EFF · ALL ON-COURT" sub />
            <div style={{ marginTop: 10 }}>
              {d.leaders.map((p, i) => (
                <div key={i} style={{
                  display: "grid", gridTemplateColumns: "30px 1fr 50px 50px 50px 60px 80px",
                  padding: "8px 12px", background: "var(--bg-2)", borderBottom: "1px solid var(--line-1)",
                  fontFamily: "var(--f-mono)", fontSize: 12, alignItems: "center"
                }}>
                  <span style={{ color: i === 0 ? "var(--hot)" : "var(--fg-3)", fontWeight: 700 }}>P{i + 1}</span>
                  <div>
                    <span style={{ fontFamily: "var(--f-mono)", color: "var(--fg-2)", marginRight: 8, fontSize: 10 }}>{p.num}</span>
                    <span style={{ fontFamily: "var(--f-display)", fontWeight: 700 }}>{p.player}</span>
                    <span style={{ color: "var(--fg-2)", fontSize: 10, marginLeft: 8 }}>· {p.team}</span>
                  </div>
                  <span style={{ textAlign: "center", color: "var(--fg-1)" }}>{p.pts}p</span>
                  <span style={{ textAlign: "center", color: "var(--fg-1)" }}>{p.reb}r</span>
                  <span style={{ textAlign: "center", color: "var(--fg-1)" }}>{p.ast}a</span>
                  <span style={{ textAlign: "right", color: "var(--good)", fontWeight: 700 }}>EFF {p.eff}</span>
                  <div style={{ height: 6, background: "var(--bg-3)", marginLeft: 12, position: "relative" }}>
                    <div style={{ position: "absolute", left: 0, top: 0, bottom: 0, width: `${p.eff / 35 * 100}%`, background: i === 0 ? "var(--hot)" : "var(--cool)" }}></div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Right: schedule, standings, rig */}
        <div style={{ background: "var(--bg-1)", padding: 20, overflow: "auto" }}>
          {/* Tourney top */}
          <TmHead label="TOURNAMENT" code={d.tournament.code} />
          <div style={{ fontFamily: "var(--f-display)", fontSize: 24, fontWeight: 700, marginTop: 6, letterSpacing: -0.5 }}>{d.tournament.name}</div>
          <div style={{ fontFamily: "var(--f-mono)", fontSize: 11, color: "var(--fg-2)", marginTop: 4 }}>
            {d.tournament.dates} · {d.tournament.venue}
          </div>

          {/* Today queue */}
          <div style={{ marginTop: 20 }}>
            <TmHead label="QUEUE" code="TODAY · 4 GAMES" sub />
            {d.todayMatches.map((m, i) => (
              <div key={i} style={{
                display: "grid", gridTemplateColumns: "60px 50px 1fr 90px",
                padding: "10px 12px", background: i === 1 ? "var(--bg-3)" : "var(--bg-2)",
                borderLeft: i === 1 ? "2px solid var(--bad)" : "2px solid transparent",
                borderBottom: "1px solid var(--line-1)",
                fontFamily: "var(--f-mono)", fontSize: 12, alignItems: "center"
              }}>
                <span style={{ color: "var(--fg-1)" }}>{m.time}</span>
                <span style={{ color: "var(--hot)", fontWeight: 700 }}>GRP {m.group}</span>
                <span style={{ fontFamily: "var(--f-display)", fontWeight: 700 }}>
                  {m.home} <span style={{ color: "var(--fg-3)", fontWeight: 400 }}>vs</span> {m.away}
                </span>
                <span style={{ textAlign: "right" }}>
                  {m.status === "live" && <span style={{ color: "var(--bad)" }}>● LIVE</span>}
                  {m.status === "done" && <span style={{ color: "var(--fg-0)" }}>{m.hs}–{m.as}</span>}
                  {m.status === "scheduled" && <span style={{ color: "var(--cool)" }}>SCHED</span>}
                </span>
              </div>
            ))}
          </div>

          {/* Standings compact */}
          <div style={{ marginTop: 20 }}>
            <TmHead label="STANDINGS" sub />
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 1, background: "var(--line-2)", marginTop: 10 }}>
              {Object.entries(d.groups).map(([g, rows]) => (
                <div key={g} style={{ background: "var(--bg-1)", padding: 10 }}>
                  <div style={{ fontFamily: "var(--f-mono)", fontSize: 10, color: "var(--fg-2)", letterSpacing: 1, marginBottom: 6 }}>GROUP {g}</div>
                  {rows.map((r, i) => (
                    <div key={i} style={{ display: "grid", gridTemplateColumns: "20px 1fr 30px 40px", padding: "5px 0",
                                          fontFamily: "var(--f-mono)", fontSize: 11, alignItems: "center" }}>
                      <span style={{ color: i < 2 ? "var(--hot)" : "var(--fg-3)", fontWeight: 700 }}>{i + 1}</span>
                      <span style={{ fontFamily: "var(--f-display)", fontWeight: 600, color: i < 2 ? "var(--fg-0)" : "var(--fg-1)" }}>{r.team}</span>
                      <span style={{ color: "var(--good)", textAlign: "center" }}>{r.w}-{r.l}</span>
                      <span style={{ color: r.diff > 0 ? "var(--good)" : "var(--bad)", textAlign: "right", fontWeight: 600 }}>
                        {r.diff > 0 ? "+" : ""}{r.diff}
                      </span>
                    </div>
                  ))}
                </div>
              ))}
            </div>
          </div>

          {/* RIG / cameras telemetry */}
          <div style={{ marginTop: 20 }}>
            <TmHead label="RIG STATUS" code="8 CHANNELS" sub />
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 1, background: "var(--line-2)", marginTop: 10 }}>
              {d.cameras.map((c, i) => (
                <div key={i} style={{ background: "var(--bg-2)", padding: "8px 10px", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    <span style={{ width: 6, height: 6, background: c.status === "live" ? "var(--good)" : "var(--bad)", borderRadius: "50%",
                                   boxShadow: c.status === "live" ? "0 0 6px var(--good)" : "none" }}></span>
                    <span style={{ fontFamily: "var(--f-mono)", fontSize: 10, color: "var(--fg-2)" }}>CAM{c.id}</span>
                    <span style={{ fontFamily: "var(--f-display)", fontSize: 11, fontWeight: 600 }}>{c.name}</span>
                  </div>
                  <span style={{ fontFamily: "var(--f-mono)", fontSize: 10, color: c.status === "live" ? "var(--fg-0)" : "var(--fg-3)" }}>
                    {c.status === "live" ? `${c.fps}fps · ${c.ms}ms` : "OFFLINE"}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      <Ticker items={d.ticker} />
    </div>
  );
}

function TmHead({ label, code, sub }) {
  return (
    <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <span style={{ width: 8, height: 8, background: "var(--hot)" }}></span>
        <span style={{ fontFamily: "var(--f-mono)", fontSize: sub ? 10 : 11, fontWeight: 700, letterSpacing: 1.2, color: "var(--fg-0)" }}>{label}</span>
      </div>
      {code && <span style={{ fontFamily: "var(--f-mono)", fontSize: 10, color: "var(--fg-2)", letterSpacing: 0.6 }}>{code}</span>}
    </div>
  );
}

function TmTeamPanel({ name, tag, score, fg, tp, ft, to, color, right }) {
  return (
    <div style={{ textAlign: right ? "right" : "left" }}>
      <div style={{ fontFamily: "var(--f-mono)", fontSize: 10, color: "var(--fg-2)", letterSpacing: 1 }}>{tag}</div>
      <div style={{ fontFamily: "var(--f-display)", fontSize: 22, fontWeight: 700, marginTop: 2 }}>{name}</div>
      <div style={{ fontFamily: "var(--f-mono)", fontSize: 64, fontWeight: 700, color, lineHeight: 0.95, marginTop: 4, letterSpacing: -2 }}>{score}</div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", marginTop: 10, gap: 4, direction: right ? "rtl" : "ltr" }}>
        {[["FG", fg], ["3PT", tp], ["FT", ft], ["TO", to]].map(([k, v], i) => (
          <div key={i} style={{ direction: "ltr" }}>
            <div style={{ fontFamily: "var(--f-mono)", fontSize: 9, color: "var(--fg-2)", letterSpacing: 0.6 }}>{k}</div>
            <div style={{ fontFamily: "var(--f-mono)", fontSize: 12, color: "var(--fg-0)", fontWeight: 600 }}>{v}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

function ScoreTrace() {
  // Simple SVG line chart of cumulative scores over Q1-Q3
  const home = [0, 18, 30, 41];
  const away = [0, 14, 27, 38];
  const W = 480, H = 110;
  const xStep = W / 3;
  const max = 45;
  const path = (arr) => arr.map((v, i) => `${i === 0 ? "M" : "L"} ${i * xStep},${H - v / max * H}`).join(" ");
  return (
    <svg width="100%" height={H} viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" style={{ display: "block" }}>
      {/* grid */}
      {[0, 1, 2, 3].map(i => (
        <line key={i} x1={i * xStep} x2={i * xStep} y1={0} y2={H} stroke="var(--line-2)" strokeWidth={1} />
      ))}
      {[0.25, 0.5, 0.75].map(p => (
        <line key={p} x1={0} x2={W} y1={H * p} y2={H * p} stroke="var(--line-1)" strokeWidth={1} strokeDasharray="2 2" />
      ))}
      {/* paths */}
      <path d={path(home)} fill="none" stroke="var(--hot)" strokeWidth={2} />
      <path d={path(away)} fill="none" stroke="var(--cool)" strokeWidth={2} />
      {home.map((v, i) => <circle key={`h${i}`} cx={i * xStep} cy={H - v / max * H} r={3} fill="var(--hot)" />)}
      {away.map((v, i) => <circle key={`a${i}`} cx={i * xStep} cy={H - v / max * H} r={3} fill="var(--cool)" />)}
      {/* labels */}
      {["Q1", "Q2", "Q3", "Q4"].map((q, i) => (
        <text key={q} x={i * xStep + 4} y={H - 4} fill="var(--fg-3)" fontSize="9" fontFamily="var(--f-mono)">{q}</text>
      ))}
    </svg>
  );
}

window.Opt3Telemetry = Opt3Telemetry;
