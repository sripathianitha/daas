import pprint
import time

from django.shortcuts import render
from bs4 import BeautifulSoup
from django.http import JsonResponse, HttpResponseNotFound
from restapi.models import Trainlogdata, OptimalSolution, ErrorSignature, AllBranch, SquadDetails, SevereDetail
from localapp.models import TagMapping
from django.conf import settings
import paramiko, json, datetime
from collections import defaultdict, OrderedDict
import urllib.request
from autotriage.common_utils import *
import xmltodict, requests
from operator import itemgetter
from django.core.exceptions import ObjectDoesNotExist
from autotriage.mock_mongo import get_mongo_database
from localapp.triage_finalize import finalize_v2_session_and_json
from localapp.watchmen_ingest import build_suites_from_watchmen_url
import re
from urllib.request import urlopen
import asyncio
from unparallel import up
from unparallel.unparallel import RequestError
from concurrent.futures import ThreadPoolExecutor, as_completed
from asgiref.sync import sync_to_async


# Create your views here.
def dashboard(request):
    """
    Home page dropdown datas
    """
    db = get_mongo_database()

    startdate = datetime.datetime.today() - datetime.timedelta(days=30)
    formated_start_date = startdate.strftime("%Y%m%d")
    sfsd = str(formated_start_date)
    enddate = datetime.datetime.today()
    formated_end_date = enddate.strftime("%Y%m%d")
    sfed = str(formated_end_date)

    # alltrains = Trainlogdata.objects.filter(date__range=[sfsd,sfed]).order_by('-date').values()
    collection = db["restapi_trainlogdata"]
    alltrains = collection.find({'date':{'$gte':sfsd,'$lte':sfed}}).sort("build", 1)
    unique_build = []
    for train in alltrains:
        # build = train['build'].split("-")[0].split("_")[0]
        if train['build'] not in unique_build:
            unique_build.append(train['build'])
    branch_collection = db['restapi_allbranch']
    allbranchs = branch_collection.find().sort("name",1)
    unique_branch = []
    for branch in allbranchs:
        for build in unique_build:
            if build.startswith(branch['name']) and branch['name'] not in unique_branch:
                unique_branch.append(branch['name'])
                break

    collection_name = 'restapi_squaddetails'
    collection = db[collection_name]
    train_pipeline = [{'$group': {'_id': '$train_name','count': {'$sum': 1}}},{'$count': 'unique_trains_count'}]
    train_count_result = list(collection.aggregate(train_pipeline))
    unique_trains_count = train_count_result[0]['unique_trains_count'] if train_count_result else 0

    squad_pipeline = [{'$group': {'_id': '$suite_squad','count': {'$sum': 1}}},{'$count': 'unique_squad_count'}]
    squad_count_result = list(collection.aggregate(squad_pipeline))
    unique_squad_count = squad_count_result[0]['unique_squad_count'] if squad_count_result else 0

    suite_pipeline = [{'$group': {'_id': '$suite_name','count': {'$sum': 1}}},{'$count': 'unique_suite_count'}]
    suite_count_result = list(collection.aggregate(suite_pipeline))
    unique_suite_count = suite_count_result[0]['unique_suite_count'] if suite_count_result else 0


    branchs_count = len(AllBranch.objects.all())
    error_signature_count = len(ErrorSignature.objects.all())
    optimal_solution = len(OptimalSolution.objects.exclude(optimal_solution__isnull=True).exclude(optimal_solution__exact=''))
    common_solution = len(ErrorSignature.objects.exclude(common_solution__isnull=True).exclude(common_solution__exact=''))

    return render(request, "index.html", {"branchs":unique_branch,"branchs_count":branchs_count,
                                          "error_sig_count":error_signature_count,
                                          "optimal_solution_count":optimal_solution+common_solution,
                                          "trains_count": unique_trains_count, "suites_count": unique_suite_count,
                                          "squads_count": unique_squad_count})


def dashboard_v2(request):
    db = get_mongo_database()

    startdate = datetime.datetime.today() - datetime.timedelta(days=30)
    formated_start_date = startdate.strftime("%Y%m%d")
    sfsd = str(formated_start_date)
    enddate = datetime.datetime.today()
    formated_end_date = enddate.strftime("%Y%m%d")
    sfed = str(formated_end_date)

    # alltrains = Trainlogdata.objects.filter(date__range=[sfsd,sfed]).order_by('-date').values()
    collection = db["restapi_trainlogdata"]
    alltrains = collection.find({'date':{'$gte':sfsd,'$lte':sfed}}).sort("build", 1)
    unique_build = []
    for train in alltrains:
        # build = train['build'].split("-")[0].split("_")[0]
        if train['build'] not in unique_build:
            unique_build.append(train['build'])
    branch_collection = db['restapi_allbranch']
    allbranchs = branch_collection.find().sort("name",1)
    unique_branch = []
    for branch in allbranchs:
        for build in unique_build:
            if build.startswith(branch['name']) and branch['name'] not in unique_branch:
                unique_branch.append(branch['name'])
                break
    return render(request, "v2/index.html", {"branchs": unique_branch})

def trainname_by_branch(request,branch):
    """
    This function helps to filter train names by the branch for home page dropdown.
    """
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    if is_ajax:
        if request.method == 'GET':
            startdate = datetime.datetime.today() - datetime.timedelta(days=30)
            formated_start_date = startdate.strftime("%Y%m%d")
            sfsd = str(formated_start_date)
            enddate = datetime.datetime.today()
            formated_end_date = enddate.strftime("%Y%m%d")
            sfed = str(formated_end_date)
            db = get_mongo_database()
            collection = db["restapi_trainlogdata"]
            branch_startswith_patt = re.compile(r'^'+branch)
            train_log_query = { '$and':
                                    [
                                        {'build': {'$regex': branch_startswith_patt}},
                                        {'date':{'$gte':sfsd,'$lte':sfed}}
                                    ]
            }
            # alltrains = Trainlogdata.objects.filter(build__startswith=branch,date__range=[sfsd,sfed]).order_by('-date')
            alltrains = collection.find(train_log_query).sort("date",-1 )
            list_of_train = []
            for tn in alltrains:
                if tn['trainname'] not in list_of_train:
                    list_of_train.append(tn['trainname'])
            return JsonResponse(list_of_train,safe=False)


