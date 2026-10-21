def conv(external_id, lines, started="2026-10-14T14:20:00-07:00", title="Test conversation", user="Alex"):
    return {"external_id": external_id, "title": title, "started_at": started,
            "participants": sorted({s for s, _ in lines}), "user_speaker": user,
            "utterances": [{"sequence": i, "speaker": s, "text": t} for i, (s, t) in enumerate(lines, 1)]}


def payload(*conversations):
    return {"schema_version": "1.0", "source": "test", "conversations": list(conversations)}
