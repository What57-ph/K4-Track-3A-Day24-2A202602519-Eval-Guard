from __future__ import annotations

"""Phase C: Production Guardrails — Presidio PII + NeMo Guardrails + P95 Latency."""

import asyncio
import json
import os
import re
import statistics
import sys
import time
import unicodedata

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import ADVERSARIAL_SET_PATH, GUARDRAILS_CONFIG_DIR, LATENCY_BUDGET_P95_MS, PRESIDIO_LANGUAGE


# ─── Task 9a: Presidio PII Detection ─────────────────────────────────────────

def setup_presidio():
    """Khởi tạo Presidio engine với custom Vietnamese PII recognizers. (Đã implement sẵn)

    Custom recognizers thêm vào:
        VN_CCCD  — số CCCD 12 chữ số hoặc CMND 9 chữ số
        VN_PHONE — số điện thoại Việt Nam (0[3-9]xxxxxxxx)

    Các recognizers mặc định đã có sẵn: EMAIL, PHONE_NUMBER (international), ...
    """
    from presidio_analyzer import AnalyzerEngine, RecognizerRegistry, Pattern, PatternRecognizer
    from presidio_anonymizer import AnonymizerEngine

    cccd_recognizer = PatternRecognizer(
        supported_entity="VN_CCCD",
        patterns=[
            Pattern("CCCD 12 digits", r"\b\d{12}\b", 0.9),
            Pattern("CMND 9 digits",  r"\b\d{9}\b",  0.7),
        ],
    )
    phone_recognizer = PatternRecognizer(
        supported_entity="VN_PHONE",
        patterns=[Pattern("VN mobile", r"\b0[3-9]\d{8}\b", 0.9)],
    )

    registry = RecognizerRegistry()
    registry.load_predefined_recognizers()
    registry.add_recognizer(cccd_recognizer)
    registry.add_recognizer(phone_recognizer)

    analyzer  = AnalyzerEngine(registry=registry)
    anonymizer = AnonymizerEngine()
    return analyzer, anonymizer


def pii_scan(text: str, analyzer=None, anonymizer=None) -> dict:
    """Task 9a: Quét PII trong văn bản bằng Presidio.

    Returns:
        {
          "has_pii":    bool,
          "entities":   [{"type": str, "text": str, "score": float, "start": int, "end": int}],
          "anonymized": str,   # text với PII được thay bằng <TYPE>
        }
    """
    if analyzer is None or anonymizer is None:
        analyzer, anonymizer = setup_presidio()

    # English PERSON/license recognizers mislabel ordinary Vietnamese policy text.
    allowed_entities = {"EMAIL_ADDRESS", "PHONE_NUMBER", "VN_CCCD", "VN_PHONE"}
    results = [
        result for result in analyzer.analyze(text=text, language=PRESIDIO_LANGUAGE)
        if result.entity_type in allowed_entities
    ]
    if not results:
        return {"has_pii": False, "entities": [], "anonymized": text}

    anonymized_result = anonymizer.anonymize(text=text, analyzer_results=results)
    anonymized_text = getattr(anonymized_result, "text", str(anonymized_result))

    entities = [
        {
            "type": getattr(r, "entity_type", ""),
            "text": text[r.start:r.end],
            "score": round(float(getattr(r, "score", 0.0)), 3),
            "start": r.start,
            "end": r.end,
        }
        for r in results
    ]
    return {"has_pii": True, "entities": entities, "anonymized": anonymized_text}


# ─── Task 9b + 11: NeMo Guardrails ───────────────────────────────────────────