def build_by_branch_train(request,branch,train_name):
    """
    This function helps to filter train names by the branch and trainname for home page dropdown.
    """
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    if is_ajax:
        if request.method == 'GET':
            startdate = datetime.datetime.today() - datetime.timedelta(days=30)
            formated_start_date = startdate.strftime("%Y%m%d")
            sfsd = str(formated_start_date)
            enddate = datetime.datetime.today()
            formated_end_date = enddate.strftime("%Y%m%d")
            sfed = str(formated_end_date)

            db = get_mongo_database()
            collection = db["restapi_trainlogdata"]
            branch_startswith_patt = re.compile(r'^'+branch)
            train_log_query = { '$and':
                                    [
                                        {'trainname':train_name},
                                        {'build': {'$regex': branch_startswith_patt}},
                                        {'date':{'$gte':sfsd,'$lte':sfed}}
                                    ]
            }
            builds_and_squad = {}
            builds = collection.find(train_log_query).sort("date",-1 )
            # # builds = Trainlogdata.objects.filter(date__range=[sfsd,sfed]).filter(trainname=train_name).filter(build__startswith=branch).order_by('-date')
            # print(builds)
            list_of_builds = []
            for build in builds:
                if build['build'] not in list_of_builds:
                    list_of_builds.append(build['build'])
            builds_and_squad['builds'] = list_of_builds
            sqauds = SquadDetails.objects.filter(branch=branch).filter(train_name=train_name)
            list_of_squad = []
            for squad in sqauds:
                if squad.suite_squad not in list_of_squad and squad.suite_squad != "NA":
                    list_of_squad.append(squad.suite_squad)
            builds_and_squad['squad'] = list_of_squad
            tags = TagMapping.objects.filter(train_name__contains=train_name).values('tag_name__name').distinct()
            if len(tags) > 0:
                builds_and_squad['tags'] = sorted([tag['tag_name__name'] for tag in tags ])
            return JsonResponse(builds_and_squad,safe=False)

