"""Rebuild sample_data/conversations.json from the readable transcript files in this folder.

Format:
=== <external_id> | YYYY-MM-DD HH:MM | Title        (local time, America/Phoenix)
Speaker: text
+ <seq> | action | counterparty | due_text | due | starts | ends | open|done   (optional pre-approved ledger entry)

Run:  python sample_data/source/build_sample.py   (from the backend folder)
"""
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
TZ = timezone(timedelta(hours=-7))  # America/Phoenix (no daylight saving)
USER = "Alex"


def ts(text):
    return None if text.strip() in ("", "-") else datetime.strptime(text.strip(), "%Y-%m-%d %H:%M").replace(tzinfo=TZ).isoformat()


def parse(path):
    convs, cur = [], None
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("==="):
            ext, when, title = [x.strip() for x in line[3:].split("|", 2)]
            start = datetime.strptime(when, "%Y-%m-%d %H:%M").replace(tzinfo=TZ)
            cur = {"external_id": ext, "title": title, "start": start, "lines": [], "seed": []}
            convs.append(cur)
        elif line.startswith("+"):
            seq, action, who, due_text, due, starts, ends, status = [x.strip() for x in line[1:].split("|")]
            cur["seed"].append({"utterance_sequence": int(seq), "action_text": action, "counterparty": who or None,
                                "due_text": due_text or None, "due_at": ts(due) or ts(ends), "starts_at": ts(starts),
                                "ends_at": ts(ends), "status": status})
        else:
            speaker, text = line.split(":", 1)
            cur["lines"].append((speaker.strip(), text.strip()))
    return convs


def build():
    out = []
    for path in sorted(HERE.glob("october_part*.txt")):
        for c in parse(path):
            t, utterances = c["start"], []
            for n, (speaker, text) in enumerate(c["lines"], 1):
                if n > 1:
                    t += timedelta(seconds=12 + (len(text) * 7 + n * 13) % 50)
                utterances.append({"sequence": n, "speaker": speaker, "occurred_at": t.isoformat(), "text": text})
            item = {"external_id": c["external_id"], "title": c["title"], "started_at": c["start"].isoformat(),
                    "ended_at": (t + timedelta(seconds=20)).isoformat(),
                    "participants": list(dict.fromkeys(s for s, _ in c["lines"])), "user_speaker": USER,
                    "utterances": utterances}
            if c["seed"]:
                item["seed_commitments"] = c["seed"]
            out.append(item)
    out.sort(key=lambda x: x["started_at"])
    payload = {"schema_version": "1.0", "source": "sample", "description":
               "Fictional October 2026 conversations for Recall & Commit. All people and events are invented.",
               "conversations": out}
    target = HERE.parent / "conversations.json"
    target.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    seeds = sum(len(c.get("seed_commitments", [])) for c in out)
    print(f"Wrote {target}: {len(out)} conversations, {sum(len(c['utterances']) for c in out)} utterances, "
          f"{seeds} pre-approved ledger entries")


if __name__ == "__main__":
    build()
