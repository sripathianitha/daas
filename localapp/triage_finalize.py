"""
Shared train/suite triage aggregation for v2 analyze flows (reports API + watchmen URL).
"""
from __future__ import annotations

import re
from collections import defaultdict
from operator import itemgetter
from typing import Any, DefaultDict, Dict, List

from django.http import HttpResponseNotFound, JsonResponse

from autotriage.common_utils import cleanup_text
from autotriage.llm_classifier import classify_log, error_signature_key_from_llm
from restapi.models import ErrorSignature, OptimalSolution, SevereDetail


def _attach_llm_fields(row: dict, raw_msg: str) -> None:
    r = classify_log(raw_msg or "")
    row["llm_category"] = r.get("category", "UNKNOWN")
    row["normalized_error"] = r.get("normalized_error", "")
    row["llm_predicted_failure"] = r.get("predicted_failure", "")
    row["llm_reason"] = r.get("reason", "")


def regroup_unknown_failures_with_llm(train_data: DefaultDict[str, list]) -> None:
    """Split UnknownErrSig into LLM/deterministic category buckets."""
    if "UnknownErrSig" not in train_data:
        return
    unknown_rows = train_data.pop("UnknownErrSig")
    for row in unknown_rows:
        raw = row.get("rawerrormsg") or row.get("cleanederrormsg") or ""
        r = classify_log(raw)
        key = error_signature_key_from_llm(r)
        row["llm_category"] = r.get("category", "UNKNOWN")
        row["normalized_error"] = r.get("normalized_error", "")
        row["llm_predicted_failure"] = r.get("predicted_failure", "")
        row["llm_reason"] = r.get("reason", "")
        row["cleanerrsig"] = "UnknownErrSig"
        train_data[key].append(row)