def train_analyze_result(request):
    """
    1. Fetch the watchmen log folder based on given input.
    2. Collecting the Junit file in train folder
    3. Collecting logfile for each testcase in each test suite.
    4. Iteration junit file and calculating the passed, failed, skipped data.
    5. Return the analyzed data
    """
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    if is_ajax:
        if request.method == 'POST':
            error_signature = ErrorSignature.objects.values('signature','readable_sig')
            unique_signature = [dict(uniq_sig) for uniq_sig in {tuple(sig.items()) for sig in error_signature}]
            request_data = json.load(request)
            branch = request_data.get("branch")
            trainname = request_data.get("trainname")
            build = request_data.get("build")
            category = request_data.get("category")
            squad = request_data.get("squad")
            logdata = Trainlogdata.objects.filter(build=build, trainname=trainname).order_by('id')
            train_junit_paths = {}
            for logs in logdata:
                watchmenfolder = logs.logurl.split("/")[-1]
                train_root_folder = "/home/cohesity/data/cohesityShare/watchmen_logs/" + watchmenfolder
                list_of_suite_cmd = "cd "+train_root_folder+";ls -l | grep ^d | awk '{split($9,fname,\"-\"); print fname[1]}'| xargs -I {} sh -c 'ls {}*/{}*/*.xml'"
                client = paramiko.client.SSHClient()
                client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                client.connect(settings.PLUTOURL, username=settings.PLUTOUSERNAME, password=settings.PLUTOPASSWORD)
                _stdin, _stdout, _stderr = client.exec_command(list_of_suite_cmd)
                train_suite_list = _stdout.read().decode().splitlines()
                client.close()
                if len(train_suite_list) > 0:
                    for junit_path in train_suite_list:
                        suitename = junit_path.split('/')[0].split('-')[0]
                        junit_path = ("https://" + settings.PLUTOURL + "/cohesityShare/watchmen_logs/" +
                                      watchmenfolder + "/" + junit_path)
                        train_junit_paths[suitename] = junit_path
                else:
                    return HttpResponseNotFound(trainname + " analysis result is not avaialble for " + build + " build!")

            train_data = defaultdict(list)
            suite_tc_executed_count = defaultdict(dict)
            total_tc_count_in_train = 0
            total_tc_count_in_suite = {}  # It will hold suite name as key and its respective total testcase count.
            total_executed_tc_count_in_suite = {}

            squads_details = SquadDetails.objects.filter(branch=branch, train_name=trainname)

            for suitename, junit_url in train_junit_paths.items():
                suite_squad_name = "NA"
                for squadname in squads_details:
                    if squadname.suite_name.lower() == suitename.lower() and squadname.suite_squad.lower()!= "na":
                        suite_squad_name = squadname.suite_squad
                if squad != "all" and suite_squad_name != squad:
                    continue
                suite_tc_executed_count[suitename]["squad"] = suite_squad_name
                watchmenfolder = junit_url.split("/")[-4]
                train_root_folder = "/home/cohesity/data/cohesityShare/watchmen_logs/" + watchmenfolder
                actual_suite_folder = junit_url.split("/")[-3]
                # print(actual_suite_folder)
                list_of_testcase_log_cmd = "cd "+train_root_folder+"/"+actual_suite_folder+";ls -l | grep ^d | awk '{split($9,fname,\"-\"); print fname[1]}'| xargs -I {} sh -c 'ls {}*/VanillaGinkgo.INFO'"
                # print(list_of_testcase_log_cmd)
                ssh_client_for_log = paramiko.client.SSHClient()
                ssh_client_for_log.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                ssh_client_for_log.connect(settings.PLUTOURL, username=settings.PLUTOUSERNAME, password=settings.PLUTOPASSWORD)
                _stdin, _stdout, _stderr = ssh_client_for_log.exec_command(list_of_testcase_log_cmd)
                testcases_log_list = _stdout.read().decode().splitlines()
                allcluster_cmd = "cd "+train_root_folder+"/"+actual_suite_folder+";grep -oP 'Found the cluster with tag:\[[A-Za-z0-9]*\]' VanillaGinkgo.INFO | cut -d \"[\" -f2 | rev | cut -c2- | rev | sort | uniq"
                _acstdin, _acstdout, _acstderr = ssh_client_for_log.exec_command(allcluster_cmd)
                all_cluster_list = _acstdout.read().decode().splitlines()
                # sorted_log_list = sorted(testcases_log_list,key=lambda x: (int(x.partition("_")[0]), x.partition("_")[1:].strip(',')))

                ssh_client_for_log.close()
                try:
                    # code to open and process the junit file.
                    read_junit_file = urlopen_with_retry(junit_url)
                    junit_data = read_junit_file.read()
                    read_junit_file.flush()
                    read_junit_file.close()
                except urllib.request.HTTPError as err:
                    print(f'An HTTP error occurred: {err}')
                    continue

                junit_dict = xmltodict.parse(junit_data)

                if junit_dict['testsuite']['@tests'] == '0':
                    continue
                if junit_dict['testsuite']['@tests']  == "1" and (type(junit_dict['testsuite']['testcase']) is str or type(junit_dict['testsuite']['testcase']) is dict):
                    junit_dict['testsuite']['testcase'] = [junit_dict['testsuite']['testcase']]
                if type(junit_dict['testsuite']['testcase']) is dict:
                    junit_dict['testsuite']['testcase'] = [junit_dict['testsuite']['testcase']]

                suite_tc_executed_count[suitename] = {"passed":0,"failed":0,"skipped":0,"percentage":0,
                                                      "color_code":"white", "squad":"NA"}
                total_tc_count_in_train += len(junit_dict['testsuite']['testcase']) if int(junit_dict['testsuite']['@tests']) < len(junit_dict['testsuite']['testcase']) else int(junit_dict['testsuite']['@tests'])
                total_tc_count_in_suite[suitename] = junit_dict['testsuite']['@tests']
                total_executed_tc_count_in_suite[suitename] = len(junit_dict['testsuite']['testcase']) if junit_dict['testsuite']['@tests'] != "1" else 1
                if total_tc_count_in_suite[suitename] == "1" and (type(junit_dict['testsuite']['testcase']) is str or type(junit_dict['testsuite']['testcase']) is dict):
                    junit_dict['testsuite']['testcase'] = [junit_dict['testsuite']['testcase']]
                suite_pass_percentage = round(100 - ((int(junit_dict['testsuite']['@failures'])/int(junit_dict['testsuite']['@tests'])) * 100),2)
                suite_tc_executed_count[suitename]["percentage"] = suite_pass_percentage
                if suite_pass_percentage > 93:
                    suite_color_code = "background-color: rgb(76, 184, 126);"
                elif 68 <= suite_pass_percentage <= 93:
                    suite_color_code = "background-color: rgb(201, 168, 70);"
                elif suite_pass_percentage < 68 :
                    suite_color_code = "background-color: rgb(244, 67, 54);"
                suite_tc_executed_count[suitename]["color_code"] = suite_color_code
                for xmltag in junit_dict['testsuite']['testcase']:
                    if xmltag["@name"] == "AfterSuite":
                        total_executed_tc_count_in_suite[suitename] = len(junit_dict['testsuite']['testcase']) - 1
                    removed_cluster_name = get_testcase_name(xmltag['@name'].lower(),all_cluster_list)
                    cleaned_xml_testcase_name = cleaned_testcase_name(removed_cluster_name)
                    tc_log_url = ""
                    for log in testcases_log_list:
                        rm_cl_name = get_testcase_name(log.split("/")[0].lower(),all_cluster_list)
                        tcname = cleaned_testcase_name(rm_cl_name)
                        if compare_similarity_of_string(cleaned_xml_testcase_name, tcname) == 100:
                            tc_log_url = 'https://'+settings.PLUTOURL+'/cohesityShare/watchmen_logs/'+watchmenfolder+'/'+actual_suite_folder+'/'+log
                    if 'failure' in xmltag:
                        suite_tc_executed_count[suitename]["failed"] += 1
                        failure_msg = re.sub(r'^/home.*\n?', '', xmltag['failure']['#text'], flags=re.MULTILINE)
                        cleaned_failure_msg = cleanup_text(failure_msg)
                        for signature in unique_signature:
                            err_sig_pattern = signature['signature'].replace("*", "[a-zA-Z]+")
                            if re.search(rf"\b{err_sig_pattern}\b", cleaned_failure_msg):
                                try:
                                    solution = OptimalSolution.objects.get(
                                        cleaned_error_msg=cleaned_failure_msg)
                                    if solution.err_signature.common_solution_flag:
                                        optimal_solution = solution.err_signature.common_solution
                                    elif solution.optimal_solution != "":
                                        optimal_solution = solution.optimal_solution
                                    else:
                                        optimal_solution = "No Optimal Solution So far!"
                                    train_data[solution.err_signature.readable_sig.rstrip()].append(
                                        {"suitename": xmltag['@classname'],
                                         "suitecolorcode": suite_color_code,
                                         "suiteperc":suite_pass_percentage,
                                         "squadname":suite_squad_name,
                                         "testcasename": xmltag['@name'],
                                         "cleanederrormsg":cleaned_failure_msg,
                                         "rawerrormsg": failure_msg,
                                         "optimalsolution": optimal_solution,
                                         "status": "failure",
                                         "cleanerrsig": solution.err_signature.signature.rstrip(),
                                         "logurl": tc_log_url})
                                    break
                                except OptimalSolution.DoesNotExist:
                                    err_sig_obj = ErrorSignature.objects.get(signature=signature['signature'])
                                    create_signature = OptimalSolution.objects.create(
                                        cleaned_error_msg=cleaned_failure_msg,
                                        err_signature = err_sig_obj)
                                    if err_sig_obj.common_solution != "":
                                        optimal_solution = err_sig_obj.common_solution
                                    else:
                                        optimal_solution = "No Optimal Solution So far!"
                                    train_data[create_signature.err_signature.readable_sig.rstrip()].append(
                                        {"suitename": xmltag['@classname'],
                                         "suitecolorcode": suite_color_code,
                                         "suiteperc": suite_pass_percentage,
                                         "squadname": suite_squad_name,
                                         "testcasename": xmltag['@name'],
                                         "cleanederrormsg": cleaned_failure_msg,
                                         "rawerrormsg": failure_msg,
                                         "optimalsolution": optimal_solution,
                                         "cleanerrsig": create_signature.err_signature.signature.rstrip(),
                                         "status":"failure", "logurl": tc_log_url})
                                    break
                        else:
                            train_data["UnknownErrSig"].append(
                                {"suitename": xmltag['@classname'],
                                 "suitecolorcode": suite_color_code,
                                 "suiteperc": suite_pass_percentage,
                                 "squadname": suite_squad_name,
                                 "testcasename": xmltag['@name'],
                                 "cleanederrormsg": cleaned_failure_msg,
                                 "rawerrormsg": failure_msg,
                                 "optimalsolution": "No Optimal Solution So far!",
                                 "cleanerrsig": "UnknownErrSig",
                                 "status": "failure", "logurl": tc_log_url})
                    elif 'skipped' in xmltag:
                        suite_tc_executed_count[suitename]["skipped"] += 1
                        train_data["Skipped"].append({"suitename": xmltag['@classname'],
                                                      "suitecolorcode": suite_color_code,
                                                      "suiteperc": suite_pass_percentage,
                                                      "squadname": suite_squad_name,
                                                      "testcasename": xmltag['@name'],
                                                 "status": "skipped"})
                    else:
                        suite_tc_executed_count[suitename]["passed"] += 1
                        train_data["PassedTc"].append({"suitename": xmltag['@classname'],
                                                       "suitecolorcode": suite_color_code,
                                                       "suiteperc": suite_pass_percentage,
                                                       "squadname": suite_squad_name,
                                                       "testcasename": xmltag['@name'],
                                                 "status": "passed", "logurl":tc_log_url})
            if request.session.get("errormsgdata"):
                del request.session["errormsgdata"]
            request.session["errormsgdata"] = train_data
            final_list = list()
            unique_suite_impacted = set()
            total_tc_perc = 0.0
            total_failures = 0
            if category == 'error':
                for err_sig, tdata in train_data.items():
                    if err_sig != "PassedTc" and err_sig != "Skipped":
                        failure_count = list(filter(lambda f: f['status'] == "failure", tdata))
                        suite_impacted = set(suite_name['suitename'] for suite_name in failure_count)
                        unique_suite_impacted.update(suite_impacted)
                        testcase_impact = round((len(failure_count)/total_tc_count_in_train) * 100, 2)
                        total_tc_perc += testcase_impact
                        total_failures += len(failure_count)
                        final_list.append({"error_sig": err_sig,
                                           "suite_impact": len(suite_impacted),
                                           "testcase_impact": testcase_impact,
                                           "failure_count": len(failure_count)}
                                          )
                sorted_final_list = sorted(final_list, key=itemgetter('failure_count'), reverse=True)
                return JsonResponse({"errordata": sorted_final_list,"total_impacted_suite":len(unique_suite_impacted),
                                     "total_tc_perc":round(total_tc_perc,2), "total_failure_count":total_failures,
                                     "total_suite_count":len(train_junit_paths)})
            elif category == 'suite':
                for suitename, data in suite_tc_executed_count.items():
                    if int(data["failed"]) > int(total_tc_count_in_train):
                        suite_tc_imp = round((total_tc_count_in_train / int(data["failed"])) * 100, 2)
                    elif int(data["failed"]) < int(total_tc_count_in_train):
                        suite_tc_imp = round((int(data["failed"]) / total_tc_count_in_train) * 100, 2)
                    else:
                        suite_tc_imp = 0.00
                    if int(total_executed_tc_count_in_suite[suitename]) > int(total_tc_count_in_suite[suitename]):
                        coverage_imp = round(100-(round(int(total_tc_count_in_suite[suitename]) / int(
                            total_executed_tc_count_in_suite[suitename]) * 100, 2)),2)
                    elif int(total_executed_tc_count_in_suite[suitename]) < int(total_tc_count_in_suite[suitename]):
                        coverage_imp = round(100-(round((int(total_executed_tc_count_in_suite[suitename]) / int(
                            total_tc_count_in_suite[suitename])) * 100, 2)),2)
                    else:
                        coverage_imp = 0.00
                    final_list.append(
                        {"suite": suitename, "testcase_impact": suite_tc_imp, "skipped": data["skipped"],
                         "coverage_impact": coverage_imp, "passed": data["passed"], "failure_count": data["failed"],
                         "pass_perc":data['percentage'], "squad":data['squad'], "ccode":data['color_code']})
                sorted_final_list = sorted(final_list, key=itemgetter('failure_count'), reverse=True)
                return JsonResponse({"suitedata": sorted_final_list})

