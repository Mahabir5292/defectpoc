import hashlib
import json
import re

import pandas as pd


ALIASES = {
    "ticket_id": [
        "ticket_id",
        "key",
        "issue key",
        "issue_key",
        "def_id",
        "defect id",
        "incident id",
        "number",
        "id",
    ],
    "summary": [
        "summary",
        "short description",
        "title",
        "defect summary",
    ],
    "description": [
        "description",
        "issue description",
        "details",
    ],
    "root_cause": [
        "root cause",
        "root_cause",
        "rca",
        "custom field root cause",
        "custom field (root cause)",
    ],
    "resolution": [
        "resolution",
        "fix",
        "solution",
        "workaround",
    ],
    "comments": [
        "comments",
        "comment",
        "work notes",
        "work_notes",
    ],
    "application": [
        "application",
        "application name",
        "business service",
        "service",
        "custom field application",
        "custom field (application)",
    ],
    "component": [
        "component",
        "module",
        "affected module",
    ],
    "priority": ["priority"],
    "severity": ["severity"],
    "status": ["status", "state"],
    "environment": ["environment", "env"],
    "country": ["country"],
    "market": ["market"],
    "resolver_group": [
        "resolver group",
        "assignment group",
        "support group",
        "custom field resolved by team",
        "custom field (resolved by team)",
    ],
    "assignee": ["assignee", "assigned to"],
    "reporter": ["reporter", "opened by"],
    "created_at": ["created", "created date", "created_at"],
    "updated_at": ["updated", "updated date", "updated_at"],
    "closed_at": [
        "closed",
        "closed date",
        "resolved date",
        "closed_at",
    ],
    "cause_category": [
        "cause",
        "cause category",
        "custom field cause",
        "custom field (cause)",
    ],
    "expected_result": [
        "expected result",
        "custom field expected result",
        "custom field (expected result)",
    ],
    "test_data": [
        "test data",
        "custom field test data",
        "custom field (test data)",
    ],
}


def key(value):
    return re.sub(
        r"[^a-z0-9]+",
        " ",
        str(value).strip().lower(),
    ).strip()


def clean_text(value):
    if value is None:
        return None

    text = str(value)
    text = text.replace("\xa0", " ")
    text = text.replace("\r\n", "\n")
    text = text.replace("\r", "\n")

    # Remove Jira formatting markers while retaining content.
    text = re.sub(r"\{[^{}]+\}", " ", text)
    text = re.sub(r"\[([^|\]]+)\|[^\]]+\]", r"\1", text)
    text = re.sub(r"https?://\S+", " ", text)

    # Mask long numeric test/customer identifiers.
    text = re.sub(r"\b\d{10,}\b", "[LONG_ID]", text)

    # Reduce whitespace.
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)

    text = text.strip()
    return text or None


def first(row, names):
    normalized = {key(k): v for k, v in row.items()}

    for name in names:
        value = normalized.get(key(name))

        if value is None:
            continue

        value_text = str(value).strip()

        if value_text and value_text.lower() != "nan":
            return value

    return None


def extract_rca_sections(value):
    result = {
        "root_cause": None,
        "resolution": None,
        "prevention": None,
    }

    text = clean_text(value)

    if not text:
        return result

    patterns = {
        "resolution": r"(?is)\bresolution\s*:\s*(.*?)(?=\n\s*[*-]?\s*root cause\s*:|\n\s*[*-]?\s*prevention\s*:|$)",
        "root_cause": r"(?is)\broot cause\s*:\s*(.*?)(?=\n\s*[*-]?\s*resolution\s*:|\n\s*[*-]?\s*prevention\s*:|$)",
        "prevention": r"(?is)\bprevention\s*:\s*(.*?)(?=\n\s*[*-]?\s*resolution\s*:|\n\s*[*-]?\s*root cause\s*:|$)",
    }

    for field, pattern in patterns.items():
        match = re.search(pattern, text)

        if match:
            result[field] = clean_text(match.group(1))

    # Some rows may not use the labelled template.
    if not result["root_cause"]:
        result["root_cause"] = text

    return result


def normalize_priority(value):
    text = clean_text(value)

    if not text:
        return None

    match = re.search(r"\bP[1-4]\b", text, re.IGNORECASE)
    return match.group(0).upper() if match else text


def normalize(row, ticket_type, source_file, source_row):
    out = {
        field: first(row, names)
        for field, names in ALIASES.items()
    }

    if not out["ticket_id"]:
        raise ValueError(
            "No ticket ID found. Add a Jira key/ID column "
            "or extend ALIASES."
        )

    rca_sections = extract_rca_sections(out.get("root_cause"))

    out["root_cause"] = rca_sections["root_cause"]

    if not out.get("resolution"):
        out["resolution"] = rca_sections["resolution"]

    out["prevention"] = rca_sections["prevention"]

    out["ticket_id"] = str(out["ticket_id"]).strip()
    out["ticket_type"] = ticket_type
    out["source_file"] = source_file
    out["source_row"] = source_row
    out["priority"] = normalize_priority(out.get("priority"))

    text_fields = [
        "summary",
        "description",
        "root_cause",
        "resolution",
        "comments",
        "application",
        "component",
        "severity",
        "status",
        "environment",
        "country",
        "market",
        "resolver_group",
        "assignee",
        "reporter",
        "cause_category",
        "expected_result",
        "test_data",
        "prevention",
    ]

    for field in text_fields:
        out[field] = clean_text(out.get(field))

    for field in ("created_at", "updated_at", "closed_at"):
        parsed = pd.to_datetime(
            out.get(field),
            errors="coerce",
            utc=True,
        )

        out[field] = (
            None
            if pd.isna(parsed)
            else parsed.to_pydatetime()
        )

    raw = {
        str(k): None if pd.isna(v) else v
        for k, v in row.items()
    }

    out["raw_metadata"] = raw
    out["source_hash"] = hashlib.sha256(
        json.dumps(
            raw,
            sort_keys=True,
            default=str,
        ).encode()
    ).hexdigest()

    return out


def searchable_text(ticket):
    fields = [
        ("Ticket ID", ticket.get("ticket_id")),
        ("Ticket type", ticket.get("ticket_type")),
        ("Summary", ticket.get("summary")),
        ("Application", ticket.get("application")),
        ("Priority", ticket.get("priority")),
        ("Status", ticket.get("status")),
        ("Symptom and description", ticket.get("description")),
        ("Expected result", ticket.get("expected_result")),
        ("Root cause", ticket.get("root_cause")),
        ("Cause category", ticket.get("cause_category")),
        ("Resolution", ticket.get("resolution")),
        ("Prevention", ticket.get("prevention")),
        ("Resolved by team", ticket.get("resolver_group")),
    ]

    text = "\n".join(
        f"{label}: {value}"
        for label, value in fields
        if value and str(value).strip()
    )

    # Avoid allowing large descriptions to dominate embeddings.
    return text[:12000]