def build_train_failure_map(
    all_suite_json_data: Dict[str, Any],
    trainname: str,
) -> DefaultDict[str, list]:
    error_signature = ErrorSignature.objects.values("signature", "readable_sig")
    unique_signature = [dict(uniq_sig) for uniq_sig in {tuple(sig.items()) for sig in error_signature}]
    train_data: DefaultDict[str, list] = defaultdict(list)

    for suite in all_suite_json_data["body"]:
        if suite["passed_per"] > 93:
            suite_color_code = "background-color: #55C595;"
        elif 68 <= suite["passed_per"] <= 93:
            suite_color_code = "background-color: #FF9800;"
        else:
            suite_color_code = "background-color: #FB0909;"
        if suite.get("testcase_results") is None:
            continue
        for tc_data in suite["testcase_results"]:
            if tc_data["status"] == "Failed":
                if tc_data.get("error_msg") is not None:
                    failure_msg = re.sub(r"^/home.*\n?", "", tc_data["error_msg"], flags=re.MULTILINE)
                    cleaned_failure_msg = cleanup_text(failure_msg)
                    matched = False
                    for signature in unique_signature:
                        err_sig_pattern = signature["signature"].replace("*", "[a-zA-Z]+")
                        escaped_err_sig_pattern = re.escape(err_sig_pattern)
                        if re.search(rf"\b{escaped_err_sig_pattern}\b", cleaned_failure_msg):
                            matched = True
                            try:
                                core_error = signature["signature"]
                                solutions = OptimalSolution.objects.filter(
                                    cleaned_error_msg__icontains=core_error
                                )
                                solution = solutions.first()
                                if solution:
                                    if solution.err_signature.common_solution_flag:
                                        optimal_solution = solution.err_signature.common_solution
                                    elif solution.optimal_solution:
                                        optimal_solution = solution.optimal_solution
                                    else:
                                        optimal_solution = "No Optimal Solution So far!"
                                    train_data[solution.err_signature.readable_sig.rstrip()].append(
                                        {
                                            "suitename": suite["suite_name"],
                                            "trainname": trainname,
                                            "suitecolorcode": suite_color_code,
                                            "suiteperc": suite["passed_per"],
                                            "squadname": suite["squad"],
                                            "testcasename": tc_data["test_name"],
                                            "cleanederrormsg": cleaned_failure_msg,
                                            "rawerrormsg": failure_msg,
                                            "optimalsolution": optimal_solution,
                                            "status": "failure",
                                            "cleanerrsig": solution.err_signature.signature.rstrip(),
                                            "logurl": tc_data["log"],
                                        }
                                    )
                                    _attach_llm_fields(
                                        train_data[solution.err_signature.readable_sig.rstrip()][-1],
                                        failure_msg,
                                    )
                                else:
                                    raise OptimalSolution.DoesNotExist
                                break
                            except OptimalSolution.DoesNotExist:
                                err_sig_obj = ErrorSignature.objects.get(signature=signature["signature"])
                                if err_sig_obj.common_solution:
                                    optimal_solution = err_sig_obj.common_solution
                                else:
                                    optimal_solution = "No Optimal Solution So far!"
                                train_data[err_sig_obj.readable_sig.rstrip()].append(
                                    {
                                        "suitename": suite["suite_name"],
                                        "trainname": trainname,
                                        "suitecolorcode": suite_color_code,
                                        "suiteperc": suite["passed_per"],
                                        "squadname": suite["squad"],
                                        "testcasename": tc_data["test_name"],
                                        "cleanederrormsg": cleaned_failure_msg,
                                        "rawerrormsg": failure_msg,
                                        "optimalsolution": optimal_solution,
                                        "cleanerrsig": err_sig_obj.signature.rstrip(),
                                        "status": "failure",
                                        "logurl": tc_data["log"],
                                    }
                                )
                                _attach_llm_fields(
                                    train_data[err_sig_obj.readable_sig.rstrip()][-1],
                                    failure_msg,
                                )
                                break
                    if not matched:
                        train_data["UnknownErrSig"].append(
                            {
                                "suitename": suite["suite_name"],
                                "trainname": trainname,
                                "suitecolorcode": suite_color_code,
                                "suiteperc": suite["passed_per"],
                                "squadname": suite["squad"],
                                "testcasename": tc_data["test_name"],
                                "cleanederrormsg": cleaned_failure_msg,
                                "rawerrormsg": failure_msg,
                                "optimalsolution": "No Optimal Solution So far!",
                                "cleanerrsig": "UnknownErrSig",
                                "status": "failure",
                                "logurl": tc_data["log"],
                            }
                        )
                else:
                    train_data["UnknownErrSig"].append(
                        {
                            "suitename": suite["suite_name"],
                            "trainname": trainname,
                            "suitecolorcode": suite_color_code,
                            "suiteperc": suite["passed_per"],
                            "squadname": suite["squad"],
                            "testcasename": tc_data["test_name"],
                            "cleanederrormsg": "Suite Summary is not generated",
                            "rawerrormsg": "Suite Summary is not generated",
                            "optimalsolution": "No Optimal Solution So far!",
                            "cleanerrsig": "UnknownErrSig",
                            "status": "failure",
                            "logurl": tc_data["log"],
                        }
                    )
            elif tc_data["status"] == "Skipped":
                train_data["Skipped"].append(
                    {
                        "suitename": suite["suite_name"],
                        "suitecolorcode": suite_color_code,
                        "suiteperc": suite["passed_per"],
                        "squadname": suite["squad"],
                        "trainname": trainname,
                        "testcasename": tc_data["test_name"],
                        "status": "skipped",
                    }
                )
            else:
                train_data["PassedTc"].append(
                    {
                        "suitename": suite["suite_name"],
                        "suitecolorcode": suite_color_code,
                        "suiteperc": suite["passed_per"],
                        "squadname": suite["squad"],
                        "testcasename": tc_data["test_name"],
                        "trainname": trainname,
                        "status": "passed",
                        "logurl": tc_data["log"],
                    }
                )
    regroup_unknown_failures_with_llm(train_data)
    return train_data