#
# def run_command(ssh_client, command):
#     stdin, stdout, stderr = ssh_client.exec_command(command)
#     output = stdout.read().decode('utf-8')
#     error = stderr.read().decode('utf-8')
#     return command, output, error
#
# def pluto_server_command_execute_function(commands):
#     ssh_client_for_log = paramiko.client.SSHClient()
#     ssh_client_for_log.set_missing_host_key_policy(paramiko.AutoAddPolicy())
#     ssh_client_for_log.connect(settings.PLUTOURL, username=settings.PLUTOUSERNAME, password=settings.PLUTOPASSWORD)
#     with ThreadPoolExecutor(max_workers=20) as executor:
#         futures = {executor.submit(run_command, ssh_client_for_log, command): command for command in commands}
#
#         for future in as_completed(futures):
#             command = futures[future]
#             try:
#                 command, output, error = future.result()
#                 print(f"Output of '{command}':")
#                 print(output)
#                 if error:
#                     print(f"Error for '{command}': {error}")
#             except Exception as e:
#                 print(f"Error executing '{command}': {e}")
#     ssh_client_for_log.close()
#

async def train_severe_analyze_function(folderpath):
    ssh_client_for_log = paramiko.client.SSHClient()
    ssh_client_for_log.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh_client_for_log.connect(settings.PLUTOURL, username=settings.PLUTOUSERNAME, password=settings.PLUTOPASSWORD)
    start_time = time.time()

    # #
    # commands = ["ls /home/cohesity/data/cohesityShare/watchmen_logs/" + path + "/workflow_logs/*.severe" for path in folderpath]
    # await asyncio.sleep(1)
    # result = await asyncio.to_thread(pluto_server_command_execute_function, commands)
    # # async with asyncssh.connect(settings.PLUTOURL, username=settings.PLUTOUSERNAME,
    # #                             password=settings.PLUTOPASSWORD) as conn:
    # #     semaphore = asyncio.Semaphore(15)
    # #     results = await asyncio.gather(*[pluto_server_command_execute_function(conn, command,semaphore) for command in commands])
    # #     for command, result in zip(commands, results):
    # #         print(f"Output of '{command}':")
    # #         print(result)
    # #
    # print(">>>>>>>>>>>>>>>>>><<<<<", time.time() - start_time)

    severe_log_path = []
    for path in folderpath:
        train_root_folder = "/home/cohesity/data/cohesityShare/watchmen_logs/" + path + "/workflow_logs/"
        # list_of_severe_log_cmd = "cd " + train_root_folder + ";ls -l | grep ^d | awk '{split($9,fname,\"-\"); print fname[1]}'| xargs -I {} sh -c 'ls {}*/workflow_logs/*.severe'"
        list_of_severe_log_cmd = "ls " + train_root_folder + "*.severe"
        # print(list_of_severe_log_cmd)
        _stdin, _stdout, _stderr = ssh_client_for_log.exec_command(list_of_severe_log_cmd)
        testcases_log_list = _stdout.read().decode().splitlines()
        modified_test_log = []
        temp = ''
        for i in testcases_log_list:
            if i.endswith(".severe") and temp == "":
                modified_test_log.append(i)
            elif i.endswith(".severe") and temp != "":
                temp = temp + i
                modified_test_log.append(temp)
                temp = ""
            else:
                temp = temp+i
        testcases_log_list = ["https://sv4-pluto.eng.cohesity.com/cohesityShare/watchmen_logs/"+file.split("watchmen_logs/")[1] for file in modified_test_log]
        severe_log_path.extend(testcases_log_list)
    ssh_client_for_log.close()
    # print(severe_log_path)
    severe_results = await up(
        severe_log_path, method="GET", response_fn=lambda x: x.text, raise_for_status=False, timeout=600, progress=True
    )
    severe_data = defaultdict(list)
    for filepath, content in zip(severe_log_path,severe_results):
        split_path = filepath.split('/')
        suitename = re.sub(r"-[0-9]{4}-[0-9]{2}-[0-9]{2}-[0-9]{2}-[0-9]{2}-[0-9]{2}-[a-z]+","",split_path[6])
        testcase_name = re.sub(r"-[0-9]+\.severe","",split_path[8])

        splited_content = content.split('\n')
        for cnt in splited_content:
            if cnt != "Console Log Level: SEVERE" and cnt != "":
                unique_name_for_error = clean_severe_content(cnt)
                severe_data[unique_name_for_error].append((suitename,testcase_name,cnt,unique_name_for_error,filepath))
    # os.remove("severe_data.json")
    # with open('severe_data.json', 'w') as file:
    #     json.dump(severe_data, file, indent=4,)
    return severe_data


