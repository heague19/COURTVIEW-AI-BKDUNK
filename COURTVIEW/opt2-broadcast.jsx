// =============================================================================
// OPTION 2 — BROADCAST
// ESPN/NBA broadcast graphic. Big display type, diagonal cuts, hero matchup.
// =============================================================================

function Opt2Broadcast() {
  const d = window.cvData;
  return (
    <div style={{ background: "var(--bg-1)", color: "var(--fg-0)", height: "100%", display: "flex", flexDirection: "column", overflow: "hidden" }}>
      <TopNav active="home" />

      <div style={{ flex: 1, overflow: "auto" }}>
        {/* Hero matchup banner */}
        <div style={{ position: "relative", background: "var(--bg-0)", overflow: "hidden", borderBottom: "1px solid var(--line-2)" }}>
          {/* Diagonal slashes */}
          <div style={{ position: "absolute", inset: 0, pointerEvents: "none",
            background: `repeating-linear-gradient(115deg, transparent 0 60px, rgba(255,90,31,0.04) 60px 62px)` }}></div>
          <div style={{ position: "absolute", top: 0, right: 0, bottom: 0, width: "40%",
            background: `linear-gradient(115deg, transparent 0 30%, var(--hot-soft) 30% 70%, transparent 70%)` }}></div>

          <div style={{ position: "relative", padding: "32px 40px 28px", display: "grid", gridTemplateColumns: "1fr auto 1fr", gap: 32, alignItems: "center" }}>
            {/* HOME */}
            <div>
              <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 10 }}>
                <span className="cv-tag live"><span style={{ width: 6, height: 6, background: "var(--bad)", borderRadius: "50%" }}></span> LIVE · GROUP B</span>
                <span style={{ fontFamily: "var(--f-mono)", fontSize: 11, color: "var(--fg-2)", letterSpacing: 0.8 }}>Q3 · 07:24</span>
              </div>
              <div style={{ fontFamily: "var(--f-mono)", fontSize: 11, color: "var(--fg-2)", letterSpacing: 1 }}>HOME · #11 LED · 3W-0L</div>
              <div style={{ display: "flex", alignItems: "baseline", gap: 16, marginTop: 4 }}>
                <div style={{ fontFamily: "var(--f-display)", fontSize: 56, fontWeight: 700, letterSpacing: -2, lineHeight: 0.95 }}>VOLTS</div>
              </div>
              <div style={{ fontFamily: "var(--f-display)", fontSize: 140, fontWeight: 700, color: "var(--hot)", lineHeight: 0.85, letterSpacing: -6, marginTop: 6 }}>41</div>
              <div style={{ display: "flex", gap: 12, marginTop: 10, fontFamily: "var(--f-mono)", fontSize: 11, color: "var(--fg-1)" }}>
                <span>FG <b style={{ color: "var(--fg-0)" }}>14/28</b></span>
                <span>3PT <b style={{ color: "var(--fg-0)" }}>5/12</b></span>
                <span>FT <b style={{ color: "var(--fg-0)" }}>8/9</b></span>
                <span>TO <b style={{ color: "var(--fg-0)" }}>7</b></span>
              </div>
            </div>

            {/* CENTER MATCHUP */}
            <div style={{ textAlign: "center" }}>
              <div style={{ fontFamily: "var(--f-mono)", fontSize: 10, letterSpacing: 2, color: "var(--fg-2)" }}>SEMIFINAL · KO</div>
              <div style={{ fontFamily: "var(--f-display)", fontSize: 60, fontWeight: 700, color: "var(--fg-3)", letterSpacing: -2, lineHeight: 1 }}>VS</div>
              <div style={{ fontFamily: "var(--f-display)", fontSize: 16, fontWeight: 700, color: "var(--hot)", marginTop: 6 }}>+3</div>
              <div style={{ fontFamily: "var(--f-mono)", fontSize: 10, color: "var(--fg-2)", marginTop: 2, letterSpacing: 0.8 }}>VOLTS LEAD</div>
            </div>

            {/* AWAY */}
            <div style={{ textAlign: "right" }}>
              <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 10, justifyContent: "flex-end" }}>
                <span style={{ fontFamily: "var(--f-mono)", fontSize: 11, color: "var(--fg-2)", letterSpacing: 0.8 }}>2W-2L</span>
                <span className="cv-tag cool">AWAY · #42 BLU</span>
              </div>
              <div style={{ fontFamily: "var(--f-display)", fontSize: 56, fontWeight: 700, letterSpacing: -2, lineHeight: 0.95 }}>BLAZERS</div>
              <div style={{ fontFamily: "var(--f-display)", fontSize: 140, fontWeight: 700, color: "var(--cool)", lineHeight: 0.85, letterSpacing: -6, marginTop: 6 }}>38</div>
              <div style={{ display: "flex", gap: 12, marginTop: 10, fontFamily: "var(--f-mono)", fontSize: 11, color: "var(--fg-1)", justifyContent: "flex-end" }}>
                <span>FG <b style={{ color: "var(--fg-0)" }}>12/30</b></span>
                <span>3PT <b style={{ color: "var(--fg-0)" }}>3/10</b></span>
                <span>FT <b style={{ color: "var(--fg-0)" }}>11/14</b></span>
                <span>TO <b style={{ color: "var(--fg-0)" }}>9</b></span>
              </div>
            </div>
          </div>

          {/* Quarter strip */}
          <div style={{ display: "grid", gridTemplateColumns: "120px repeat(5, 1fr)", borderTop: "1px solid var(--line-2)", fontFamily: "var(--f-mono)", fontSize: 12 }}>
            {["", "Q1", "Q2", "Q3", "Q4", "TOT"].map((h, i) => (
              <div key={i} style={{ padding: "8px 14px", borderRight: i < 5 ? "1px solid var(--line-1)" : "none", color: "var(--fg-2)", fontSize: 10, letterSpacing: 1, textAlign: i === 0 ? "left" : "center" }}>{h}</div>
            ))}
            {[
              ["VOLTS", 18, 12, 11, "—", 41, "var(--hot)"],
              ["BLAZERS", 14, 13, 11, "—", 38, "var(--cool)"]
            ].map((row, ri) => row.map((c, ci) => (
              <div key={`${ri}-${ci}`} style={{
                padding: "10px 14px", borderTop: "1px solid var(--line-1)",
                borderRight: ci < 5 ? "1px solid var(--line-1)" : "none",
                fontWeight: ci === 0 ? 700 : ci === 5 ? 700 : 400,
                color: ci === 0 ? row[6] : ci === 5 ? "var(--fg-0)" : "var(--fg-1)",
                textAlign: ci === 0 ? "left" : "center",
                fontFamily: ci === 0 ? "var(--f-display)" : "var(--f-mono)"
              }}>{c}</div>
            )))}
          </div>
        </div>

        {/* Tournament + system row */}
        <div style={{ display: "grid", gridTemplateColumns: "1.4fr 1fr 1fr", gap: 1, background: "var(--line-2)" }}>

          {/* Tournament block */}
          <div style={{ background: "var(--bg-1)", padding: 24 }}>
            <SectionHead label="TOURNAMENT" sub={d.tournament.code} />
            <div style={{ fontFamily: "var(--f-display)", fontSize: 32, fontWeight: 700, letterSpacing: -1, marginTop: 8 }}>{d.tournament.name}</div>
            <div style={{ display: "flex", gap: 14, marginTop: 6, fontFamily: "var(--f-mono)", fontSize: 11, color: "var(--fg-2)", letterSpacing: 0.5 }}>
              <span>{d.tournament.dates}</span><span>·</span>
              <span>{d.tournament.venue}</span>
            </div>

            {/* Big stats */}
            <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", marginTop: 22, gap: 0, border: "1px solid var(--line-2)" }}>
              {[
                ["TEAMS", d.tournament.teams, "var(--fg-0)"],
                ["TOTAL", d.tournament.total, "var(--fg-0)"],
                ["DONE", d.tournament.done, "var(--good)"],
                ["LEFT", d.tournament.left, "var(--cool)"],
              ].map(([k, v, c], i) => (
                <div key={i} style={{ padding: "16px 18px", borderRight: i < 3 ? "1px solid var(--line-2)" : "none" }}>
                  <div style={{ fontFamily: "var(--f-mono)", fontSize: 10, color: "var(--fg-2)", letterSpacing: 1 }}>{k}</div>
                  <div style={{ fontFamily: "var(--f-display)", fontSize: 36, fontWeight: 700, color: c, marginTop: 2, lineHeight: 1 }}>{v}</div>
                </div>
              ))}
            </div>

            {/* Today schedule cards */}
            <div style={{ marginTop: 22 }}>
              <SectionHead label="TODAY" sub="05.07 · 4 GAMES" />
              <div style={{ display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: 10, marginTop: 10 }}>
                {d.todayMatches.map((m, i) => <BcastMatchCard key={i} m={m} />)}
              </div>
            </div>
          </div>

          {/* Standings */}
          <div style={{ background: "var(--bg-1)", padding: 24 }}>
            <SectionHead label="STANDINGS" sub="GROUP A · B" />
            {Object.entries(d.groups).map(([g, rows]) => (
              <div key={g} style={{ marginTop: 16 }}>
                <div style={{ display: "flex", alignItems: "baseline", gap: 8, marginBottom: 6 }}>
                  <span style={{ fontFamily: "var(--f-display)", fontSize: 22, fontWeight: 700, color: "var(--hot)" }}>GRP {g}</span>
                  <span style={{ fontFamily: "var(--f-mono)", fontSize: 10, color: "var(--fg-2)", letterSpacing: 1 }}>TOP 2 ADVANCE</span>
                </div>
                <div style={{ display: "grid", gap: 1, background: "var(--line-2)" }}>
                  {rows.map((r, i) => (
                    <div key={i} style={{ display: "grid", gridTemplateColumns: "20px 1fr 30px 30px 50px", padding: "10px 12px", background: "var(--bg-2)",
                                          borderLeft: i < 2 ? "3px solid var(--hot)" : "3px solid transparent",
                                          fontFamily: "var(--f-mono)", fontSize: 12, alignItems: "center" }}>
                      <span style={{ color: i < 2 ? "var(--hot)" : "var(--fg-3)", fontWeight: 700 }}>{i + 1}</span>
                      <span style={{ fontFamily: "var(--f-display)", fontWeight: 700, color: "var(--fg-0)" }}>{r.team}</span>
                      <span style={{ color: "var(--good)", textAlign: "center" }}>{r.w}</span>
                      <span style={{ color: r.l ? "var(--bad)" : "var(--fg-2)", textAlign: "center" }}>{r.l}</span>
                      <span style={{ color: r.diff > 0 ? "var(--good)" : r.diff < 0 ? "var(--bad)" : "var(--fg-1)", textAlign: "right", fontWeight: 600 }}>
                        {r.diff > 0 ? "+" : ""}{r.diff}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>

          {/* Bracket + system */}
          <div style={{ background: "var(--bg-1)", padding: 24 }}>
            <SectionHead label="KO BRACKET" />
            <BcastBracket />

            <div style={{ marginTop: 24 }}>
              <SectionHead label="ENGINE" sub="LIVE" />
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 1, background: "var(--line-2)", marginTop: 10 }}>
                {Object.entries(d.systemHealth).map(([k, v], i) => (
                  <div key={i} style={{ background: "var(--bg-2)", padding: "10px 12px" }}>
                    <div style={{ fontFamily: "var(--f-mono)", fontSize: 10, color: "var(--fg-2)", letterSpacing: 0.8, textTransform: "uppercase" }}>{k}</div>
                    <div style={{ fontFamily: "var(--f-mono)", fontSize: 13, fontWeight: 600, color: "var(--fg-0)", marginTop: 2 }}>{v}</div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>

      <Ticker items={d.ticker} />
    </div>
  );
}

function SectionHead({ label, sub }) {
  return (
    <div style={{ display: "flex", alignItems: "baseline", gap: 10, paddingBottom: 6, borderBottom: "2px solid var(--hot)" }}>
      <span style={{ fontFamily: "var(--f-display)", fontSize: 14, fontWeight: 700, letterSpacing: 1, color: "var(--fg-0)" }}>{label}</span>
      {sub && <span style={{ fontFamily: "var(--f-mono)", fontSize: 10, color: "var(--fg-2)", letterSpacing: 0.8 }}>{sub}</span>}
    </div>
  );
}

function BcastMatchCard({ m }) {
  return (
    <div style={{ position: "relative", background: "var(--bg-2)", border: "1px solid var(--line-2)", padding: 12,
                  borderLeft: m.status === "live" ? "3px solid var(--bad)" : m.status === "done" ? "3px solid var(--fg-3)" : "3px solid var(--cool)" }}>
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 8 }}>
        <span style={{ fontFamily: "var(--f-mono)", fontSize: 10, color: "var(--fg-2)", letterSpacing: 1 }}>GROUP {m.group} · {m.time}</span>
        {m.status === "live" && <span className="cv-tag live" style={{ padding: "1px 6px", fontSize: 9 }}>LIVE</span>}
        {m.status === "done" && <span style={{ fontFamily: "var(--f-mono)", fontSize: 10, color: "var(--fg-2)" }}>FINAL</span>}
        {m.status === "scheduled" && <span style={{ fontFamily: "var(--f-mono)", fontSize: 10, color: "var(--cool)" }}>SCHED</span>}
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "1fr auto 1fr", gap: 12, alignItems: "center" }}>
        <div>
          <div style={{ fontFamily: "var(--f-display)", fontSize: 18, fontWeight: 700 }}>{m.home}</div>
          {m.hs != null && <div style={{ fontFamily: "var(--f-mono)", fontSize: 28, fontWeight: 700, color: m.hs > m.as ? "var(--hot)" : "var(--fg-1)" }}>{m.hs}</div>}
        </div>
        <div style={{ fontFamily: "var(--f-display)", fontSize: 14, color: "var(--fg-3)" }}>VS</div>
        <div style={{ textAlign: "right" }}>
          <div style={{ fontFamily: "var(--f-display)", fontSize: 18, fontWeight: 700 }}>{m.away}</div>
          {m.as != null && <div style={{ fontFamily: "var(--f-mono)", fontSize: 28, fontWeight: 700, color: m.as > m.hs ? "var(--hot)" : "var(--fg-1)" }}>{m.as}</div>}
        </div>
      </div>
    </div>
  );
}

function BcastBracket() {
  const slot = (label, score, lit) => (
    <div style={{
      display: "flex", justifyContent: "space-between", padding: "8px 12px",
      background: "var(--bg-2)", border: "1px solid var(--line-2)",
      fontFamily: "var(--f-display)", fontSize: 13, fontWeight: 700,
      color: lit ? "var(--fg-0)" : "var(--fg-2)"
    }}>
      <span>{label}</span>
      <span style={{ fontFamily: "var(--f-mono)", color: "var(--fg-3)" }}>{score ?? "—"}</span>
    </div>
  );
  return (
    <div style={{ marginTop: 12, display: "grid", gap: 4 }}>
      <div style={{ fontFamily: "var(--f-mono)", fontSize: 10, color: "var(--fg-3)", letterSpacing: 1 }}>SEMI 1</div>
      {slot("A1 · FALCONS")}{slot("B2 · BLAZERS")}
      <div style={{ height: 6 }}></div>
      <div style={{ fontFamily: "var(--f-mono)", fontSize: 10, color: "var(--fg-3)", letterSpacing: 1 }}>SEMI 2</div>
      {slot("B1 · VOLTS")}{slot("A2 · STORM")}
      <div style={{ height: 6 }}></div>
      <div style={{ fontFamily: "var(--f-mono)", fontSize: 10, color: "var(--hot)", letterSpacing: 1 }}>FINAL</div>
      {slot("TBD")}{slot("TBD")}
    </div>
  );
}

Object.assign(window, { Opt2Broadcast, BcastBracket });
