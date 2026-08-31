function toLocalInput(d) {
  const p = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}T${p(d.getHours())}:${p(d.getMinutes())}`;
}

export function createDefaultContext(saved = {}, fallbackParticipant = "", now = new Date()) {
  const end = new Date(now);
  const start = new Date(end.getTime() - 3600000);
  return {
    experiment: saved.experiment || "",
    participant: saved.participant || fallbackParticipant || "",
    start: saved.start || toLocalInput(start),
    end: saved.end || toLocalInput(end),
    channels: saved.channels || "eda, ppg",
  };
}

export function resolveConsoleContext(context, fallbackParticipant = "") {
  const experiment = String(context.experiment || "").trim();
  const participant = String(context.participant || fallbackParticipant || "").trim();
  const startDate = new Date(context.start || "");
  const endDate = new Date(context.end || "");
  const rows = String(context.channels || "")
    .split(",")
    .map((value) => value.trim())
    .filter(Boolean);

  if (!participant) return { error: "participant_id を入力してください" };
  if (Number.isNaN(startDate.getTime()) || Number.isNaN(endDate.getTime())) {
    return { error: "有効な開始・終了時刻を指定してください" };
  }
  if (startDate >= endDate) return { error: "開始時刻は終了時刻より前にしてください" };

  return {
    experiment,
    participant,
    start: startDate.toISOString(),
    end: endDate.toISOString(),
    rows,
    error: "",
  };
}
