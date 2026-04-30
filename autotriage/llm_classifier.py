"""
Classify test failure / error logs into fixed triage categories.

When LLM_API_BASE and LLM_MODEL are set, calls an OpenAI-compatible API to
infer the root failure from log text, assign a single triage label (category),
and return a short predicted failure description. Otherwise uses a
deterministic rules engine (same schema).
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

ALLOWED = frozenset(
    {
        "VM_CONFIG_ERROR",
        "VM_DISCOVERY_ERROR",
        "OBJECT_FETCH_ERROR",
        "NETWORK_ERROR",
        "PERMISSION_ERROR",
        "STORAGE_ERROR",
        "TIMEOUT_ERROR",
        "UNKNOWN",
    }
)

SYSTEM_PROMPT = """You are a production-grade error-log triage system for test and infrastructure failures.

Input: one or more lines of error output, stack traces, or failure logs from a test run.

Your tasks (in order):
1. Read the log and decide whether it describes a real failure or error (vs noise-only lines).
2. Predict what actually failed — the underlying root cause in plain language (not the log wording verbatim).
3. Assign exactly ONE triage label (category) from the list below that best matches that predicted failure.
4. Produce a short canonical "normalized_error" string so similar failures group together (stable wording, no volatile IDs).
5. Return ONLY a single JSON object, no markdown fences, no commentary.

Category definitions (pick ONE label):
- VM_CONFIG_ERROR — VM/template/.vmx configuration missing, corrupt, or inaccessible
- VM_DISCOVERY_ERROR — VM inventory or enumeration failed, empty object references
- OBJECT_FETCH_ERROR — Could not fetch or resolve protection/source objects
- NETWORK_ERROR — Connectivity, DNS, connection refused, unreachable host
- PERMISSION_ERROR — Authn/authz, forbidden, access denied
- STORAGE_ERROR — Datastore, disk, volume, NFS, VMFS issues (when not VM-specific config)
- TIMEOUT_ERROR — Deadlines, timeouts, hung operations
- UNKNOWN — Insufficient signal or does not map cleanly

Rules:
- Infer root cause from evidence in the log; do not invent components not implied by the text.
- Focus on root cause, not stack frame noise; strip volatile tokens from normalized_error.
- If the log shows no error/failure signal, set error_detected to false and category to UNKNOWN.

Return this JSON shape ONLY:
{
  "error_detected": true,
  "category": "ONE_CATEGORY_FROM_LIST",
  "predicted_failure": "one concise sentence: what failed and why (your inference from the log)",
  "normalized_error": "short stable label for grouping similar failures",
  "reason": "one sentence: which log lines or phrases support the category"
}
"""

USER_LOG_MESSAGE_TEMPLATE = """Analyze this error or failure log. Predict what failed, then assign the best triage label.