async def train_analyze_result_core_function(branch,trainname,build,squad,severe,suite_tag):
    """
    1. Fetch the watchmen log folder based on given input.
    2. Collecting the Junit file in train folder
    3. Collecting logfile for each testcase in each test suite.
    4. Iteration junit file and calculating the passed, failed, skipped data.
    5. Return the analyzed data
    """
    reports_base = "https://reports.eng.cohesity.com/api/v1/"
    common_headers = {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
    }
    all_suite_list_url = (reports_base+"e2etestsuitereport?branch="+branch+
                          "&build="+build+"&train="+trainname+
                          "&report_type=testcase&os=all&tag=All")
    try:
        all_suite_response = requests.get(url=all_suite_list_url, headers=common_headers)
        if all_suite_response.status_code == 200:  # Check if the response is OK (status 200)
            if all_suite_response.content:  # Check if the content is not empty
                try:
                    all_suite_json_data = json.loads(all_suite_response.content)  # Attempt to parse the JSON
                except json.decoder.JSONDecodeError as e:
                    print(f"JSONDecodeError: {e}")
                    print("Response content:", all_suite_response.content)
                    return 'Invalid JSON response'
            else:
                print("Error: Empty response body")
                return 'Empty body'
        else:
            print(f"Error: HTTP status {all_suite_response.status_code}")
            return f"HTTP Error: {all_suite_response.status_code}"

    except requests.exceptions.ConnectionError as conn_err:
        print(conn_err)
    except requests.exceptions.RetryError as retry_err:
        print(retry_err)
    if len(all_suite_json_data.get('body')) == 0:
        return 'emptybody'

    if squad != 'all':
        all_suite_json_data['body'][:] = [squad_suite for squad_suite in all_suite_json_data['body'] if squad_suite['squad'] == squad]
    if suite_tag != 'all':
        @sync_to_async
        def fetch_suites_by_tag():
            return list(TagMapping.objects.filter(tag_name__name=suite_tag,train_name=trainname).values_list('suite_name', flat=True))
        suites_by_tag = await fetch_suites_by_tag()
        all_suite_json_data['body'][:] = [squad_suite for squad_suite in all_suite_json_data['body'] if squad_suite['suite_name'] in suites_by_tag]
    suites_data = {}
    suites_folder = []
    for suite in all_suite_json_data['body']:
        suites_data[suite['suite_name']] = suite
        train_root_folder = suite['suite_log_url'].split("watchmen_logs/")[1]
        if train_root_folder not in suites_folder:
            suites_folder.append(train_root_folder)
    if len(suites_folder) and severe:
        severe_data = await train_severe_analyze_function(suites_folder)
        all_suite_json_data['severe_data'] = severe_data
        # pprint.pp(severe_data)

    suite_urls = [x['suite_log_url']+"/" for x in all_suite_json_data['body']]
    suite_results = await up(
        suite_urls, method="GET", response_fn=lambda x: x.text, raise_for_status=False, timeout=600, progress=True
    )

    for name, url, content in zip(suites_data.keys(),suite_urls, suite_results):
        suitename = name
        suites_data[suitename]['suite_page_content'] = content
    # pprint.pprint(suites_data)

    running_suite = []
    for suitename, data in suites_data.items():
        # print(suitename)
        # print(data['suite_log_url'])
        suite_op_res = data['suite_page_content']
        junit_dir_pattern = r""+suitename+"[-A-Z0-9a-z]+\/"
        junit_dir_matchs = re.findall(junit_dir_pattern, suite_op_res)
        if len(junit_dir_matchs) == 0:
            running_suite.append(suitename)
            continue
        data["junit_url"] = data['suite_log_url']+"/"+junit_dir_matchs[0]+"jUnit.xml"
        soup = BeautifulSoup(suite_op_res, 'html.parser')
        name_only = {}
        for link in soup.find_all('a'):
            if (link.contents[0] == "Name" or link.contents[0] == "Last modified" or link.contents[0] == "Size" or
                link.contents[0] == "Description" or link.contents[0] == "Parent Directory"):
                continue
            tc_name = re.sub(r"[_#]{2}TR[:Cc0-9,\s]+(TR[_#]{2})?", "", link.contents[0])
            tc_name = re.sub(r"^[\d]+_","",tc_name.replace("/",""))
            tc_name = tc_name.replace(" ", "_")
            name_only[tc_name] = link.contents[0]
        # pathof_tc = list(map(lambda x: re.sub(r"[_#]{2}TR[:Cc0-9,\s]+(TR[_#]{2})?", "", x.contents[0]),soup.find_all('a')[4:]))
        # data['tc_name_only']  = {re.sub(r"^[\d]+_","",p.replace("/","")): p for p in pathof_tc}
        data['tc_name_only'] = name_only
        del data['suite_page_content']

    if len(running_suite) > 0:
        for suite in running_suite:
            del suites_data[suite]
    #     # print(suite['tc_name_only'])
    # # pprint.pp(suites_data)
    all_tc_list_url = []
    for suite in suites_data.keys():
        all_tc_list_url.append(reports_base+"e2etestcaselevelreport?branch="+branch+
                          "&build="+build+"&train="+trainname+"&suite="+suite+
                          "&os=all")
    testcase_status = await up(all_tc_list_url, method="HEAD", response_fn=lambda x: x.status_code, progress=True)
    failed_suite = []
    for i in testcase_status:
        if isinstance(i,RequestError):
            failed_suite.append(i.url.split('suite=')[1].split('&')[0])

    tc_results = await up(
        all_tc_list_url, method="GET", headers=common_headers, raise_for_status=False, timeout=600, progress=True
    )

    for suitename, url, content in zip(suites_data.keys(),all_tc_list_url, tc_results):
        if suitename not in failed_suite:
            suites_data[suitename]['testcase_results'] = content['body']['testcase_results']

    for suite in failed_suite:
        # print(suites_data[suite].get("junit_url"))
        if suites_data[suite].get("junit_url") is None:
            continue
        e_junit_res = requests.head(suites_data[suite].get("junit_url"))
        if e_junit_res.status_code == 200:
            try:
                e_read_junit_file = urlopen(suites_data[suite]["junit_url"])
                e_junit_data = e_read_junit_file.read()
                e_read_junit_file.flush()
                e_read_junit_file.close()
            except urllib.request.HTTPError as err:
                print(f'An HTTP error occurred: {err}')
                continue
            e_junit_dict = xmltodict.parse(e_junit_data)

            if e_junit_dict['testsuite'].get('testcase') is None:
                continue
            if type(e_junit_dict['testsuite']['testcase']) is str or type(e_junit_dict['testsuite']['testcase']) is dict:
                e_junit_dict['testsuite']['testcase'] = [e_junit_dict['testsuite']['testcase']]
            testcase_result = []
            for exmltag in e_junit_dict['testsuite']['testcase']:
                tc_data = {}
                tc_data['test_name'] = exmltag['@name']
                if "failure" in exmltag:
                    tc_data['status'] = "Failed"
                elif "skipped" in exmltag:
                    tc_data['status'] = "Skipped"
                else:
                    tc_data['status'] = "Passed"
                testcase_result.append(tc_data)
            suites_data[suite]['testcase_results'] = testcase_result
        else:
            del suites_data[suite]
            # print(suites_data[suite]['testcase_results'])
    # pprint.pprint(suites_data)
    matching_log_task = [matching_logs(suite,results) for suite,results in suites_data.items()]
    matching_error_task = [mapping_errors(suite, results) for suite, results in suites_data.items()]
    await asyncio.gather(*matching_log_task)
    await asyncio.gather(*matching_error_task)
    return all_suite_json_data

