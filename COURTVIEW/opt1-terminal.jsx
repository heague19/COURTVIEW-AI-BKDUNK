// =============================================================================
// OPTION 1 — TERMINAL
// Bloomberg/TradingView density. Mono-heavy, ASCII-grid feel, ticker tape.
// =============================================================================

function Opt1Terminal() {
  const d = window.cvData;
  return (
    <div style={{ background: "var(--bg-1)", color: "var(--fg-0)", height: "100%", display: "flex", flexDirection: "column", overflow: "hidden", fontFamily: "var(--f-mono)" }}>
      <TopNav active="home" />
      <Ticker items={d.ticker} />

      {/* Status strip */}
      <div style={{
        display: "grid", gridTemplateColumns: "repeat(8, 1fr)",
        borderBottom: "1px solid var(--line-2)", fontFamily: "var(--f-mono)", fontSize: 11
      }}>
        {[
          ["TOURNEY", d.tournament.code, "var(--hot)"],
          ["TEAMS", d.tournament.teams, "var(--fg-0)"],
          ["DONE", d.tournament.done, "var(--good)"],
          ["LEFT", d.tournament.left, "var(--cool)"],
          ["TOTAL", d.tournament.total, "var(--fg-0)"],
          ["%", Math.round(d.tournament.done / d.tournament.total * 100) + "%", "var(--fg-0)"],
          ["GPU", "12.4ms", "var(--good)"],
          ["DISK", "142/2000", "var(--fg-1)"],
        ].map(([k, v, c], i) => (
          <div key={i} style={{ padding: "8px 14px", borderRight: i < 7 ? "1px solid var(--line-1)" : "none", display: "flex", justifyContent: "space-between", gap: 12 }}>
            <span style={{ color: "var(--fg-2)", letterSpacing: 0.6 }}>{k}</span>
            <span style={{ color: c, fontWeight: 600 }}>{v}</span>
          </div>
        ))}
      </div>

      {/* Main grid */}
      <div style={{ flex: 1, display: "grid", gridTemplateColumns: "minmax(0,1fr) minmax(0,1fr) 320px", gap: 1, background: "var(--line-2)", overflow: "hidden" }}>

        {/* Tournament panel */}
        <div style={{ background: "var(--bg-1)", padding: 16, overflow: "auto" }}>
          <PanelHead label="TOURNAMENT" code={d.tournament.code} />
          <div style={{ fontFamily: "var(--f-display)", fontSize: 28, fontWeight: 600, letterSpacing: -0.5, marginTop: 4 }}>{d.tournament.name}</div>
          <div style={{ display: "flex", gap: 12, marginTop: 6, fontSize: 11, color: "var(--fg-2)" }}>
            <span>{d.tournament.dates}</span><span>·</span>
            <span>{d.tournament.venue}</span><span>·</span>
            <span style={{ color: "var(--hot)" }}>{d.tournament.format}</span>
          </div>

          {/* Progress as ASCII bar */}
          <div style={{ marginTop: 18, fontFamily: "var(--f-mono)", fontSize: 11 }}>
            <div style={{ display: "flex", justifyContent: "space-between", color: "var(--fg-2)", marginBottom: 4 }}>
              <span>PROGRESS</span><span>{d.tournament.done}/{d.tournament.total}</span>
            </div>
            <AsciiBar pct={d.tournament.done / d.tournament.total} />
          </div>

          {/* Today schedule as table */}
          <div style={{ marginTop: 22 }}>
            <PanelHead label="TODAY · 05.07" />
            <table style={{ width: "100%", marginTop: 8, fontSize: 12, fontFamily: "var(--f-mono)", borderCollapse: "collapse" }}>
              <thead>
                <tr style={{ color: "var(--fg-2)", fontSize: 10, letterSpacing: 0.6 }}>
                  <th style={th}>TIME</th><th style={th}>GRP</th><th style={{ ...th, textAlign: "left" }}>MATCHUP</th>
                  <th style={th}>STAT</th><th style={th}>SCORE</th>
                </tr>
              </thead>
              <tbody>
                {d.todayMatches.map((m, i) => (
                  <tr key={i} style={{ borderTop: "1px solid var(--line-1)" }}>
                    <td style={td}>{m.time}</td>
                    <td style={td}>{m.group}</td>
                    <td style={{ ...td, textAlign: "left", fontFamily: "var(--f-sans)", fontWeight: 600 }}>
                      {m.home} <span style={{ color: "var(--fg-3)" }}>vs</span> {m.away}
                    </td>
                    <td style={td}>
                      {m.status === "live" && <span className="cv-tag live" style={{ padding: "1px 6px" }}>● LIVE {m.q}</span>}
                      {m.status === "done" && <span style={{ color: "var(--fg-2)" }}>FINAL</span>}
                      {m.status === "scheduled" && <span style={{ color: "var(--cool)" }}>SCHED</span>}
                    </td>
                    <td style={{ ...td, color: m.status === "live" ? "var(--hot)" : "var(--fg-0)" }}>
                      {m.hs != null ? `${m.hs}-${m.as}` : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Group standings as terminal tables */}
          <div style={{ marginTop: 22, display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
            {Object.entries(d.groups).map(([g, rows]) => (
              <div key={g}>
                <PanelHead label={`GROUP ${g}`} sub={`${rows.length} TEAMS`} />
                <table style={{ width: "100%", marginTop: 6, fontSize: 11, fontFamily: "var(--f-mono)", borderCollapse: "collapse" }}>
                  <thead><tr style={{ color: "var(--fg-2)", fontSize: 10 }}>
                    <th style={th}>#</th><th style={{ ...th, textAlign: "left" }}>TEAM</th>
                    <th style={th}>W</th><th style={th}>L</th><th style={th}>+/-</th>
                  </tr></thead>
                  <tbody>{rows.map((r, i) => (
                    <tr key={i} style={{ borderTop: "1px solid var(--line-1)", color: i < 2 ? "var(--fg-0)" : "var(--fg-1)" }}>
                      <td style={{ ...td, color: i < 2 ? "var(--hot)" : "var(--fg-3)", fontWeight: 700 }}>{i + 1}</td>
                      <td style={{ ...td, textAlign: "left", fontFamily: "var(--f-sans)", fontWeight: 600 }}>
                        {i < 2 && <span style={{ color: "var(--hot)", marginRight: 4 }}>▸</span>}
                        {r.team}
                      </td>
                      <td style={{ ...td, color: "var(--good)" }}>{r.w}</td>
                      <td style={{ ...td, color: r.l ? "var(--bad)" : "var(--fg-2)" }}>{r.l}</td>
                      <td style={{ ...td, color: r.diff > 0 ? "var(--good)" : r.diff < 0 ? "var(--bad)" : "var(--fg-1)" }}>
                        {r.diff > 0 ? "+" : ""}{r.diff}
                      </td>
                    </tr>
                  ))}</tbody>
                </table>
              </div>
            ))}
          </div>
        </div>

        {/* LIVE match panel */}
        <div style={{ background: "var(--bg-1)", padding: 16, overflow: "auto" }}>
          <PanelHead label="LIVE · NOW" hot />
          <div style={{ marginTop: 8, padding: 16, background: "var(--bg-2)", border: "1px solid var(--line-2)" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 10 }}>
              <span className="cv-tag live"><span style={{ width: 6, height: 6, background: "var(--bad)", borderRadius: "50%" }}></span> LIVE</span>
              <span style={{ fontFamily: "var(--f-mono)", fontSize: 11, color: "var(--fg-1)" }}>GROUP B · Q3 · 07:24</span>
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr auto 1fr", alignItems: "center", gap: 24 }}>
              <div>
                <div style={{ fontSize: 11, color: "var(--fg-2)", letterSpacing: 0.6 }}>HOME · #11 LED</div>
                <div style={{ fontFamily: "var(--f-display)", fontSize: 24, fontWeight: 700 }}>VOLTS</div>
                <div style={{ fontFamily: "var(--f-mono)", fontSize: 56, fontWeight: 700, color: "var(--hot)", lineHeight: 1, marginTop: 6 }}>41</div>
              </div>
              <div style={{ fontFamily: "var(--f-display)", fontSize: 22, color: "var(--fg-3)", padding: "0 4px" }}>:</div>
              <div style={{ textAlign: "right" }}>
                <div style={{ fontSize: 11, color: "var(--fg-2)", letterSpacing: 0.6 }}>AWAY</div>
                <div style={{ fontFamily: "var(--f-display)", fontSize: 24, fontWeight: 700 }}>BLAZERS</div>
                <div style={{ fontFamily: "var(--f-mono)", fontSize: 56, fontWeight: 700, color: "var(--cool)", lineHeight: 1, marginTop: 6 }}>38</div>
              </div>
            </div>
            {/* Quarter scoreline */}
            <div style={{ marginTop: 14, display: "grid", gridTemplateColumns: "60px repeat(4, 1fr) 60px", fontFamily: "var(--f-mono)", fontSize: 11, gap: 1, background: "var(--line-2)" }}>
              {["", "Q1", "Q2", "Q3", "Q4", "TOT"].map((h, i) => (
                <div key={i} style={{ background: "var(--bg-1)", padding: "4px 6px", color: "var(--fg-2)", textAlign: "center", fontSize: 10 }}>{h}</div>
              ))}
              {[["VOLTS", 18, 12, 11, "—", 41], ["BLAZ", 14, 13, 11, "—", 38]].map((row, i) => (
                row.map((c, j) => (
                  <div key={j} style={{ background: "var(--bg-1)", padding: "5px 6px", textAlign: j === 0 ? "left" : "center",
                                         color: j === 5 ? "var(--hot)" : "var(--fg-0)", fontWeight: j === 0 || j === 5 ? 700 : 400 }}>{c}</div>
                ))
              ))}
            </div>
          </div>

          {/* Play-by-play */}
          <div style={{ marginTop: 18 }}>
            <PanelHead label="PLAY-BY-PLAY" sub={`${d.events.length} EVENTS`} />
            <div style={{ marginTop: 8, fontFamily: "var(--f-mono)", fontSize: 11 }}>
              {d.events.map((e, i) => (
                <div key={i} style={{ display: "grid", gridTemplateColumns: "60px 50px 60px 1fr 30px", padding: "5px 0", borderTop: "1px solid var(--line-1)", alignItems: "center" }}>
                  <span style={{ color: "var(--fg-2)" }}>{e.q} {e.t}</span>
                  <span style={{ color: e.icon === "score" ? "var(--hot)" : e.icon === "foul" ? "var(--bad)" : "var(--cool)", fontWeight: 700 }}>
                    {e.icon === "score" ? "SCO" : e.icon === "foul" ? "FL" : e.icon === "to" ? "TO" : "SUB"}
                  </span>
                  <span style={{ color: "var(--fg-0)", fontWeight: 600 }}>{e.team}</span>
                  <span style={{ color: "var(--fg-1)", fontFamily: "var(--f-sans)" }}>{e.text}</span>
                  <span style={{ color: "var(--good)", textAlign: "right" }}>{e.pts || ""}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Leaders */}
          <div style={{ marginTop: 18 }}>
            <PanelHead label="GAME LEADERS" />
            <table style={{ width: "100%", marginTop: 6, fontSize: 11, fontFamily: "var(--f-mono)", borderCollapse: "collapse" }}>
              <thead><tr style={{ color: "var(--fg-2)" }}>
                <th style={{ ...th, textAlign: "left" }}>PLAYER</th><th style={th}>TEAM</th>
                <th style={th}>PTS</th><th style={th}>REB</th><th style={th}>AST</th><th style={th}>EFF</th>
              </tr></thead>
              <tbody>{d.leaders.map((p, i) => (
                <tr key={i} style={{ borderTop: "1px solid var(--line-1)" }}>
                  <td style={{ ...td, textAlign: "left", fontFamily: "var(--f-sans)", fontWeight: 600 }}>
                    <span style={{ color: "var(--fg-2)", marginRight: 6 }}>{p.num}</span>{p.player}
                  </td>
                  <td style={{ ...td, color: "var(--fg-1)" }}>{p.team}</td>
                  <td style={{ ...td, color: "var(--hot)", fontWeight: 700 }}>{p.pts}</td>
                  <td style={td}>{p.reb}</td><td style={td}>{p.ast}</td>
                  <td style={{ ...td, color: "var(--good)" }}>{p.eff}</td>
                </tr>
              ))}</tbody>
            </table>
          </div>
        </div>

        {/* Right column: bracket + system */}
        <div style={{ background: "var(--bg-1)", padding: 16, overflow: "auto" }}>
          <PanelHead label="BRACKET" sub="KO ROUND" />
          <BracketCompact />

          <div style={{ marginTop: 22 }}>
            <PanelHead label="SYSTEM" />
            <div style={{ marginTop: 8, fontFamily: "var(--f-mono)", fontSize: 11 }}>
              {Object.entries(d.systemHealth).map(([k, v], i) => (
                <div key={i} style={{ display: "flex", justifyContent: "space-between", padding: "5px 0", borderTop: "1px solid var(--line-1)" }}>
                  <span style={{ color: "var(--fg-2)", textTransform: "uppercase", letterSpacing: 0.6 }}>{k}</span>
                  <span style={{ color: "var(--fg-0)", fontWeight: 600 }}>{v}</span>
                </div>
              ))}
            </div>
          </div>

          <div style={{ marginTop: 22 }}>
            <PanelHead label="CAMERAS" sub="8 RIG" />
            <div style={{ marginTop: 8 }}>
              {d.cameras.map((c, i) => (
                <div key={i} style={{ display: "flex", justifyContent: "space-between", padding: "5px 0", borderTop: "1px solid var(--line-1)", fontSize: 11, fontFamily: "var(--f-mono)" }}>
                  <span style={{ color: "var(--fg-1)" }}>
                    <span style={{ color: c.status === "live" ? "var(--good)" : "var(--bad)", marginRight: 6 }}>●</span>
                    CAM{c.id} · {c.name}
                  </span>
                  <span style={{ color: c.status === "live" ? "var(--fg-0)" : "var(--fg-3)" }}>{c.fps ? c.fps + "fps" : "—"}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

const th = { padding: "6px 6px", textAlign: "center", fontWeight: 600, letterSpacing: 0.6, fontSize: 10, color: "var(--fg-2)" };
const td = { padding: "6px 6px", textAlign: "center" };

function PanelHead({ label, sub, code, hot }) {
  return (
    <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", paddingBottom: 6, borderBottom: "1px solid var(--line-2)" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <span style={{ width: 3, height: 12, background: hot ? "var(--bad)" : "var(--hot)" }}></span>
        <span style={{ fontFamily: "var(--f-mono)", fontSize: 11, fontWeight: 700, letterSpacing: 1, color: "var(--fg-0)" }}>{label}</span>
        {sub && <span style={{ fontFamily: "var(--f-mono)", fontSize: 10, color: "var(--fg-3)" }}>{sub}</span>}
      </div>
      {code && <span style={{ fontFamily: "var(--f-mono)", fontSize: 10, color: "var(--fg-2)" }}>{code}</span>}
    </div>
  );
}

function AsciiBar({ pct }) {
  const cells = 32;
  const filled = Math.round(pct * cells);
  return (
    <div style={{ display: "flex", gap: 1 }}>
      {Array.from({ length: cells }).map((_, i) => (
        <div key={i} style={{ flex: 1, height: 8, background: i < filled ? "var(--hot)" : "var(--bg-3)" }}></div>
      ))}
      <span style={{ marginLeft: 8, color: "var(--hot)", fontWeight: 700 }}>{Math.round(pct * 100)}%</span>
    </div>
  );
}

function BracketCompact() {
  const slot = (label, score, lit) => (
    <div style={{ display: "flex", justifyContent: "space-between", padding: "6px 8px", background: "var(--bg-2)", border: "1px solid var(--line-2)", fontSize: 11, fontFamily: "var(--f-mono)" }}>
      <span style={{ color: lit ? "var(--fg-0)" : "var(--fg-2)", fontWeight: lit ? 700 : 400 }}>{label}</span>
      <span style={{ color: "var(--fg-3)" }}>{score ?? "—"}</span>
    </div>
  );
  return (
    <div style={{ marginTop: 8, display: "grid", gap: 4 }}>
      <div style={{ fontSize: 10, color: "var(--fg-3)", letterSpacing: 0.8 }}>SEMIFINAL</div>
      {slot("A1 · FALCONS")}{slot("B2 · BLAZERS")}
      <div style={{ height: 6 }}></div>
      {slot("B1 · VOLTS")}{slot("A2 · STORM")}
      <div style={{ fontSize: 10, color: "var(--fg-3)", letterSpacing: 0.8, marginTop: 8 }}>FINAL</div>
      {slot("TBD")}{slot("TBD")}
      <div style={{ marginTop: 10, padding: "10px 12px", border: "1px dashed var(--hot)", background: "var(--hot-soft)", textAlign: "center" }}>
        <div style={{ fontSize: 10, color: "var(--fg-2)", letterSpacing: 1 }}>CHAMPION</div>
        <div style={{ fontFamily: "var(--f-display)", fontSize: 14, fontWeight: 700, color: "var(--hot)", marginTop: 2 }}>TBD</div>
      </div>
    </div>
  );
}

window.Opt1Terminal = Opt1Terminal;
