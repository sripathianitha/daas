"""
Build triage session data by crawling a watchmen_logs directory over HTTP(S),
without the reports API or django-cron Trainlogdata sync.
"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from collections import defaultdict
from typing import Any, DefaultDict, Dict, List, Optional, Tuple
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from django.conf import settings


def _normalize_base_url(url: str) -> str:
    u = (url or "").strip()
    if not u:
        return u
    if not u.endswith("/"):
        u += "/"
    return u


def _fetch_text(url: str, timeout: int = 120) -> str:
    verify = getattr(settings, "WATCHMEN_HTTP_VERIFY_SSL", True)
    r = requests.get(url, timeout=timeout, verify=verify)
    r.raise_for_status()
    return r.text


def _list_subdirectory_hrefs(page_url: str) -> List[Tuple[str, str]]:
    """Return (href, label) for subdirectory links from an Apache-style listing."""
    html = _fetch_text(page_url)
    soup = BeautifulSoup(html, "html.parser")
    out: List[Tuple[str, str]] = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if href in ("../", "?C=N;O=D", "?C=M;O=A", "?C=S;O=A", "?C=D;O=A"):
            continue
        if not href.endswith("/"):
            continue
        if href.startswith("?"):
            continue
        out.append((href, a.get_text(strip=True) or href.rstrip("/")))
    return out


def _suite_name_from_folder(folder_href: str) -> str:
    base = folder_href.rstrip("/").split("/")[-1]
    m = re.match(r"^(.+?)-\d{4}-\d{1,2}-\d{1,2}-\d{1,2}-\d{1,2}-\d{1,2}-[A-Za-z0-9]+$", base)
    if m:
        return m.group(1)
    return base.split("-")[0] if "-" in base else base


def _find_junit_href(suite_page_url: str) -> Optional[str]:
    html = _fetch_text(suite_page_url)
    soup = BeautifulSoup(html, "html.parser")
    for a in soup.find_all("a", href=True):
        h = a["href"]
        if "junit.xml" in h.lower() or h.lower().endswith("junit.xml"):
            return h
    return None


def _find_tc_log_map(suite_page_url: str) -> Dict[str, str]:
    """Map normalized testcase key -> href to folder or INFO file."""
    html = _fetch_text(suite_page_url)
    soup = BeautifulSoup(html, "html.parser")
    name_only: Dict[str, str] = {}
    for link in soup.find_all("a", href=True):
        label = link.get_text(strip=True)
        if label in ("Name", "Last modified", "Size", "Description", "Parent Directory"):
            continue
        tc_name = re.sub(r"[_#]{2}TR[:Cc0-9,\s]+(TR[_#]{2})?", "", label)
        tc_name = re.sub(r"^[\d]+_", "", tc_name.replace("/", ""))
        tc_name = tc_name.replace(" ", "_")
        name_only[tc_name] = label
    return name_only


def _parse_junit(junit_xml: str) -> List[Dict[str, Any]]:
    root = ET.fromstring(junit_xml)
    cases: List[Dict[str, Any]] = []
    for tc in root.findall("testcase"):
        name = tc.get("name", "")
        classname = tc.get("classname", "")
        failure = tc.find("failure")
        skipped = tc.find("skipped")
        if failure is not None:
            text = (failure.text or "") + (failure.attrib.get("message") or "")
            cases.append(
                {
                    "test_name": name,
                    "classname": classname,
                    "status": "Failed",
                    "error_msg": text,
                }
            )
        elif skipped is not None:
            cases.append({"test_name": name, "classname": classname, "status": "Skipped"})
        else:
            cases.append({"test_name": name, "classname": classname, "status": "Passed"})
    return cases


def _suite_pass_meta(testcases: List[Dict[str, Any]]) -> Tuple[int, float, str]:
    total = len(testcases)
    failed = sum(1 for t in testcases if t["status"] == "Failed")
    if total == 0:
        return 0, 100.0, "background-color: #55C595;"
    pct = round(100 - ((failed / total) * 100), 2)
    if pct > 93:
        cc = "background-color: #55C595;"
    elif 68 <= pct <= 93:
        cc = "background-color: #FF9800;"
    else:
        cc = "background-color: #FB0909;"
    return failed, float(pct), cc


def _attach_logs(
    suite_log_url: str,
    testcases: List[Dict[str, Any]],
    tc_name_only: Dict[str, str],
) -> None:
    suite_log_url = suite_log_url.rstrip("/") + "/"
    for db_tc in testcases:
        if db_tc["status"] not in ("Passed", "Failed"):
            continue
        db_name = db_tc["test_name"]
        db_name = re.sub(r"^(Prepare-)|(Result-)|(Execute-)", "", db_name)
        db_name = db_name.replace(" ", "_")
        for log_key, orig in list(tc_name_only.items()):
            if log_key in db_name:
                db_tc["log"] = suite_log_url + orig + "VanillaGinkgo.INFO"
                del tc_name_only[log_key]
                break
        else:
            db_tc["log"] = suite_log_url + "suite_summary.html"


def build_suites_from_watchmen_url(
    watchmen_log_url: str,
    squad_by_suite: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """
    Returns a structure compatible with train_analyze_result_v2 processing:
    { 'body': [ suite dicts with testcase_results, suite_name, passed_per, ... ] }
    """
    squad_by_suite = squad_by_suite or {}
    base = _normalize_base_url(watchmen_log_url)
    subdirs = _list_subdirectory_hrefs(base)
    body: List[Dict[str, Any]] = []

    for href, _label in subdirs:
        suite_page_url = urljoin(base, href)
        junit_rel = _find_junit_href(suite_page_url)
        if not junit_rel:
            continue
        junit_url = urljoin(suite_page_url, junit_rel)
        junit_xml = _fetch_text(junit_url)
        tcs = _parse_junit(junit_xml)
        failed, passed_per, color = _suite_pass_meta(tcs)
        suite_name = _suite_name_from_folder(href)
        tc_map = _find_tc_log_map(suite_page_url)
        tc_map_copy = dict(tc_map)
        _attach_logs(suite_page_url, tcs, tc_map_copy)

        body.append(
            {
                "suite_name": suite_name,
                "suite_log_url": suite_page_url.rstrip("/"),
                "squad": squad_by_suite.get(suite_name, "NA"),
                "passed": sum(1 for t in tcs if t["status"] == "Passed"),
                "failed": failed,
                "skipped": sum(1 for t in tcs if t["status"] == "Skipped"),
                "total": len(tcs),
                "total_executed": len(tcs),
                "passed_per": passed_per,
                "coverage_per": int(round(100 - passed_per)),
                "testcase_results": tcs,
            }
        )

    return {"body": body, "severe_data": "emptysevere"}