def train_analyze_result_v2(request):
    """
    1. Fetch the watchmen log folder based on given input.
    2. Collecting the Junit file in train folder
    3. Collecting logfile for each testcase in each test suite.
    4. Iteration junit file and calculating the passed, failed, skipped data.
    5. Return the analyzed data
    """
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    if is_ajax:
        if request.method == 'POST':
            request_data = json.load(request)
            branch = request_data.get("branch")
            trainname = request_data.get("trainname")
            build = request_data.get("build")
            category = request_data.get("category")
            squad = request_data.get("squad")
            severe = request_data.get("severe")
            suite_tag = request_data.get("tag")
            all_suite_json_data = asyncio.run(train_analyze_result_core_function(branch,trainname,build,squad,severe,
                                                                                 suite_tag))
            if all_suite_json_data == "emptybody":
                return HttpResponseNotFound(trainname + " analysis result is not avaialble for " + build + " build!")
            return finalize_v2_session_and_json(
                request, all_suite_json_data, branch, trainname, build, category, severe
            )


def analyze_watchmen_url_v2(request):
    """
    Analyze failures by crawling a watchmen_logs share URL (HTTP directory + jUnit),
    without reports API / django-cron train sync.
    """
    is_ajax = request.headers.get("X-Requested-With") == "XMLHttpRequest"
    if not is_ajax or request.method != "POST":
        return HttpResponseNotFound("Invalid request")
    request_data = json.load(request)
    watchmen_url = (request_data.get("watchmen_log_url") or "").strip()
    branch = request_data.get("branch") or "local"
    trainname = request_data.get("trainname") or "magneto_dmaas_vmware_train"
    build = request_data.get("build") or "watchmen-direct"
    category = request_data.get("category") or "error"
    severe = bool(request_data.get("severe"))
    if not watchmen_url:
        return HttpResponseNotFound("watchmen_log_url is required")
    squad_by: dict = {}
    db = get_mongo_database()
    squad_query: dict = {}
    if trainname:
        squad_query["train_name"] = trainname
    if branch and branch != "local":
        squad_query["branch"] = branch
    for doc in db["restapi_squaddetails"].find(squad_query):
        sn, sq = doc.get("suite_name"), doc.get("suite_squad")
        if sn and sq:
            squad_by[sn] = sq
    try:
        all_suite_json_data = build_suites_from_watchmen_url(watchmen_url, squad_by)
    except Exception as exc:
        return HttpResponseNotFound("Failed to read watchmen URL: " + str(exc))
    if not all_suite_json_data.get("body"):
        return HttpResponseNotFound("No suite / jUnit.xml found under this watchmen URL.")
    return finalize_v2_session_and_json(
        request, all_suite_json_data, branch, trainname, build, category, severe
    )


