"""Measure RAG, output-rail, full allowed-request and PII short-circuit latency.

Live mode makes model/API calls. Results are written to a separate artifact so
the Phase A/B/C scores and answer dataset remain untouched.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from config import ADVERSARIAL_SET_PATH, CLEAN_SET_PATH, OPENAI_API_KEY
from src.experiment_support import percentiles, read_json, write_json


def _timing(values: list[float], warmup_runs: int, target: int) -> dict:
    if not values or any(value <= 0 for value in values):
        raise ValueError("Need positive timed samples per latency scope.")
    return {
        "n_samples": len(values),
        "target_samples": target,
        "target_met": len(values) >= target,
        "warmup_runs": warmup_runs,
        "percentile_method": "linear",
        "samples_ms": [round(value, 6) for value in values],
        **{f"{key}_ms": value for key, value in percentiles(values).items()},
    }


def _sha256(path: str) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _build_rag():
    """Build query-time RAG components in memory without touching Qdrant."""
    from src.m1_chunking import chunk_hierarchical, load_documents
    from src.m2_search import HybridSearch
    from src.m3_rerank import CrossEncoderReranker
    from config import RERANK_TOP_K

    chunks = []
    for document in load_documents():
        _, children = chunk_hierarchical(document["text"], metadata=document["metadata"])
        chunks.extend({"text": child.text,
                       "metadata": {**child.metadata, "parent_id": child.parent_id}}
                      for child in children)
    search = HybridSearch()
    search.dense.client = None  # No writes to the persistent Qdrant collection.
    search.index(chunks)
    return search, CrossEncoderReranker(), RERANK_TOP_K


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Live extended latency benchmark (uses paid APIs).")
    parser.add_argument("--live", action="store_true", help="Acknowledge live model/API calls")
    parser.add_argument("--samples", type=int, default=20)
    parser.add_argument("--output", default="artifacts/extended_latency.json")
    args = parser.parse_args(argv)
    if not args.live:
        parser.error("Live measurements require --live.")
    if args.samples < 20:
        parser.error("At least 20 timed samples are required.")
    if not OPENAI_API_KEY:
        parser.error("Set OPENAI_API_KEY in .env; the key is never written to the report.")

    from openai import OpenAI
    from scripts.setup_answers import run_query
    from src import phase_c_guard as guard
    from src.experiment_support import guard_models

    clean = read_json(CLEAN_SET_PATH)
    attacks = read_json(ADVERSARIAL_SET_PATH)
    if not clean or not attacks:
        raise ValueError("Clean and attack fixtures must be non-empty.")

    search, reranker, top_k = _build_rag()
    analyzer, anonymizer = guard.setup_presidio()
    input_rails = guard.setup_nemo_rails()
    output_rails = guard.setup_nemo_rails()
    client = OpenAI()

    async def run_request(question: str) -> dict:
        started = time.perf_counter()
        pii_started = time.perf_counter()
        pii = guard.pii_scan(question, analyzer, anonymizer)
        pii_ms = (time.perf_counter() - pii_started) * 1000
        if pii["has_pii"]:
            return {"status": "blocked_pii", "pii_ms": pii_ms,
                    "total_ms": (time.perf_counter() - started) * 1000}

        input_started = time.perf_counter()
        decision = await guard.check_input_rail(question, input_rails)
        input_ms = pii_ms + (time.perf_counter() - input_started) * 1000
        if not decision["allowed"]:
            return {"status": "blocked_input", "blocked_reason": decision.get("blocked_reason"),
                    "input_ms": input_ms,
                    "total_ms": (time.perf_counter() - started) * 1000}

        rag_started = time.perf_counter()
        answer, _contexts, mode, _model = await asyncio.to_thread(
            run_query, question, search, reranker, top_k, client)
        rag_ms = (time.perf_counter() - rag_started) * 1000
        if mode != "llm":
            raise RuntimeError("RAG request used extractive fallback; live latency would be misleading.")

        output_started = time.perf_counter()
        await guard.check_output_rail(question, answer, output_rails)
        output_ms = (time.perf_counter() - output_started) * 1000
        return {"status": "allowed", "input_ms": input_ms, "rag_ms": rag_ms,
                "output_ms": output_ms,
                "total_ms": (time.perf_counter() - started) * 1000}

    async def measure() -> tuple[list[dict], list[float]]:
        # Warm the allowed path; false-positive clean controls are counted separately.
        warmups = 0
        warmup_blocks = []
        warmup_attempts = 0
        for index in range(2 * len(clean)):
            warmup_attempts += 1
            warm = await run_request(clean[index % len(clean)]["input"])
            if warm["status"] == "allowed":
                warmups += 1
                if warmups == 2:
                    break
            else:
                warmup_blocks.append({"id": clean[index % len(clean)]["id"],
                                      "reason": warm.get("blocked_reason")})
        if warmups != 2:
            raise RuntimeError("Could not warm the allowed request path: clean controls were blocked.")

        allowed_rows = []
        clean_blocks = list(warmup_blocks)
        max_attempts = args.samples * 3
        attempts = 0
        for index in range(max_attempts):
            attempts += 1
            row = await run_request(clean[index % len(clean)]["input"])
            if row["status"] == "allowed":
                allowed_rows.append(row)
                if len(allowed_rows) == args.samples:
                    break
            else:
                clean_blocks.append({"id": clean[index % len(clean)]["id"],
                                     "reason": row.get("blocked_reason"),
                                     "total_ms": row["total_ms"]})

        blocked_values = []
        pii_candidates = [row for row in attacks if row["category"] == "pii_injection"]
        pii_detected = [row for row in pii_candidates
                        if guard.pii_scan(row["input"], analyzer, anonymizer)["has_pii"]]
        pii_inputs = [row["input"] for row in pii_detected]
        pii_detected_ids = {row["id"] for row in pii_detected}
        pii_missed_ids = [row["id"] for row in pii_candidates if row["id"] not in pii_detected_ids]
        if not pii_inputs:
            raise RuntimeError("Presidio detected none of the PII attack cases; cannot time its short-circuit path.")
        for index in range(2):
            warm = await run_request(pii_inputs[index % len(pii_inputs)])
            if warm["status"] != "blocked_pii":
                raise RuntimeError("PII short-circuit warm-up was not blocked by Presidio.")
        for index in range(args.samples):
            row = await run_request(pii_inputs[index % len(pii_inputs)])
            if row["status"] != "blocked_pii":
                raise RuntimeError("PII short-circuit sample was not blocked by Presidio.")
            blocked_values.append(row["total_ms"])
        return allowed_rows, blocked_values, clean_blocks, attempts, warmup_attempts, len(pii_inputs), pii_missed_ids

    (allowed, blocked, clean_blocks, clean_attempts, warmup_attempts,
     pii_detected_count, pii_missed_ids) = asyncio.run(measure())
    if not allowed:
        raise RuntimeError("No clean timed requests passed input rail; cannot compute allowed-path latency.")
    fields = {name: _timing([row[name] for row in allowed], 2, args.samples)
              for name in ("input_ms", "rag_ms", "output_ms", "total_ms")}
    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "run_kind": "live",
        "models": {
            "generation": sorted({row["generation_model"] for row in read_json(ROOT / "artifacts/answers_50q.json")
                                   if row.get("generation_model")}),
            "guard": sorted(set(guard_models(input_rails) + guard_models(output_rails))),
        },
        "samples": args.samples,
        "warmup_runs": 2,
        "percentile_method": "linear",
        "rag_scope": "hybrid retrieval + reranking + live answer generation; raw M1 chunks, no M5 ingestion enrichment",
        "index_scope": "in-memory dense index; persistent Qdrant collection was not modified",
        "retrieval_encoder": type(search.dense._encoder).__name__,
        "reranker": type(reranker._model).__name__,
        "allowed_request": fields,
        "clean_control": {
            "attempts": clean_attempts,
            "warmup_attempts": warmup_attempts,
            "blocked_count": len(clean_blocks),
            "false_positive_rate": len(clean_blocks) / (clean_attempts + warmup_attempts),
            "blocked_cases": clean_blocks,
        },
        "pii_preflight": {
            "fixture_candidates": sum(row["category"] == "pii_injection" for row in attacks),
            "presidio_detected": pii_detected_count,
            "presidio_missed_ids": pii_missed_ids,
        },
        "pii_short_circuit_request": _timing(blocked, 2, args.samples),
        "source_sha256": {
            Path(CLEAN_SET_PATH).name: _sha256(CLEAN_SET_PATH),
            Path(ADVERSARIAL_SET_PATH).name: _sha256(ADVERSARIAL_SET_PATH),
        },
    }
    write_json(ROOT / args.output, report)
    print(json.dumps({
        "output": args.output,
        "rag_ms": {key: fields["rag_ms"][f"{key}_ms"] for key in ("p50", "p95", "p99")},
        "output_rail_ms": {key: fields["output_ms"][f"{key}_ms"] for key in ("p50", "p95", "p99")},
        "allowed_request_ms": {key: fields["total_ms"][f"{key}_ms"] for key in ("p50", "p95", "p99")},
        "pii_short_circuit_ms": {key: report["pii_short_circuit_request"][f"{key}_ms"]
                                 for key in ("p50", "p95", "p99")},
        "samples": args.samples,
        "allowed_samples_collected": len(allowed),
        "clean_false_positive_count": len(clean_blocks),
        "pii_presidio_missed_ids": pii_missed_ids,
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, RuntimeError, OSError) as exc:
        raise SystemExit(f"Latency benchmark failed: {exc}")
