from django_cron import CronJobBase, Schedule
from django.core.exceptions import MultipleObjectsReturned
from autotriage.common_utils import retry_session
from restapi.models import Trainlogdata, AllBranch, SquadDetails
import json
import requests
import time, pprint


class PullCompletedSuites(CronJobBase):
    RUN_EVERY_MINS = 5

    schedule = Schedule(run_every_mins=RUN_EVERY_MINS)
    code = 'autotriage.PullCompletedSuites'

    def do(self):
        reports_base = "https://reports.eng.cohesity.com/api/v1/"
        common_headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        }
        os_branchs = {"cohesity":["hedp"],"helios_dmaas":["hedp","hecp"],"onprem":["hedp"]}
        for os,env in os_branchs.items():
            for dmaas_env in env:
                all_branch_list_url = (reports_base+"get_branch_list?os="+os+"&grouping=All&dmaas="+dmaas_env)
                session = retry_session(retries=5)
                all_branch_response = session.get(url=all_branch_list_url, headers=common_headers)
                if all_branch_response.status_code < 500:
                    all_branch_data = json.loads(all_branch_response.content)
                    for branch in all_branch_data:
                        print(os,dmaas_env,branch['name'])
                        _, branchcreated = AllBranch.objects.get_or_create(name=branch["name"])
                        if branchcreated:
                            print(branchcreated)

                    latestbuilds = []
                    for branch in all_branch_data:
                        branch_run_url = (reports_base+"e2ecoveragedatabybranch?branch=" +branch["name"] +
                                          "&area=all&type=all&train_type=all_train&report_type=testcase&date=-1&" +
                                          "build=-1&os="+os+"&grouping=All&tag=All&denv=All&dmaas="+dmaas_env)
                        try:
                            all_branch_run_response = session.get(
                                url=branch_run_url,
                                headers=common_headers,
                                timeout=240,
                            )
                            print(branch_run_url, all_branch_run_response.status_code)
                            if all_branch_run_response.status_code >= 400:
                                continue
                            try:
                                branch_coverage = all_branch_run_response.json()
                            except ValueError:
                                continue
                            latest_data = branch_coverage.get("header") or []
                            if len(latest_data) > 0:
                                sort_raw = latest_data[0].get("sort")
                                if sort_raw is None:
                                    time.sleep(0.5)
                                    print(latestbuilds)
                                    continue
                                try:
                                    least_run_date = int(sort_raw)
                                except (TypeError, ValueError):
                                    time.sleep(0.5)
                                    print(latestbuilds)
                                    continue
                                start_run_date = least_run_date - 3
                                for lrd in latest_data:
                                    s = lrd.get("sort")
                                    build_ver = lrd.get("build_version")
                                    if s is None or build_ver is None:
                                        continue
                                    try:
                                        sort_i = int(s)
                                    except (TypeError, ValueError):
                                        continue
                                    if start_run_date <= sort_i <= least_run_date:
                                        latestbuilds.append([branch["name"], build_ver])
                            time.sleep(0.5)
                        except requests.exceptions.RequestException:
                            continue
                        print(latestbuilds)

                    for logurl in latestbuilds:
                        train_by_build_url = (reports_base+"e2etrainlevelcoveragebybuild?branch="+logurl[0] +
                                              "&build=" + logurl[1] + "&area=-1&area_details_id=-1&train=-1&" +
                                              "train_type=all_train&os="+os+"&grouping=All&tag=All&denv=All&dmaas="+
                                              dmaas_env)
                        try:
                            all_train_name_response = session.get(url=train_by_build_url, headers=common_headers)
                            print(train_by_build_url, all_train_name_response.status_code)
                            all_train_name_data = json.loads(all_train_name_response.content)
                            if all_train_name_data.get("body") is not None and len(all_train_name_data) > 0:
                                for train in all_train_name_data["body"]:
                                    if train["area"] != "Grand Total":
                                        for name in train["train_list"]:
                                            if name["train_name"] != "Grand Total":
                                                # print(train["area"]+"###"+name["train_name"]+"###"+
                                                #       name["coverage"]["train_log_url"]+"###"+
                                                #       name["coverage"]["build_date"])
                                                try:
                                                    traindata, created = Trainlogdata.objects.get_or_create(
                                                        area=train["area"],
                                                        trainname=name["train_name"],
                                                        build=name["coverage"]["build_version"],
                                                        date=name["coverage"]["build_date"],
                                                        logurl=name["coverage"]["train_log_url"]
                                                    )
                                                    if created:
                                                        print(traindata)
                                                except MultipleObjectsReturned:
                                                    continue
                            time.sleep(0.5)
                        except requests.exceptions.ConnectionError as conn_err:
                            continue
                        except requests.exceptions.RetryError as retry_err:
                            continue

        for row in Trainlogdata.objects.all().reverse():
            if Trainlogdata.objects.filter(logurl=row.logurl).count() > 1:
                # print(row.trainname,row.build,row.date)
                row.delete()


class PullSquadDetails(CronJobBase):
    RUN_AT_TIMES = ['23:59']

    schedule = Schedule(run_at_times=RUN_AT_TIMES)
    code = 'autotriage.PullSquadDetails'

    def do(self):
        reports_base = "https://reports.eng.cohesity.com/api/v1/"
        common_headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        }
        os_branchs = ['cohesity', 'hecp', 'hedp', 'onprem']
        for os in os_branchs:
            all_branch_list_url = (reports_base + "get_branch_list?os=" + os)
            all_area_list_url = (reports_base + "get_area_list?os="+ os)
            session = retry_session(retries=5)
            all_branch_response = session.get(url=all_branch_list_url, headers=common_headers)
            all_branch_data = json.loads(all_branch_response.content)
            all_area_response = session.get(url=all_area_list_url, headers=common_headers)
            all_area_data = json.loads(all_area_response.content)
            # print(all_branch_data)
            for branch in all_branch_data:
                branch_name = branch.get("name")
                for area in all_area_data:
                    area_name = area.get("name")
                    get_train_url = (reports_base + "e2e-get-train-list?branch=" + branch_name + "&area=" +
                                     area_name)
                    all_train_response = session.get(url=get_train_url, headers=common_headers)
                    all_train_data = json.loads(all_train_response.content)
                    # pprint(all_train_data)
                    for train in all_train_data.get("trains"):
                        # print(os,branch_name,area_name,train)
                        all_suite_url = (reports_base + "get-all-suites?branch=" + branch_name + "&train=" +
                                         train + "&area=" + area_name)
                        all_suite_response = session.get(url=all_suite_url, headers=common_headers)
                        all_suite_detail = json.loads(all_suite_response.content)
                        for suite in all_suite_detail.get("suite_details"):
                            print(os,branch_name,area_name,train,suite.get("group"), suite.get("owner"),suite.get("squad"),suite.get("suite_name"))
                            try:
                                suitedata, created = SquadDetails.objects.get_or_create(
                                    os=os,
                                    branch=branch_name,
                                    area=area_name,
                                    train_name=train,
                                    suite_group=suite.get("group"),
                                    suite_owner=suite.get("owner"),
                                    suite_squad=suite.get("squad"),
                                    suite_name=suite.get("suite_name")
                                )
                                if created:
                                    print(suitedata)
                            except MultipleObjectsReturned:
                                continue