def error_basis_triage(request):
    """
    This function will process by session data.
    """
    if request.method != "POST":
        return render(request, "error.html", {"errormsg": "DirectAccessRestrict"})
    if request.POST.get("error_signature") is None or request.session['errormsgdata'] is None:
        return render(request, "error.html", {"errormsg": "SomeThingWrong."})
    error_signature = request.POST.get("error_signature")
    error_details = request.session['errormsgdata'][error_signature]
    common_optimal_solution = list()
    grouping_errordata = defaultdict(list)
    for errors in error_details:
        if errors["status"] != "passed" and errors["status"] != "skipped":
            common_optimal_solution.append(errors['optimalsolution'])
            grouping_errordata[errors['suitename']].append(errors)
    grouping_errordata.default_factory = None
    sorted_group_data = OrderedDict(sorted(grouping_errordata.items(), key= lambda x: x[1][0]['suiteperc'], reverse=False))
    finaldata = {'error_msg': error_signature, 'optimal_solution': set(common_optimal_solution),
                 'error_details':sorted_group_data}
    # print(finaldata)
    return render(request, "triage_v3.html", {"data": finaldata})

def error_basis_triage_v2(request):
    """
    This function will process by session data.
    """
    if request.method != "POST":
        return render(request, "error.html", {"errormsg": "DirectAccessRestrict"})
    if request.POST.get("error_signature") is None or request.session['errormsgdata'] is None:
        return render(request, "error.html", {"errormsg": "SomeThingWrong."})
    error_signature = request.POST.get("error_signature")
    error_details = request.session['errormsgdata'][error_signature]
    common_optimal_solution = list()
    grouping_errordata = defaultdict(list)
    for errors in error_details:
        if errors["status"] != "passed" and errors["status"] != "skipped":
            if errors['optimalsolution'] is not None and errors['optimalsolution'] != "":
                common_optimal_solution.append(errors['optimalsolution'])
            grouping_errordata[errors['suitename']].append(errors)
    grouping_errordata.default_factory = None
    sorted_group_data = OrderedDict(sorted(grouping_errordata.items(), key= lambda x: x[1][0]['suiteperc'], reverse=False))
    print("Optimal Solutions:", list(set(common_optimal_solution)))
    finaldata = {'error_msg': error_signature, 'optimal_solution': list(set(common_optimal_solution)),
                 'error_details':sorted_group_data}
    # print(finaldata)
    # print(finaldata)
    return render(request, "v2/error_triage.html", {"data": finaldata})

def submit_optimal_solution(request):
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    if is_ajax:
        if request.method == 'POST':
            request_data = json.load(request)
            err_sig_obj = ErrorSignature.objects.get(signature=request_data.get("cleaned_err_sig"))
            if request_data.get("common_solution"):
                err_sig_obj.common_solution = request_data.get('optimal_solution')
                err_sig_obj.common_solution_flag = True
                err_sig_obj.save()
            else:
                solution = OptimalSolution.objects.get(cleaned_error_msg=request_data.get("cleaned_err_msg"))
                solution.optimal_solution = request_data.get('optimal_solution')
                solution.err_signature = err_sig_obj
                solution.err_category = request_data.get('category')
                solution.email_address = request_data.get('email_addr')
                solution.save()
            return JsonResponse({"success": "updated"})

def submit_search_engine_error(request):
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    if is_ajax:
        if request.method == 'POST':
            request_data = json.load(request)
            error_input = request_data.get('error_input')
            error_msg = re.sub(r'^/home.*\n?', '', error_input, flags=re.MULTILINE)
            cleaned_failure_msg = cleanup_text(error_msg)
            error_signature = ErrorSignature.objects.values('signature','readable_sig')
            unique_signature = [dict(uniq_sig) for uniq_sig in {tuple(sig.items()) for sig in error_signature}]
            optimal_solution = ""
            solutions = []
            unique_solution = []
            for signature in unique_signature:
                if signature['readable_sig'].lower() == error_input.lower():
                    results = ErrorSignature.objects.filter(readable_sig=signature['readable_sig'])
                    for result in results:
                        if result.common_solution_flag:
                            solutions.append(result.common_solution)
                        unique_solution = list(set(solutions))
                    if len(unique_solution) > 1:
                        for solution in range (0,len(solutions)):
                            optimal_solution = optimal_solution + " " + "Solution" + str(solution+1) + ": " + unique_solution[solution]
                    else:
                        optimal_solution = "Solution: " + unique_solution[0]
                    break
                else:
                    if signature['signature'] in cleaned_failure_msg:
                        try:
                            result = OptimalSolution.objects.get(cleaned_error_msg=cleaned_failure_msg)
                            if result.optimal_solution is not None:
                                optimal_solution = result.optimal_solution
                        except ObjectDoesNotExist:
                            optimal_solution = "No Optimal Solution So far!"

            if optimal_solution == "":
                optimal_solution = "No Optimal Solution So far!"
            return JsonResponse({"solution": optimal_solution})


