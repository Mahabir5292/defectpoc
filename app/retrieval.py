import re

from qdrant_client import QdrantClient, models

from .aws_clients import embed
from .config import settings
from .db import (
    aggregate,
    fetch_by_ids,
    lexical_search,
)
from .llm import generate


qdrant = QdrantClient(url=settings.qdrant_url)


STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "about",
    "defect",
    "defects",
    "find",
    "for",
    "from",
    "how",
    "incident",
    "incidents",
    "is",
    "of",
    "on",
    "related",
    "show",
    "similar",
    "the",
    "to",
    "what",
    "with",
}


def route(query):
    query_lower = query.lower()

    aggregate_terms = [
        "how many",
        "count",
        "most common",
        "top root cause",
        "breakdown",
        "distribution",
    ]

    return (
        "sql"
        if any(term in query_lower for term in aggregate_terms)
        else "hybrid"
    )


def parse_filters(query):
    filters = {}

    priority_match = re.search(
        r"\b(P[1-4])\b",
        query,
        re.IGNORECASE,
    )

    if priority_match:
        filters["priority"] = priority_match.group(1).upper()

    if re.search(r"\bdefects?\b", query, re.IGNORECASE):
        filters["ticket_type"] = "DEFECT"

    if re.search(r"\bincidents?\b", query, re.IGNORECASE):
        filters["ticket_type"] = "INCIDENT"

    status_terms = {
        "closed": "Closed",
        "open": "Open",
        "resolved": "Resolved",
    }

    for word, value in status_terms.items():
        if re.search(
            rf"\b{word}\b",
            query,
            re.IGNORECASE,
        ):
            filters["status"] = value

    return filters


def qfilter(filters):
    conditions = []

    for field, value in filters.items():
        conditions.append(
            models.FieldCondition(
                key=field,
                match=models.MatchValue(value=value),
            )
        )

    return models.Filter(must=conditions) if conditions else None


def vector_search(query, filters):
    response = qdrant.query_points(
        collection_name=settings.qdrant_collection,
        query=embed(query),
        query_filter=qfilter(filters),
        limit=settings.top_k,
        score_threshold=settings.min_score,
        with_payload=True,
    )

    return [
        {
            "ticket_id": hit.payload.get("ticket_id"),
            "vector_score": float(hit.score),
        }
        for hit in response.points
        if hit.payload.get("ticket_id")
    ]


def normalize_lexical_scores(rows):
    if not rows:
        return {}

    maximum = max(
        float(row.get("lexical_score") or 0)
        for row in rows
    )

    if maximum <= 0:
        return {
            row["ticket_id"]: 0.0
            for row in rows
        }

    return {
        row["ticket_id"]:
            float(row.get("lexical_score") or 0) / maximum
        for row in rows
    }


def rerank(vector_hits, lexical_hits):
    vector_map = {
        hit["ticket_id"]: hit["vector_score"]
        for hit in vector_hits
    }

    lexical_map = normalize_lexical_scores(lexical_hits)

    all_ids = set(vector_map) | set(lexical_map)
    ranked = []

    for ticket_id in all_ids:
        vector_score = vector_map.get(ticket_id, 0.0)
        lexical_score = lexical_map.get(ticket_id, 0.0)

        final_score = (
            settings.vector_weight * vector_score
            + settings.lexical_weight * lexical_score
        )

        ranked.append(
            {
                "ticket_id": ticket_id,
                "score": round(final_score, 4),
                "vector_score": round(vector_score, 4),
                "lexical_score": round(lexical_score, 4),
            }
        )

    ranked.sort(
        key=lambda item: item["score"],
        reverse=True,
    )

    return ranked[:settings.final_k]


