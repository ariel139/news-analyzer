import { dayKey, dayLabel, fullDate, markerPct, relTime } from "./format";

const TZ = "Asia/Jerusalem";
const NOW = Date.parse("2026-10-10T18:00:00Z"); // 21:00 in Jerusalem (UTC+3)

describe("relTime", () => {
  const ago = (min: number) => new Date(NOW - min * 60_000).toISOString();
  it("says now, minutes, an hour, hours", () => {
    expect(relTime(ago(0), TZ, NOW)).toBe("עכשיו");
    expect(relTime(ago(5), TZ, NOW)).toBe("לפני 5 דק׳");
    expect(relTime(ago(60), TZ, NOW)).toBe("לפני שעה");
    expect(relTime(ago(190), TZ, NOW)).toBe("לפני 3 שעות");
  });
  it("falls back to a local date after a day", () => {
    expect(relTime("2026-10-08T09:30:00Z", TZ, NOW)).toBe("08.10 12:30");
  });
});

describe("local time", () => {
  it("formats in the site timezone, not the visitor's", () => {
    expect(fullDate("2026-10-10T18:04:00Z", TZ)).toBe("10.10.2026 21:04");
    expect(fullDate("2026-01-10T18:04:00Z", TZ)).toBe("10.01.2026 20:04"); // winter time, UTC+2
  });
  it("groups by the local day (a late-evening UTC time is already tomorrow in Israel)", () => {
    expect(dayKey("2026-10-10T22:30:00Z", TZ)).toBe("2026-10-11");
  });
  it("labels today, yesterday and older days", () => {
    expect(dayLabel("2026-10-10", TZ, NOW)).toBe("היום");
    expect(dayLabel("2026-10-09", TZ, NOW)).toBe("אתמול");
    expect(dayLabel("2026-10-08", TZ, NOW)).toBe("יום חמישי, 8.10");
  });
});

it("places scores on their scale", () => {
  expect(markerPct(-2, -2, 2)).toBe(0);
  expect(markerPct(0, -2, 2)).toBe(50);
  expect(markerPct(1, -2, 2)).toBe(75);
  expect(markerPct(3, 0, 4)).toBe(75);
});