def suite_basis_triage(request):
    """
    This function will process by session data.
    """
    if request.method != "POST":
        return render(request, "error.html", {"errormsg": "DirectAccessRestrict"})
    if request.POST.get("suite_name") is None or request.session['errormsgdata'] is None:
        return render(request, "error.html", {"errormsg": "SomeThingWrong."})
    suitename = request.POST.get("suite_name")
    error_details = request.session['errormsgdata']
    suite_error_data = []
    errsig = ""
    for signature,errors in error_details.items():
        if signature != "PassedTc" and signature != "Skipped":
            suites_data = list(filter(lambda f: f['status'] == "failure" and f['suitename'] == suitename, errors))
            errsig = signature
            suite_error_data.extend(suites_data)
    # pprint.pprint(suite_error_data)
    return render(request, "suite_triage.html", {"errordata": suite_error_data,
                                                 "suitename":suitename, "signature":errsig})

def suite_basis_triage_v2(request):
    """
    This function will process by session data.
    """
    if request.method != "POST":
        return render(request, "error.html", {"errormsg": "DirectAccessRestrict"})
    if request.POST.get("suite_name") is None or request.session['errormsgdata'] is None:
        return render(request, "error.html", {"errormsg": "SomeThingWrong."})
    suitename = request.POST.get("suite_name")
    error_details = request.session['errormsgdata']
    suite_error_data = []
    errsig = ""
    for signature,errors in error_details.items():
        if signature != "PassedTc" and signature != "Skipped":
            suites_data = list(filter(lambda f: f['status'] == "failure" and f['suitename'] == suitename, errors))
            errsig = signature
            suite_error_data.extend(suites_data)
    # pprint.pprint(suite_error_data)
    return render(request, "v2/suite_triage.html", {"errordata": suite_error_data,
                                                 "suitename":suitename, "signature":errsig})


def severe_basis_triage(request):
    if request.method != "POST":
        return render(request, "error.html", {"errormsg": "DirectAccessRestrict"})
    if request.POST.get("severeerrorsig") is None or request.session['severelogdata'] is None:
        return render(request, "error.html", {"errormsg": "SomeThingWrong."})
    severe_err_type = request.POST.get("severeerrorsig")
    severe_sig_data = request.session['severelogdata']['scat']
    severe_details = request.session['severelogdata']['sdata']
    severe_signatures = severe_sig_data[severe_err_type]
    if len(severe_signatures) > 0:
        severe_data = []
        for sig in severe_signatures:
            error_log_info = {}
            details = severe_details[sig]
            unique_suite_name = { s[0] for s in details }
            unique_tc = { t[1] for t in details }
            occurence = len(details)
            for info in details:
                if error_log_info.get(info[0]):
                    error_log_info[info[0]].update({info[1]:info[4]})
                else:
                    error_log_info[info[0]] = {info[1]:info[4]}
            severe_data.append({"error_msg": details[0][2],"suite":len(unique_suite_name),"testcase":len(unique_tc),
                                "occurence":occurence,"signature":sig,"err_type":severe_err_type,
                                "err_log":error_log_info})
            # pprint.pprint(error_log_info)
        sorted_severe_data = sorted(severe_data, key=itemgetter('occurence'), reverse=True)
    return render(request, "severe_log_triage.html",{"severe_data": sorted_severe_data})

def severe_basis_triage_v2(request):
    if request.method != "POST":
        return render(request, "error.html", {"errormsg": "DirectAccessRestrict"})
    if request.POST.get("severeerrorsig") is None or request.session['severelogdata'] is None:
        return render(request, "error.html", {"errormsg": "SomeThingWrong."})
    severe_err_type = request.POST.get("severeerrorsig")
    severe_sig_data = request.session['severelogdata']['scat']
    severe_details = request.session['severelogdata']['sdata']
    severe_signatures = severe_sig_data[severe_err_type]
    if len(severe_signatures) > 0:
        severe_data = []
        total_occurence = 0
        total_testcases = 0
        total_suites = 0
        for sig in severe_signatures:
            error_log_info = {}
            details = severe_details[sig]
            unique_suite_name = { s[0] for s in details }
            unique_tc = { t[1] for t in details }
            occurence = len(details)
            for info in details:
                if error_log_info.get(info[0]):
                    error_log_info[info[0]].update({info[1]:info[4]})
                else:
                    error_log_info[info[0]] = {info[1]:info[4]}
            total_occurence += occurence
            total_suites += len(unique_suite_name)
            total_testcases += len(unique_tc)
            severe_data.append({"error_msg": details[0][2],"suite":len(unique_suite_name),"testcase":len(unique_tc),
                                "occurence":occurence,"signature":sig,"err_type":severe_err_type,
                                "err_log":error_log_info})
            # pprint.pprint(error_log_info)
        sorted_severe_data = sorted(severe_data, key=itemgetter('occurence'), reverse=True)
    return render(request, "v2/severe_log_triage.html",{"severe_data": sorted_severe_data,
                    "total_occurence":total_occurence, "total_suites":total_suites,"total_testcases":total_testcases })


def submit_severe_solution(request):
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    if is_ajax:
        if request.method == 'POST':
            request_data = json.load(request)
            err_msg = request_data.get('cleaned_err_sig')
            err_cat = request_data.get('err_category')
            if err_cat == "buggy":
                bug_id = request_data.get('bug_id')
                SevereDetail.objects.filter(cleaned_error=err_msg).update(error_category=err_cat,bug_id=bug_id)
            elif err_cat == "expected" or err_cat == "need_analysis":
                comments = request_data.get('comments')
                SevereDetail.objects.filter(cleaned_error=err_msg).update(error_category=err_cat, comments=comments)
            return JsonResponse({"success": "updated"})