def finalize_v2_session_and_json(
    request,
    all_suite_json_data: Dict[str, Any],
    branch: str,
    trainname: str,
    build: str,
    category: str,
    severe: bool,
) -> JsonResponse | HttpResponseNotFound:
    total_tc_executed_count_in_train = sum(
        suite.get("total_executed", 0) for suite in all_suite_json_data["body"]
    )
    if total_tc_executed_count_in_train == 0:
        return HttpResponseNotFound(
            "Seems none the testcases executed in "
            + trainname
            + ". If train is still running, please check the analysis report in sometime later!"
        )

    train_data = build_train_failure_map(all_suite_json_data, trainname)

    if request.session.get("errormsgdata"):
        del request.session["errormsgdata"]
    request.session["errormsgdata"] = train_data

    final_list: List[dict] = []
    unique_suite_impacted = set()
    total_tc_perc = 0.0
    total_failures = 0
    total_tc_count_in_train = sum(suite.get("total", 0) for suite in all_suite_json_data["body"])
    total_passed_tc_count_in_train = sum(suite.get("passed", 0) for suite in all_suite_json_data["body"])
    total_failed_tc_count_in_train = sum(suite.get("failed", 0) for suite in all_suite_json_data["body"])
    total_skipped_tc_count_in_train = sum(suite.get("skipped", 0) for suite in all_suite_json_data["body"])
    train_pass_per = round((total_passed_tc_count_in_train / total_tc_executed_count_in_train) * 100, 2)
    train_coverage_per = round(100 - train_pass_per, 2)

    if category == "error":
        severe_err_category = None
        if severe and all_suite_json_data.get("severe_data") not in (None, "emptysevere", {}):
            if request.session.get("severelogdata"):
                del request.session["severelogdata"]
            severe_err_category = {"buggy": [], "expected": [], "need_analysis": [], "new_error": []}
            for serr_msg in all_suite_json_data["severe_data"].keys():
                slog_data, created = SevereDetail.objects.get_or_create(cleaned_error=serr_msg)
                if created:
                    severe_err_category["new_error"].append(serr_msg)
                else:
                    severe_err_category[slog_data.error_category].append(serr_msg)
            request.session["severelogdata"] = {
                "scat": severe_err_category,
                "sdata": all_suite_json_data["severe_data"],
            }
        for err_sig, tdata in train_data.items():
            if err_sig != "PassedTc" and err_sig != "Skipped":
                failure_count = list(filter(lambda f: f["status"] == "failure", tdata))
                suite_impacted = set(suite_name["suitename"] for suite_name in failure_count)
                unique_suite_impacted.update(suite_impacted)
                testcase_impact = round((len(failure_count) / total_tc_count_in_train) * 100, 2)
                total_tc_perc += testcase_impact
                total_failures += len(failure_count)
                final_list.append(
                    {
                        "error_sig": err_sig,
                        "suite_impact": len(suite_impacted),
                        "testcase_impact": testcase_impact,
                        "failure_count": len(failure_count),
                    }
                )
        sorted_final_list = sorted(final_list, key=itemgetter("failure_count"), reverse=True)
        json_data = {
            "errordata": sorted_final_list,
            "total_impacted_suite": len(unique_suite_impacted),
            "total_tc_perc": round(total_tc_perc, 2),
            "total_failure_count": total_failures,
            "total_suite_count": len(all_suite_json_data["body"]),
        }
        if severe_err_category is not None and all_suite_json_data.get("severe_data") != "emptysevere":
            json_data["severedata"] = severe_err_category
        return JsonResponse(json_data)

    if category == "suite":
        final_list = []
        for suite in all_suite_json_data["body"]:
            suite_tc_imp = round((int(suite["failed"]) / total_tc_count_in_train) * 100, 2)
            coverage_imp = 100 - int(suite["coverage_per"])
            suite_pass_percentage = suite["passed_per"]
            if suite_pass_percentage > 93:
                suite_color_code = "background-color: #55C595;"
            elif 68 <= suite_pass_percentage <= 93:
                suite_color_code = "background-color: #FF9800;"
            else:
                suite_color_code = "background-color: #FB0909;"
            final_list.append(
                {
                    "suite": suite["suite_name"],
                    "testcase_impact": suite_tc_imp,
                    "skipped": suite["skipped"],
                    "coverage_impact": coverage_imp,
                    "passed": suite["passed"],
                    "failure_count": suite["failed"],
                    "pass_perc": suite["passed_per"],
                    "squad": suite["squad"],
                    "ccode": suite_color_code,
                    "totaltc": suite["total"],
                    "executed": suite["total_executed"],
                    "trainname": trainname,
                }
            )
        sorted_final_list = sorted(final_list, key=itemgetter("failure_count"), reverse=True)
        return JsonResponse(
            {
                "suitedata": sorted_final_list,
                "total": total_tc_count_in_train,
                "executed": total_tc_executed_count_in_train,
                "passed": total_passed_tc_count_in_train,
                "failed": total_failed_tc_count_in_train,
                "skipped": total_skipped_tc_count_in_train,
                "total_per": train_pass_per,
                "train_impact": train_coverage_per,
            }
        )

    return JsonResponse({"errordata": []})