def build_context(records, scores):
    score_map = {
        item["ticket_id"]: item
        for item in scores
    }

    blocks = []

    for record in records:
        extra = record.get("raw_metadata") or {}

        values = {
            "ticket_id": record.get("ticket_id"),
            "ticket_type": record.get("ticket_type"),
            "summary": record.get("summary"),
            "application": record.get("application"),
            "priority": record.get("priority"),
            "status": record.get("status"),
            "description": record.get("description"),
            "root_cause": record.get("root_cause"),
            "cause_category": extra.get(
                "Custom field (Cause)"
            ),
            "resolution": record.get("resolution"),
            "expected_result": extra.get(
                "Custom field (Expected Result)"
            ),
            "resolved_by_team": record.get(
                "resolver_group"
            ),
        }

        scores_for_ticket = score_map.get(
            record["ticket_id"],
            {},
        )

        values["retrieval_score"] = (
            scores_for_ticket.get("score")
        )

        block = "\n".join(
            f"{key}: {value}"
            for key, value in values.items()
            if value is not None and str(value).strip()
        )

        blocks.append(block)

    context = "\n\n---\n\n".join(blocks)
    return context[:settings.max_context_chars]


def retrieval_only(records, hits):
    if not records:
        return (
            "No matching evidence was found above "
            "the configured retrieval threshold."
        )

    lines = ["Retrieved evidence:"]

    hit_map = {
        hit["ticket_id"]: hit
        for hit in hits
    }

    for record in records:
        score = hit_map.get(
            record["ticket_id"],
            {},
        ).get("score")

        lines.append(
            f"- {record['ticket_id']} | "
            f"score {score} | "
            f"{record.get('summary') or 'No summary'} | "
            f"RCA: "
            f"{record.get('root_cause') or 'Not recorded'} | "
            f"Resolution: "
            f"{record.get('resolution') or 'Not recorded'}"
        )

    return "\n".join(lines)


def ask(query):
    filters = parse_filters(query)
    mode = route(query)

    if mode == "sql":
        rows = aggregate(filters)

        context = (
            "Structured database result:\n"
            f"{rows}"
        )

        sources = []
        records = []

    else:
        vector_hits = vector_search(query, filters)

        lexical_hits = lexical_search(
            query=query,
            filters=filters,
            limit=settings.top_k,
        )

        sources = rerank(
            vector_hits,
            lexical_hits,
        )

        records = fetch_by_ids(
            [
                item["ticket_id"]
                for item in sources
            ]
        )

        context = build_context(
            records,
            sources,
        )

    if settings.llm_provider.lower() == "none":
        answer = (
            str(rows)
            if mode == "sql"
            else retrieval_only(records, sources)
        )
    else:
        system_prompt = """
You are an enterprise Jira defect-triage assistant.

Mandatory rules:
1. Use only the supplied evidence.
2. Never invent ticket IDs, causes, resolutions, teams, counts,
   environments, or confidence levels.
3. Cite supporting Jira ticket IDs in every material finding.
4. Distinguish confirmed root cause from probable similarity.
5. If evidence is insufficient, state that clearly.
6. Do not expose customer IDs, test data, credentials, URLs,
   trace IDs, or other sensitive identifiers.
7. Recommendations must be framed as validation steps, not as
   confirmed fixes.
8. Prefer concise technical language.
""".strip()

        user_prompt = f"""
User query:
{query}

Retrieved Jira evidence:
{context}

Produce the response in this structure:

### Direct answer
Answer the question in two to five sentences.

### Supporting historical defects
List the most relevant ticket IDs and briefly explain why each
ticket supports the answer.

### Observed pattern
State the evidence-backed application, symptom, cause,
resolution, or team pattern.

### Recommended validation steps
Provide safe diagnostic steps based only on resolutions and
prevention notes present in the evidence.

### Limitations
State missing or uncertain information.
""".strip()

        answer = generate(
            system_prompt,
            user_prompt,
        )

    return {
        "mode": mode,
        "filters": filters,
        "llm_provider": settings.llm_provider,
        "answer": answer,
        "sources": sources,
    }