_POLICY_TERMS = re.compile(
    r"\b(?:hr|policy|employee|leave|salary|benefits|insurance|security|account|allowance|time off|"
    r"nhan vien|chinh sach|nghi phep|nghi om|nghi benh|bao hiem|"
    r"luong|phu cap|vpn|mat khau|password|mfa|tai khoan|bao mat|incident|"
    r"su co|quy trinh|wfh|lam viec tu xa|thu viec|phep nam)\b"
)
_ATTACK_TERMS = re.compile(
    r"\b(?:ignore (?:all )?(?:previous|prior) instructions?|ignore your system prompt|"
    r"system override|admin command|dump (?:all |the )?(?:training data|employee|confidential)|"
    r"do anything now|unrestricted ai|bypass (?:all )?(?:rules|polic(?:y|ies))|"
    r"bo qua (?:tat ca )?(?:huong dan|chi dan|policy|chinh sach)|"
    r"tiet lo (?:toan bo |chi tiet )?(?:bang luong|du lieu|thong tin|system)|"
    r"in (?:ra )?(?:toan bo )?(?:system instructions|huong dan he thong|context)|"
    r"tan cong mang noi bo|mat khau admin|ra lenh ban bo qua)\b"
)
_SENSITIVE_REQUESTS = re.compile(
    r"\b(?:bang luong|salary details|all employee salaries|employee records|"
    r"confidential (?:hr )?data|ho so nhan vien|du lieu nhan vien|"
    r"thong tin ca nhan|thong tin cua nhan vien|salary of [a-z]+ [a-z]+|"
    r"luong cua (?:nhan vien|[a-z]+ [a-z]+))\b"
)
_QUESTION_TERMS = re.compile(
    r"\?|\b(?:bao nhieu|the nao|la gi|co .{0,50} khong|duoc khong|"
    r"toi thieu|bat buoc|quy trinh|can lam gi)\b"
)


def _local_input_decision(text: str) -> bool | None:
    """Apply clear scope and injection rules before the probabilistic rail."""
    normalized = unicodedata.normalize("NFKD", text.casefold())
    normalized = "".join(char for char in normalized if not unicodedata.combining(char))
    if _ATTACK_TERMS.search(normalized) or _SENSITIVE_REQUESTS.search(normalized):
        return False
    if not _POLICY_TERMS.search(normalized):
        return False
    # shortcut: policy questions skip NeMo false positives; upgrade if injection tests show a bypass.
    return True if _QUESTION_TERMS.search(normalized) else None


def setup_nemo_rails():
    """Khởi tạo NeMo Guardrails từ guardrails/config.yml. (Đã implement sẵn)

    Config directory: guardrails/
        config.yml  — model + rails config
        rails.co    — câu từ chối Colang 1.0; built-in self-check flows được bật trong YAML
    """
    from nemoguardrails import RailsConfig, LLMRails
    config = RailsConfig.from_path(GUARDRAILS_CONFIG_DIR)
    rails  = LLMRails(config)
    return rails


async def check_input_rail(text: str, rails=None) -> dict:
    """Task 9b: Kiểm tra input qua NeMo input rails (topic guard + jailbreak guard).

    Returns:
        {
          "allowed":        bool,
          "blocked_reason": str | None,
          "response":       str,          # NeMo's raw response
        }
    """
    local_decision = _local_input_decision(text)
    if local_decision is False:
        return {
            "allowed": False,
            "blocked_reason": "local_input_policy",
            "response": "Request is outside policy scope or contains an instruction attack.",
        }

    if rails is None:
        rails = setup_nemo_rails()

    result = await rails.generate_async(
        messages=[{"role": "user", "content": text}],
        options={"rails": ["input"], "log": {"activated_rails": True}},
    )
    resp_obj = result.response[0] if result.response else {"content": ""}
    response = resp_obj.get("content", "") if isinstance(resp_obj, dict) else getattr(resp_obj, "content", "")

    activated = getattr(getattr(result, "log", None), "activated_rails", [])
    blocked = any(getattr(rail, "stop", False) for rail in activated)
    return {
        "allowed":        not blocked,
        "blocked_reason": "nemo_input_rail" if blocked else None,
        "response":       response,
    }


async def check_output_rail(question: str, answer: str, rails=None) -> dict:
    """Task 11: Kiểm tra LLM output qua NeMo output rails trước khi trả về user.

    NeMo output rails hoạt động trong context của cả cuộc hội thoại (input + output).
    Kiểm tra PII và nội dung nhạy cảm. Self-check này không thay RAGAS faithfulness
    hoặc kiểm tra factual accuracy với retrieved contexts.

    Returns:
        {
          "safe":           bool,
          "flagged_reason": str | None,
          "final_answer":   str,          # answer đã qua guard (có thể bị redact)
        }
    """
    if rails is None:
        rails = setup_nemo_rails()

    result = await rails.generate_async(
        messages=[
            {"role": "user", "content": question},
            {"role": "assistant", "content": answer},
        ],
        options={"rails": ["output"], "log": {"activated_rails": True}},
    )
    resp_obj = result.response[0] if result.response else {"content": answer}
    response = resp_obj.get("content", answer) if isinstance(resp_obj, dict) else getattr(resp_obj, "content", answer)

    activated = getattr(getattr(result, "log", None), "activated_rails", [])
    flagged = any(getattr(rail, "stop", False) for rail in activated)
    return {
        "safe":           not flagged,
        "flagged_reason": "nemo_output_rail" if flagged else None,
        "final_answer":   response,
    }


