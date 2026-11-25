export const when = (ts) => {
  if (!ts) return "-";
  const d = new Date(ts.replace(" ", "T") + (/[zZ]|[+-]\d\d:?\d\d$/.test(ts) ? "" : "Z"));
  return isNaN(d) ? ts : d.toLocaleString([], { dateStyle: "medium", timeStyle: "short" });
};
export const day = (ts) => (ts ? when(ts).split(",").slice(0, 2).join(",") : "-");
export const badgeClass = (s = "") =>
  /accepted|published|sent|logged/i.test(s) ? "b ok" : /declined|expired|closed|failed/i.test(s) ? "b bad" : /pending|review|wait|submitted|manual/i.test(s) ? "b warn" : "b";
