// =============================================================================
// COURTVIEW — Mock data shared across all option variants
// =============================================================================

const cvData = {
  tournament: {
    name: "2026 SEOUL METRO CUP",
    code: "SMC-26",
    venue: "OLYMPIC PARK · SEOUL",
    dates: "MAY 01 — MAY 12",
    format: "GROUP + KO",
    teams: 12,
    total: 28,
    done: 17,
    left: 11,
  },
  todayMatches: [
    { time: "14:00", home: "FALCONS", away: "TITANS", group: "A", status: "done", hs: 78, as: 64 },
    { time: "16:30", home: "VOLTS", away: "BLAZERS", group: "B", status: "live", hs: 41, as: 38, q: "Q3", clock: "07:24" },
    { time: "19:00", home: "STORM", away: "PHANTOMS", group: "A", status: "scheduled" },
    { time: "21:30", home: "RIDERS", away: "CRUSADERS", group: "B", status: "scheduled" },
  ],
  groups: {
    A: [
      { team: "FALCONS", gp: 4, w: 4, l: 0, pf: 312, pa: 248, diff: 64 },
      { team: "STORM",   gp: 3, w: 2, l: 1, pf: 234, pa: 219, diff: 15 },
      { team: "TITANS",  gp: 4, w: 1, l: 3, pf: 268, pa: 290, diff: -22 },
      { team: "PHANTOMS",gp: 3, w: 0, l: 3, pf: 198, pa: 255, diff: -57 },
    ],
    B: [
      { team: "VOLTS",     gp: 3, w: 3, l: 0, pf: 241, pa: 198, diff: 43 },
      { team: "BLAZERS",   gp: 4, w: 2, l: 2, pf: 288, pa: 282, diff: 6 },
      { team: "RIDERS",    gp: 3, w: 1, l: 2, pf: 209, pa: 220, diff: -11 },
      { team: "CRUSADERS", gp: 4, w: 1, l: 3, pf: 256, pa: 294, diff: -38 },
    ],
  },
  ticker: [
    { tag: "Q3 07:24", text: "VOLTS @ BLAZERS", val: "41-38", up: true },
    { tag: "FINAL", text: "FALCONS d. TITANS", val: "78-64" },
    { tag: "LEADER", text: "K. PARK 24P / 8R / 6A" },
    { tag: "ENGINE", text: "tracker.gpu0 · 60FPS · 12.4ms", val: "OK" },
    { tag: "REC", text: "8 cams streaming · 142 GB", val: "WRT" },
    { tag: "GROUP A", text: "FALCONS clinch top seed" },
    { tag: "NEXT", text: "STORM v PHANTOMS · 19:00" },
  ],
  cameras: [
    { id: 1, name: "BASELINE-N", status: "live", fps: 60, ms: 8 },
    { id: 2, name: "BASELINE-S", status: "live", fps: 60, ms: 9 },
    { id: 3, name: "SIDELINE-W", status: "live", fps: 60, ms: 11 },
    { id: 4, name: "SIDELINE-E", status: "live", fps: 60, ms: 10 },
    { id: 5, name: "OVERHEAD",   status: "live", fps: 30, ms: 14 },
    { id: 6, name: "TIGHT-HOOP-N", status: "stalled", fps: 0, ms: 0 },
    { id: 7, name: "TIGHT-HOOP-S", status: "live", fps: 60, ms: 9 },
    { id: 8, name: "BENCH-CAM",  status: "live", fps: 30, ms: 18 },
  ],
  events: [
    { t: "07:24", q: "Q3", icon: "score", team: "VOLTS", text: "K.PARK · 3PT MADE · ASSIST D.LEE", pts: "+3" },
    { t: "07:51", q: "Q3", icon: "foul",  team: "BLAZERS", text: "M.HAN · PERSONAL FOUL (P3)" },
    { t: "08:12", q: "Q3", icon: "score", team: "BLAZERS", text: "Y.KIM · LAYUP MADE", pts: "+2" },
    { t: "08:44", q: "Q3", icon: "sub",   team: "VOLTS", text: "SUB IN: J.OH · OUT: S.RYU" },
    { t: "09:02", q: "Q3", icon: "score", team: "VOLTS", text: "S.RYU · FT 2/2", pts: "+2" },
    { t: "09:30", q: "Q3", icon: "to",    team: "BLAZERS", text: "TIMEOUT 60s" },
    { t: "10:11", q: "Q3", icon: "score", team: "BLAZERS", text: "T.KO · MIDRANGE", pts: "+2" },
  ],
  leaders: [
    { player: "K. PARK", team: "VOLTS", num: "#11", pts: 24, reb: 8, ast: 6, eff: 31 },
    { player: "M. HAN", team: "BLAZERS", num: "#7", pts: 18, reb: 11, ast: 2, eff: 24 },
    { player: "S. RYU", team: "VOLTS", num: "#23", pts: 14, reb: 3, ast: 9, eff: 21 },
    { player: "T. KO", team: "BLAZERS", num: "#3", pts: 12, reb: 4, ast: 4, eff: 16 },
  ],
  systemHealth: {
    gpu: "RTX 4090",
    vram: "14.2 / 24 GB",
    fps: 60,
    latency: "12.4 ms",
    storage: "142 / 2000 GB",
    streams: "8 active",
  }
};

window.cvData = cvData;