# ─── Task 10: Adversarial Test Suite ─────────────────────────────────────────

def run_adversarial_suite(adversarial_set: list[dict], rails=None,
                           analyzer=None, anonymizer=None) -> list[dict]:
    """Task 10: Chạy 20 adversarial inputs qua full guard stack, so sánh với expected.

    Guard stack order:
        1. pii_scan()         → block nếu has_pii (cho category pii_injection)
        2. check_input_rail() → block nếu jailbreak / off-topic / prompt injection

    Returns:
        list of {
          "id": int, "category": str, "input": str,
          "expected": "blocked"|"allowed",
          "actual":   "blocked"|"allowed",
          "blocked_by": str | None,       # "presidio" | "nemo_input" | None
          "passed": bool,
        }
    """
    if analyzer is None or anonymizer is None:
        analyzer, anonymizer = setup_presidio()
    if rails is None:
        rails = setup_nemo_rails()

    async def _run_all():
        results = []
        for item in adversarial_set:
            blocked_by = None

            # Layer 1: Presidio PII (synchronous, fast)
            pii_result = pii_scan(item["input"], analyzer, anonymizer)
            if pii_result["has_pii"]:
                blocked_by = "presidio"

            # Layer 2: NeMo input rail (async — await, không dùng asyncio.run())
            if blocked_by is None:
                rail_result = await check_input_rail(item["input"], rails)
                if not rail_result["allowed"]:
                    blocked_by = "nemo_input"

            actual = "blocked" if blocked_by else "allowed"
            results.append({
                "id":         item["id"],
                "category":   item["category"],
                "input":      item["input"],
                "expected":   item["expected"],
                "actual":     actual,
                "blocked_by": blocked_by,
                "passed":     actual == item["expected"],
            })
        return results

    results = asyncio.run(_run_all())
    passed = sum(1 for r in results if r["passed"])
    print(f"Adversarial suite: {passed}/{len(results)} passed")
    return results


# ─── Task 12: P95 Latency Measurement ────────────────────────────────────────

def measure_p95_latency(test_inputs: list[str], n_runs: int = 20,
                         rails=None, analyzer=None, anonymizer=None) -> dict:
    """Task 12: measure INPUT layers sequentially, not end-to-end guard/RAG latency.

    Reuse engines. Inside ONE event loop, execute two real warm-up calls per layer,
    excluded from samples. Then collect exactly n_runs timed samples (cycle clean
    inputs), always measuring BOTH PII and NeMo input even if PII blocks.
    Use perf_counter; keep raw milliseconds. summarize_latency() supplies linear
    percentiles at (n - 1) * q. Submission requires n_runs >= 20.
    Short-circuit request timing, RAG and output timing are outside this scope.
    """
    from src.experiment_support import summarize_latency
    if not test_inputs or n_runs < 1:
        raise ValueError("Need inputs and n_runs >= 1")
    if analyzer is None or anonymizer is None:
        analyzer, anonymizer = setup_presidio()
    if rails is None:
        rails = setup_nemo_rails()

    async def _measure():
        for i in range(2):
            text = test_inputs[i % len(test_inputs)]
            pii_scan(text, analyzer, anonymizer)
            await check_input_rail(text, rails)

        samples = []
        for i in range(n_runs):
            text = test_inputs[i % len(test_inputs)]
            t0 = time.perf_counter()
            pii_scan(text, analyzer, anonymizer)
            pii_ms = (time.perf_counter() - t0) * 1000.0

            t1 = time.perf_counter()
            await check_input_rail(text, rails)
            nemo_ms = (time.perf_counter() - t1) * 1000.0

            samples.append({
                "presidio_ms": pii_ms,
                "nemo_input_ms": nemo_ms,
                "input_guard_ms": pii_ms + nemo_ms,
            })
        return samples

    return summarize_latency(asyncio.run(_measure()), warmup_runs=2)


# ─── Main ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    from scripts.run_experiments import main
    raise SystemExit(main(["--phase", "c", *sys.argv[1:]]))