--- error log ---
{log}
--- end log ---
"""


def _normalize_category(raw: Optional[str]) -> str:
    if not raw:
        return "UNKNOWN"
    c = str(raw).strip().upper()
    if c in ALLOWED:
        return c
    return "UNKNOWN"


def classify_log_deterministic(log_text: str) -> Dict[str, Any]:
    """Same input -> same output; no network."""
    t = (log_text or "").lower()
    if not t.strip():
        return {
            "error_detected": False,
            "category": "UNKNOWN",
            "predicted_failure": "",
            "normalized_error": "",
            "reason": "empty log",
        }

    if "timeout" in t or "timed out" in t or "deadline exceeded" in t:
        return {
            "error_detected": True,
            "category": "TIMEOUT_ERROR",
            "predicted_failure": "The operation did not complete within the allowed time.",
            "normalized_error": "operation timed out",
            "reason": "timeout-related wording",
        }
    if "permission" in t or "unauthorized" in t or "forbidden" in t or "access denied" in t:
        return {
            "error_detected": True,
            "category": "PERMISSION_ERROR",
            "predicted_failure": "Access was denied due to permissions or credentials.",
            "normalized_error": "permission or authorization failure",
            "reason": "authz/authn failure indicators",
        }
    if "connection refused" in t or "no route to host" in t or "network is unreachable" in t or "dns" in t:
        return {
            "error_detected": True,
            "category": "NETWORK_ERROR",
            "predicted_failure": "Network connectivity or name resolution failed.",
            "normalized_error": "network connectivity failure",
            "reason": "network stack or connectivity",
        }
    if "datastore" in t or "disk" in t or "storage" in t or "nfs" in t or "volume" in t:
        if "unable to access" in t and "virtual machine configuration" in t:
            pass
        elif "vmfs" in t or "datastore" in t:
            return {
                "error_detected": True,
                "category": "STORAGE_ERROR",
                "predicted_failure": "Storage or datastore access failed.",
                "normalized_error": "storage subsystem failure",
                "reason": "storage/datastore indicators",
            }
    if "unable to access the virtual machine configuration" in t or ".vmtx" in t or ".vmx" in t:
        return {
            "error_detected": True,
            "category": "VM_CONFIG_ERROR",
            "predicted_failure": "The VM configuration or template file could not be read or was invalid.",
            "normalized_error": "unable to access VM configuration file",
            "reason": "VM configuration/template access failure",
        }
    if "failed to retrieve vms" in t or "object references is empty" in t:
        return {
            "error_detected": True,
            "category": "VM_DISCOVERY_ERROR",
            "predicted_failure": "VM inventory or discovery returned no usable VM references.",
            "normalized_error": "failed to retrieve VM objects",
            "reason": "VM inventory/discovery returned no references",
        }
    if "fetch source objects" in t or "createheliosobjectprotection" in t.replace(
        " ", ""
    ) or "unable to fetch source objects" in t:
        return {
            "error_detected": True,
            "category": "OBJECT_FETCH_ERROR",
            "predicted_failure": "Required source or protection objects could not be fetched.",
            "normalized_error": "unable to fetch protection source objects",
            "reason": "object protection source resolution failed",
        }
    err_like = any(
        x in t
        for x in ("error", "failed", "exception", "unable to", "fatal", "invalid")
    )
    ne = (log_text or "")[:200].replace("\n", " ").strip()
    return {
        "error_detected": bool(err_like),
        "category": "UNKNOWN",
        "predicted_failure": ne if err_like else "",
        "normalized_error": ne,
        "reason": "no deterministic rule matched" if err_like else "no error signal",
    }


def _extract_json_object(text: str) -> Optional[dict]:
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text, re.IGNORECASE)
    if fence:
        try:
            return json.loads(fence.group(1).strip())
        except json.JSONDecodeError:
            pass
    m = re.search(r"\{[\s\S]*\}\s*$", text)
    if not m:
        m = re.search(r"\{[\s\S]*\}", text)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return None


def classify_log_llm(log_text: str) -> Optional[Dict[str, Any]]:
    base = getattr(settings, "LLM_API_BASE", "") or ""
    model = getattr(settings, "LLM_MODEL", "") or ""
    if not base or not model:
        return None
    api_key = getattr(settings, "LLM_API_KEY", "") or ""
    url = base.rstrip("/") + "/chat/completions"
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    user_content = USER_LOG_MESSAGE_TEMPLATE.format(log=(log_text or "")[:8000])
    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
        "temperature": 0,
    }
    try:
        r = requests.post(url, headers=headers, json=body, timeout=120)
        r.raise_for_status()
        data = r.json()
        content = data["choices"][0]["message"]["content"]
        parsed = _extract_json_object(content)
        if not parsed:
            return None
        cat = _normalize_category(parsed.get("category"))
        pred = parsed.get("predicted_failure")
        if pred is None or str(pred).strip() == "":
            pred = parsed.get("normalized_error", "")
        return {
            "error_detected": bool(parsed.get("error_detected", True)),
            "category": cat,
            "predicted_failure": str(pred)[:500],
            "normalized_error": str(parsed.get("normalized_error", ""))[:500],
            "reason": str(parsed.get("reason", ""))[:500],
        }
    except Exception as exc:
        logger.warning("LLM classify failed: %s", exc)
        return None


def classify_log(log_text: str) -> Dict[str, Any]:
    llm = classify_log_llm(log_text)
    if llm:
        return llm
    return classify_log_deterministic(log_text)


def classify_logs_batch(logs: List[str]) -> List[Dict[str, Any]]:
    return [classify_log(x) for x in logs]


def error_signature_key_from_llm(result: Dict[str, Any]) -> str:
    """Session grouping key for triage UI (replaces UnknownErrSig bucket)."""
    cat = result.get("category") or "UNKNOWN"
    ne = (result.get("normalized_error") or "").strip() or "unclassified"
    return f"{cat}: {ne}"
