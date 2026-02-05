import json
import os
from dataclasses import dataclass


DEFAULT_PATH = "moh_time_os/out/rules_overrides.json"


@dataclass
class RuleOverrides:
    # simple string-substring match lists
    archive_sender_substr: list[str]
    archive_subject_substr: list[str]
    delegate_krystie_substr: list[str]


def load_rules(path: str = DEFAULT_PATH) -> RuleOverrides:
    if not os.path.exists(path):
        return RuleOverrides([], [], [])
    try:
        data = json.loads(open(path, "r", encoding="utf-8").read())
    except Exception:
        data = {}
    return RuleOverrides(
        archive_sender_substr=list(dict.fromkeys(data.get("archive_sender_substr") or [])),
        archive_subject_substr=list(dict.fromkeys(data.get("archive_subject_substr") or [])),
        delegate_krystie_substr=list(dict.fromkeys(data.get("delegate_krystie_substr") or [])),
    )


def save_rules(r: RuleOverrides, path: str = DEFAULT_PATH) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    data = {
        "archive_sender_substr": list(dict.fromkeys(r.archive_sender_substr)),
        "archive_subject_substr": list(dict.fromkeys(r.archive_subject_substr)),
        "delegate_krystie_substr": list(dict.fromkeys(r.delegate_krystie_substr)),
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
