// =============================================================================
// COURTVIEW — SEASON TIMELINE (C10)
// Tournament progression as a horizontal week-by-week timeline.
// =============================================================================

function CvTimelineScreen() {
  // Tournament weeks — Day 1..7, each with games
  const weeks = [
    {
      day: 1, date: "05 · 01", label: "OPENING",
      games: [
        { time: "13:00", grp: "A", h: "FALCONS", a: "PHANTOMS", hs: 78, as: 64, st: "DONE" },
        { time: "16:00", grp: "B", h: "VOLTS",   a: "RIDERS",   hs: 89, as: 66, st: "DONE" },
        { time: "19:00", grp: "C", h: "STORM",   a: "CRUSADERS",hs: 71, as: 73, st: "DONE", upset: true },
      ],
    },
    {
      day: 2, date: "05 · 02", label: "GROUP",
      games: [
        { time: "13:00", grp: "A", h: "TITANS",  a: "PHANTOMS", hs: 82, as: 79, st: "DONE" },
        { time: "16:00", grp: "B", h: "BLAZERS", a: "RIDERS",   hs: 90, as: 81, st: "DONE" },
        { time: "19:00", grp: "C", h: "STORM",   a: "FALCONS",  hs: 71, as: 84, st: "DONE" },
      ],
    },
    {
      day: 3, date: "05 · 03", label: "GROUP",
      games: [
        { time: "13:00", grp: "A", h: "FALCONS", a: "TITANS",   hs: 78, as: 64, st: "DONE", marquee: true },
        { time: "16:00", grp: "B", h: "VOLTS",   a: "BLAZERS",  hs: 95, as: 67, st: "DONE" },
        { time: "19:00", grp: "C", h: "PHANTOMS",a: "CRUSADERS",hs: 73, as: 73, st: "DONE", overtime: true },
      ],
    },
    {
      day: 4, date: "05 · 04", label: "REST",
      games: [],
    },
    {
      day: 5, date: "05 · 05", label: "QUARTERS",
      games: [
        { time: "16:00", grp: "QF", h: "FALCONS", a: "TITANS",   hs: 78, as: 64, st: "DONE", playoff: true },
        { time: "19:00", grp: "QF", h: "VOLTS",   a: "BLAZERS",  hs: 95, as: 67, st: "DONE", playoff: true },
        { time: "21:00", grp: "QF", h: "BLAZERS", a: "CRUSADERS",hs: 88, as: 85, st: "DONE", playoff: true },
      ],
    },
    {
      day: 6, date: "05 · 06", label: "REST",
      games: [],
    },
    {
      day: 7, date: "05 · 07", label: "SEMIS · TODAY",
      isToday: true,
      games: [
        { time: "13:00", grp: "SF", h: "FALCONS", a: "TITANS",   hs: 78, as: 64, st: "DONE", playoff: true },
        { time: "16:00", grp: "SF", h: "VOLTS",   a: "BLAZERS",  hs: 41, as: 38, st: "Q3 LIVE", live: true, playoff: true },
        { time: "19:00", grp: "SF", h: "STORM",   a: "RIDERS",   hs: null, as: null, st: "SCHED", playoff: true, sched: true },
      ],
    },
    {
      day: 8, date: "05 · 08", label: "FINAL",
      future: true,
      games: [
        { time: "19:00", grp: "F", h: "TBD", a: "TBD", hs: null, as: null, st: "FINAL", playoff: true, sched: true, marquee: true },
      ],
    },
  ];

  // Aggregate stats for the strip
  const totalGames = weeks.reduce((n, w) => n + w.games.filter(g => g.st === "DONE").length, 0);
  const liveCount  = weeks.reduce((n, w) => n + w.games.filter(g => g.live).length, 0);
  const upsetCount = weeks.reduce((n, w) => n + w.games.filter(g => g.upset).length, 0);
  const otCount    = weeks.reduce((n, w) => n + w.games.filter(g => g.overtime).length, 0);

  const [filter, setFilter] = React.useState("ALL"); // ALL · GROUP · KO · MARQUEE

  return (
    <div style={{ background: "var(--bg-1)", color: "var(--fg-0)", height: "100%", display: "flex", flexDirection: "column", overflow: "hidden" }}>
      <TopNav active="result" />
      <div style={{ flex: 1, overflow: "auto" }}>
        <EdHero
          issue="TML · 007"
          kicker="EVERY DAY OF THE TOURNAMENT, ONE LONG SCROLL"
          title={{ primary: "THE", accent: "WEEK." }}
          subline={[
            { k: "DAYS", v: "8" },
            { k: "GAMES PLAYED", v: totalGames },
            { k: "LIVE NOW", v: liveCount, c: "var(--bad)" },
          ]}
          right={<button className="cv-btn">↓ EXPORT TIMELINE</button>}
        />

        <EdStatStrip items={[
          { k: "DAYS COMPLETE", v: 6, sub: "of 8" },
          { k: "GAMES PLAYED", v: totalGames },
          { k: "OVERTIMES", v: otCount, c: otCount ? "var(--cool)" : "var(--fg-1)" },
          { k: "UPSETS", v: upsetCount, c: upsetCount ? "var(--hot)" : "var(--fg-1)" },
          { k: "LIVE", v: liveCount, c: liveCount ? "var(--bad)" : "var(--fg-1)" },
        ]} />

        {/* Filter */}
        <div style={{ padding: "14px 48px", borderBottom: "1px solid var(--line-2)", display: "flex", gap: 12, alignItems: "center" }}>
          <span style={{ fontFamily: "var(--f-mono)", fontSize: 10, color: "var(--fg-2)", letterSpacing: 1.5 }}>VIEW —</span>
          {[
            ["ALL", "전체"],
            ["GROUP", "조별"],
            ["KO", "토너먼트"],
            ["MARQUEE", "주요경기"],
          ].map(([k, ko]) => (
            <button key={k} onClick={() => setFilter(k)}
              className={`cv-btn ${filter === k ? "primary" : "ghost"}`}
              style={{ height: 28, fontSize: 10, padding: "0 12px" }}>
              {k} <span style={{ color: filter === k ? "var(--bg-1)" : "var(--fg-3)", marginLeft: 6, fontSize: 9 }}>{ko}</span>
            </button>
          ))}
          <span style={{ flex: 1 }}></span>
          <span style={{ fontFamily: "var(--f-mono)", fontSize: 10, color: "var(--fg-3)", letterSpacing: 1 }}>SCROLL HORIZONTALLY →</span>
        </div>

        {/* Timeline rail */}
        <div style={{ padding: "32px 0 8px", borderBottom: "1px solid var(--line-2)", overflowX: "auto", overflowY: "hidden" }}>
          {/* Continuous date axis */}
          <div style={{ position: "relative", paddingLeft: 48, paddingRight: 48, minWidth: weeks.length * 280 }}>
            {/* Spine line */}
            <div style={{ position: "absolute", top: 30, left: 48, right: 48, height: 2, background: "var(--line-2)" }}></div>

            {/* Day markers */}
            <div style={{ display: "grid", gridTemplateColumns: `repeat(${weeks.length}, 1fr)`, gap: 0, position: "relative" }}>
              {weeks.map((w, i) => {
                const filteredGames = w.games.filter(g => {
                  if (filter === "ALL") return true;
                  if (filter === "GROUP") return !g.playoff;
                  if (filter === "KO") return g.playoff;
                  if (filter === "MARQUEE") return g.marquee || g.upset || g.overtime;
                  return true;
                });

                return (
                  <div key={i} style={{ padding: "0 14px", borderRight: i < weeks.length - 1 ? "1px dashed var(--line-1)" : "none", position: "relative" }}>
                    {/* Day chip on spine */}
                    <div style={{ position: "relative", height: 60, display: "flex", flexDirection: "column", alignItems: "center" }}>
                      <div style={{
                        width: 20, height: 20, borderRadius: "50%",
                        background: w.isToday ? "var(--hot)" : w.future ? "var(--bg-2)" : "var(--bg-2)",
                        border: w.isToday ? "2px solid var(--hot)" : w.future ? "2px dashed var(--line-3)" : `2px solid ${w.games.some(g => g.live) ? "var(--bad)" : "var(--line-3)"}`,
                        display: "flex", alignItems: "center", justifyContent: "center",
                        fontFamily: "var(--f-mono)", fontSize: 10, fontWeight: 700, color: w.isToday ? "var(--bg-1)" : "var(--fg-1)",
                        position: "relative", zIndex: 2,
                      }}>{w.day}</div>
                      <div style={{ fontFamily: "var(--f-mono)", fontSize: 10, color: w.isToday ? "var(--hot)" : "var(--fg-2)", letterSpacing: 1, marginTop: 8, fontWeight: w.isToday ? 700 : 500 }}>{w.date}</div>
                      <div style={{ fontFamily: "var(--f-mono)", fontSize: 9, color: w.isToday ? "var(--hot)" : "var(--fg-3)", letterSpacing: 1.2, marginTop: 2 }}>
                        {w.isToday ? "● TODAY" : w.label}
                      </div>
                    </div>

                    {/* Games stacked */}
                    <div style={{ marginTop: 16, display: "flex", flexDirection: "column", gap: 8, minHeight: 200 }}>
                      {filteredGames.length === 0 && w.games.length > 0 && (
                        <div style={{ padding: "20px 0", textAlign: "center", fontFamily: "var(--f-mono)", fontSize: 9, color: "var(--fg-3)", letterSpacing: 1, border: "1px dashed var(--line-1)" }}>
                          FILTERED
                        </div>
                      )}
                      {filteredGames.length === 0 && w.games.length === 0 && (
                        <div style={{ padding: "20px 0", textAlign: "center", fontFamily: "var(--f-mono)", fontSize: 9, color: "var(--fg-3)", letterSpacing: 1 }}>
                          REST DAY
                        </div>
                      )}
                      {filteredGames.map((g, j) => (
                        <TimelineGameChip key={j} g={g} />
                      ))}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>

        {/* Story callouts */}
        <EdPanel kicker="STORYLINES" title="이번 토너먼트의 결정적 순간들" padding="28px 48px">
          <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 24 }}>
            {[
              { d: "DAY 1", c: "var(--hot)", t: "STORM 71 · CRUSADERS 73", b: "Cinderella opener — Crusaders shock seeded Storm in final minute of the tournament's first night." },
              { d: "DAY 3", c: "var(--cool)", t: "PHANTOMS 73 · CRUSADERS 73 (OT)", b: "First overtime of the bracket — the only tied result through 90 minutes of regulation play." },
              { d: "DAY 7 — TODAY", c: "var(--bad)", t: "VOLTS 41 · BLAZERS 38 (Q3)", b: "Semifinal currently live · Park sitting on 24 PTS · winner advances to Friday's final." },
            ].map((s, i) => (
              <div key={i} style={{ borderTop: `2px solid ${s.c}`, paddingTop: 14 }}>
                <div style={{ fontFamily: "var(--f-mono)", fontSize: 10, color: s.c, letterSpacing: 1.5, fontWeight: 700 }}>{s.d}</div>
                <div style={{ fontFamily: "var(--f-display)", fontSize: 22, fontWeight: 700, color: "var(--fg-0)", letterSpacing: -0.5, lineHeight: 1.1, marginTop: 8 }}>{s.t}</div>
                <div style={{ fontFamily: "var(--f-mono)", fontSize: 11, color: "var(--fg-2)", marginTop: 10, lineHeight: 1.5 }}>{s.b}</div>
              </div>
            ))}
          </div>
        </EdPanel>

        {/* Legend */}
        <div style={{ padding: "20px 48px 32px", borderTop: "1px solid var(--line-2)", display: "flex", gap: 28, flexWrap: "wrap" }}>
          <span style={{ fontFamily: "var(--f-mono)", fontSize: 10, color: "var(--fg-3)", letterSpacing: 1.5 }}>LEGEND —</span>
          <LegendKey c="var(--good)" label="DONE" />
          <LegendKey c="var(--bad)" label="LIVE" pulse />
          <LegendKey c="var(--cool)" label="SCHEDULED" dashed />
          <LegendKey c="var(--hot)" label="UPSET / MARQUEE" />
          <LegendKey c="var(--fg-2)" label="OVERTIME" symbol="OT" />
          <LegendKey c="var(--cool)" label="PLAYOFF" symbol="◆" />
        </div>
      </div>
    </div>
  );
}

function TimelineGameChip({ g }) {
  const winner = g.hs != null && g.as != null ? (g.hs > g.as ? "h" : g.as > g.hs ? "a" : null) : null;
  const isLive = !!g.live;
  const isSched = !!g.sched;
  const accent = isLive ? "var(--bad)" : g.upset ? "var(--hot)" : g.marquee ? "var(--hot)" : g.playoff ? "var(--cool)" : "var(--line-3)";
  return (
    <a href="#analysis" style={{
      display: "block", padding: "10px 12px",
      background: isLive ? "var(--bg-2)" : "var(--bg-1)",
      border: `1px solid ${accent}`,
      borderLeft: `3px solid ${accent}`,
      textDecoration: "none", color: "inherit",
      position: "relative",
    }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6 }}>
        <span style={{ fontFamily: "var(--f-mono)", fontSize: 9, color: "var(--fg-3)", letterSpacing: 1, fontWeight: 600 }}>
          {g.time} · {g.grp}
        </span>
        {isLive && <span style={{ fontFamily: "var(--f-mono)", fontSize: 8, color: "var(--bad)", letterSpacing: 1, fontWeight: 700 }}>● {g.st}</span>}
        {g.upset && !isLive && <span style={{ fontFamily: "var(--f-mono)", fontSize: 8, color: "var(--hot)", letterSpacing: 1, fontWeight: 700 }}>UPSET</span>}
        {g.overtime && !isLive && <span style={{ fontFamily: "var(--f-mono)", fontSize: 8, color: "var(--cool)", letterSpacing: 1, fontWeight: 700 }}>OT</span>}
        {g.marquee && !g.upset && !isLive && <span style={{ fontFamily: "var(--f-mono)", fontSize: 8, color: "var(--hot)", letterSpacing: 1, fontWeight: 700 }}>★</span>}
      </div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: 2 }}>
        <span style={{ fontFamily: "var(--f-display)", fontSize: 13, fontWeight: 700, color: winner === "h" ? "var(--fg-0)" : "var(--fg-2)", letterSpacing: -0.2 }}>{g.h}</span>
        <span style={{ fontFamily: "var(--f-display)", fontSize: 14, fontWeight: 700, color: winner === "h" ? "var(--hot)" : isLive ? "var(--bad)" : "var(--fg-2)", fontVariantNumeric: "tabular-nums" }}>
          {g.hs != null ? g.hs : "—"}
        </span>
      </div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
        <span style={{ fontFamily: "var(--f-display)", fontSize: 13, fontWeight: 700, color: winner === "a" ? "var(--fg-0)" : "var(--fg-2)", letterSpacing: -0.2 }}>{g.a}</span>
        <span style={{ fontFamily: "var(--f-display)", fontSize: 14, fontWeight: 700, color: winner === "a" ? "var(--hot)" : isLive ? "var(--bad)" : "var(--fg-2)", fontVariantNumeric: "tabular-nums" }}>
          {g.as != null ? g.as : "—"}
        </span>
      </div>
    </a>
  );
}

function LegendKey({ c, label, pulse, dashed, symbol }) {
  return (
    <span style={{ display: "flex", alignItems: "center", gap: 6, fontFamily: "var(--f-mono)", fontSize: 10, color: "var(--fg-2)", letterSpacing: 0.8 }}>
      {symbol ? (
        <span style={{ width: 14, fontFamily: "var(--f-mono)", fontSize: 10, color: c, fontWeight: 700, textAlign: "center" }}>{symbol}</span>
      ) : (
        <span style={{
          width: 10, height: 10,
          background: dashed ? "transparent" : c,
          border: dashed ? `1px dashed ${c}` : "none",
          animation: pulse ? "cv-pulse 1.4s ease-in-out infinite" : "none",
        }}></span>
      )}
      {label}
    </span>
  );
}

window.CvTimelineScreen = CvTimelineScreen;
