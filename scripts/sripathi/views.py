from django.shortcuts import render
from django.http import JsonResponse, HttpResponseBadRequest, HttpResponseNotFound, HttpResponse
from autotriage.common_utils import retry_session
from restapi.models import Trainlogdata, AllBranch
from django.conf import settings
import paramiko, requests, json, re, os, datetime
import xml.etree.ElementTree as ET
from collections import defaultdict
import base64
import urllib.request
from autotriage.common_utils import urlopen_with_retry
import xmltodict

# Create your views here.
def traindata(request):
    """
    Home page dropdown datas
    """
    startdate = datetime.datetime.today() - datetime.timedelta(days=30)
    formated_start_date = startdate.strftime("%Y%m%d")
    sfsd = str(formated_start_date)
    enddate = datetime.datetime.today()
    formated_end_date = enddate.strftime("%Y%m%d")
    sfed = str(formated_end_date)
    alltrains = Trainlogdata.objects.filter(date__range=[sfsd,sfed]).order_by('-date').values()
    unique_branch = []
    for train in alltrains:
        build = train['build'].split("-")[0].split("_")[0]
        if build not in unique_branch:
            unique_branch.append(build)
    return render(request, "index.html", {"branchs":unique_branch})


def trainname_by_branch(request,branch):
    """
    This function helps to filter train names by the branch for home page dropdown.
    """
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    if is_ajax:
        if request.method == 'GET':
            alltrains = Trainlogdata.objects.filter(build__startswith=branch).order_by('-date')
            list_of_train = []
            for tn in alltrains:
                if tn.trainname not in list_of_train:
                    list_of_train.append(tn.trainname)
            return JsonResponse(list_of_train,safe=False)


def build_by_branch_train(request,branch,train_name):
    """
    This function helps to filter train names by the branch and trainname for home page dropdown.
    """
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    if is_ajax:
        if request.method == 'GET':
            builds = Trainlogdata.objects.filter(build__startswith=branch,trainname=train_name).order_by('-date')
            list_of_builds = []
            for build in builds:
                if build.build not in list_of_builds:
                    list_of_builds.append(build.build)
            return JsonResponse(list_of_builds,safe=False)


def faliuredata(request, watchmenfolder):
    folder = "/home/cohesity/data/cohesityShare/watchmen_logs/" + watchmenfolder
    cmd = "ls " + folder
    client = paramiko.client.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(settings.PLUTOURL, username=settings.PLUTOUSERNAME, password=settings.PLUTOPASSWORD)
    _stdin, _stdout, _stderr = client.exec_command(cmd)
    print("CMD:",cmd)
    suitelist = _stdout.read().decode().splitlines()
    if len(suitelist) > 0:
        suite_dict = {}
        for val in suitelist:
            suitename = val.split('-')[0]
            cmd1 = cmd + '/' + val
            _stdin, _stdout, _stderr = client.exec_command(cmd1 + '\n' "ls" '\n')
            sub_link_list = _stdout.read().decode().splitlines()
            for sub_list in sub_link_list:
                if sub_list.split('-')[0] == suitename:
                    suite_dict[val] = sub_list
    else:
        return render(request, "error.html", {"folder": watchmenfolder})

    url_list = {}
    for i, j in suite_dict.items():
        url_updated = ("https://" + settings.PLUTOURL + "/cohesityShare/watchmen_logs/" +
                       watchmenfolder + "/" + i + "/" + j + "/" + "jUnit.xml")
        url_list[i.split('-')[0]] = url_updated
    client.close()

    # paring xml file
    failures = {}
    suitesofnojunit = []
    for suitename, url in url_list.items():
        resp = requests.get(url)
        if resp.status_code == 200:
            with open('temptrain.xml', 'wb') as f:
                f.write(resp.content)
            tree = ET.parse('temptrain.xml')

            suite = tree.getroot()
            for tcname in suite:
                for failure in tcname:
                    if failure.tag == "failure":
                        # print("tcname: ", tcname.attrib['name'])
                        # print("Error: ", failure.text)
                        failures[suitename + "###" + tcname.attrib['name']] = failure.text
        else:
            suitesofnojunit.append(suitename)
    if len(failures) > 0:
        return render(request, "triage.html", {"failures": failures,"nojunit":suitesofnojunit})
    else:
        return render(request, "error.html", {"nofailure": True})


def train_analyze_result(request):
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    if is_ajax:
        if request.method == 'POST':
            data = json.load(request)
            trainname = data.get("trainname")
            build = data.get("build")
            category = data.get("category")
            logdata = Trainlogdata.objects.get(build=build, trainname=trainname)
            print(logdata.logurl)
            watchmenfolder = logdata.logurl.split("/")[-1]
            folder = "/home/cohesity/data/cohesityShare/watchmen_logs/" + watchmenfolder
            cmd = "ls " + folder
            client = paramiko.client.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            client.connect(settings.PLUTOURL, username=settings.PLUTOUSERNAME, password=settings.PLUTOPASSWORD)
            _stdin, _stdout, _stderr = client.exec_command(cmd)
            suitelist = _stdout.read().decode().splitlines()
            print(suitelist)
            if len(suitelist) > 0:
                suite_dict = {}
                for val in suitelist:
                    suitename = val.split('-')[0]
                    cmd1 = cmd + '/' + val
                    _stdin, _stdout, _stderr = client.exec_command(cmd1 + '\n' "ls" '\n')
                    sub_link_list = _stdout.read().decode().splitlines()
                    for sub_list in sub_link_list:
                        if sub_list.split('-')[0] == suitename:
                            suite_dict[val] = sub_list
            else:
                return HttpResponseNotFound(trainname+" analysis result is not avaialble for "+build+" build!")

            suite_junit_list = {}
            for i, j in suite_dict.items():
                url_updated = ("https://" + settings.PLUTOURL + "/cohesityShare/watchmen_logs/" +
                               watchmenfolder + "/" + i + "/" + j + "/" + "jUnit.xml")
                suite_junit_list[i.split('-')[0]] = url_updated
            client.close()
            failures={}
            failure_count = {}
            total_count = {}
            suite_impact = {}
            testcase_impact = {}
            error_count = {}
            error_impact = {}
            coverage_impact = {}
            coverage_count = defaultdict(list)
            coverage_total_count = {}
            total = 0
            suite_error_count = defaultdict(list)
            suite_impact_count = {}
            final_list = []
            junit_url_info = defaultdict(list)

            for suitename, junit_url in suite_junit_list.items():
                resp = requests.get(junit_url)
                if resp.status_code == 200:
                    if os.path.isfile("temptrain.xml"):
                        os.remove("temptrain.xml")
                    with open('temptrain.xml', 'wb') as f:
                        f.write(resp.content)
                    tree = ET.parse('temptrain.xml')
                    suite = tree.getroot()
                    total += int(suite.attrib['tests'])
                    for tcname in suite:
                        failure_count[suite.attrib['name']] = suite.attrib['failures']
                        total_count[suite.attrib['name']] = suite.attrib['tests']
                        coverage_count[suite.attrib['name']].append(tcname.attrib['name'])

                        for failure in tcname:
                            if failure.tag == "failure":
                                failure_info = re.sub(r'^/home.*\n?', '', failure.text, flags=re.MULTILINE)
                                failures[tcname.attrib['name']] = failure.text
                                suite_error_count[failure_info].append(suite.attrib['name'])
                                junit_bytes = junit_url.encode("ascii")

                                junit_base64_bytes = base64.b64encode(junit_bytes)
                                junit_encoded = junit_base64_bytes.decode("ascii")
                                junit_url_info[failure_info].append(junit_encoded)
                                if failure_info in error_count.keys():
                                    error_count[failure_info] += 1
                                else:
                                    error_count[failure_info] = 1
                else:
                    #todo: junit xml file is not present. Needs to handle this error too
                    print(suitename+" junit xml file is not present. Needs to handle this error too")
            # Calculating the failure testcase per train and suite wise.
            for key, value in failure_count.items():
                testcase_impact[key] = int(value) / total * 100
                suite_impact[key] = int(value) / int(total_count[key]) * 100
            for key, value in coverage_count.items():
                coverage_total_count[key] = len(value)
            for key, value in error_count.items():
                error_impact[key] = int(value) / total * 100
            # Calculating the error testcase per train
            for key, value in coverage_total_count.items():
                coverage_impact[key] = int(total_count[key]) / int(value) * 100
            for key, value in suite_error_count.items():
                suite_impact_count[key] = len(set(value))
            if category == 'error':
                for key, value in error_count.items():
                    junit_details = "#@#".join(junit_url_info[key])
                    error_bytes = key.encode("utf-8")

                    error_base64_bytes = base64.b64encode(error_bytes)
                    error_decrypt = error_base64_bytes.decode("utf-8")
                    final_list.append({"error": key, "suite_impact": suite_impact_count[key],
                                       "testcase_impact": round(error_impact[key], 2), "failure_count": error_count[key],
                                       "junit": junit_details,"error_decrypt":error_decrypt})
                return JsonResponse({"errordata": final_list})
            elif category == 'suite':
                for key, value in failure_count.items():
                    if int(value) != 0:
                        final_list.append(
                            {"suite": key, "suite_impact": 1, "testcase_impact": round(testcase_impact[key], 2),
                             "coverage_impact": (100 - round(coverage_impact[key], 2)), "failure_count": failure_count[key]})
                return JsonResponse({"suitedata": final_list})
        return JsonResponse(["test"],safe=False)
    else:
        return HttpResponseBadRequest('Invalid request')

def error_basis_triage(request):
    if request.method != "POST":
        return render(request, "error.html", {"errormsg": "DirectAccessRestrict"})
    if request.POST.get("error_message") is None or request.POST.get("resultdata") is None:
        return render(request, "error.html", {"errormsg": "SomeThingWrong"})
    junit_base_code = request.POST.get("resultdata")
    error_info = request.POST.get("error_message")
    error_info_string = error_info.encode("utf-8")
    error_info_bytes = base64.b64decode(error_info_string)
    errors = error_info_bytes.decode("utf-8")
    testdetailslist = []
    junit = junit_base_code.split("#@#")
    junit_decrypt = []
    for i in junit:
        junit_string = i.encode("ascii")
        junit_bytes = base64.b64decode(junit_string)
        junit_decrypt_string = junit_bytes.decode("ascii")
        if junit_decrypt_string not in junit_decrypt:
            junit_decrypt.append(junit_decrypt_string)
    for junit_info in junit_decrypt:
        failure_testcase = {}
        testcase_name = {}
        reference_dict = {}
        exact_failure_testcase = {}
        resp = requests.get(junit_info)
        # saving the xml file
        with open('junitfeed.xml', 'wb') as f:
            f.write(resp.content)
        tree = ET.parse('junitfeed.xml')
        suite = tree.getroot()
        for tcname in suite:
            for failure in tcname:
                if failure.tag == "failure":
                    failure_verify = re.sub(r'^/home.*\n?', '', failure.text, flags=re.MULTILINE)
                    # First drilling down with error logic
                    if errors.strip() == failure_verify.strip():
                        exact_failure_testcase[tcname.attrib['name']] = errors
                        folder_url = junit_info.split("/")
                        folder = "/home/cohesity/data/cohesityShare/watchmen_logs/"
                        # Getting the folder of testcase for suite
                        testcase_folder = folder + folder_url[-4] + "/" + folder_url[-3] + "/"
                        cmd = "cd " + testcase_folder
                        client = paramiko.client.SSHClient()
                        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                        client.connect(settings.PLUTOURL, username=settings.PLUTOUSERNAME,
                                       password=settings.PLUTOPASSWORD)
                        _stdin, _stdout, _stderr = client.exec_command(cmd + '\n' "ls" '\n')
                        testcaselist = _stdout.read().decode().splitlines()
                        failure_testcase[tcname.attrib['name']] = 1
                        # Removing the special characters and testrail id from failure testcase
                        testcase_strip = tcname.attrib['name'].strip()
                        testcase_testrail_fr_rm = testcase_strip.replace("##TR",'')
                        testcase_testrail_bk_rm = testcase_testrail_fr_rm.replace("TR##",'')
                        testcase_colon_rm = testcase_testrail_bk_rm.replace(":",'')
                        testcase_hash_rm = testcase_colon_rm.replace("#",'')
                        testcase_comma_rm = testcase_hash_rm.replace(",", '')
                        testcase_space_rm = testcase_comma_rm.replace(" ", '')

                        testcase_testrail_id_rm = re.sub(r'C(\d)+',"",testcase_space_rm)
                        splited_testcase = testcase_testrail_id_rm.replace("_", "")
                        # Iterating over folder to get the log file of failed testcase
                        for k in testcaselist:
                            # Removing the special characters and testrail id from testcase folder
                            testcaseflr_testrail_fr_rm = k.replace("__TR", '')
                            testcaseflr_testrail_bk_rm = testcaseflr_testrail_fr_rm.replace("TR__", '')
                            testcaseflr_testrail_colon_rm = testcaseflr_testrail_bk_rm.replace(":", '')
                            testcaseflr_testrail_hash_rm = testcaseflr_testrail_colon_rm.replace("#", '')
                            testcaseflr_testrail_comma_rm = testcaseflr_testrail_hash_rm.replace(",", '')
                            testcaseflr_testrail_underscore_rm = testcaseflr_testrail_comma_rm.replace("_", '')
                            testcaseflr_testrail_space_rm = testcaseflr_testrail_underscore_rm.replace(" ", '')

                            testcaseflr_testrail_id_rm = re.sub(r'C(\d)+', "",
                                                                testcaseflr_testrail_space_rm)
                            verify_flr = testcaseflr_testrail_id_rm.lstrip('0123456789')
                            # comparing the failure testcase between junit and folder
                            if splited_testcase.strip() in verify_flr or verify_flr in splited_testcase.strip():
                                error_log_url = testcase_folder + k
                                cmd = "cd " + error_log_url + "/"
                                client = paramiko.client.SSHClient()
                                client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                                client.connect(settings.PLUTOURL,
                                               username=settings.PLUTOUSERNAME, password=settings.PLUTOPASSWORD)
                                _stdin, _stdout, _stderr = client.exec_command(cmd + '\n' "ls" '\n')
                                errorlist = _stdout.read().decode().splitlines()
                                # Seeing the error file presents in pluto folder.
                                if "VanillaGinkgo.INFO" in errorlist:
                                    info_log = error_log_url + "/" + "VanillaGinkgo.INFO"
                                    updated_error_log_url = re.sub("/home/cohesity/data/",
                                                                   "https://sv4-pluto.eng.cohesity.com/",info_log)
                                    error_url = updated_error_log_url
                                    testname = tcname.attrib['name']
                                    if testname not in testcase_name.keys() and k not in reference_dict.keys():
                                        testdetailslist.append(
                                            {"error":errors, "tcname": tcname.attrib['name'],
                                             "suitename": suite.attrib['name'],
                                             "error_log": error_url})
                                        testcase_name[tcname.attrib['name']] = 1
                                        reference_dict[k] = 1
                        # appending the failed testcase if pluto folder is not present
                        error_tc_testcaselist = []
                        for i in testdetailslist:
                            error_tc_testcaselist.append(i['tcname'])
                        for i in exact_failure_testcase.keys():
                            if i not in error_tc_testcaselist:
                                testdetailslist.append({"error":errors, "tcname": i, "suitename": suite.attrib['name'],
                                                        "error_log":
                                                            "No Error logs for this testcase in Pluto "
                                                            "please refer previous testcase logs"})


    # print("Ther testdetails list is",testdetailslist)
    # print("length of testdetails..",len(testdetailslist))
    return render(request, "triage_v2.html", {"data": testdetailslist})

def train_analyze_optimize(request):
    """
    step1: From train watchmen url we will take the junit file with respective suite name
    step2: Loop over the junit file of each suite and will take the failure and coverage counts
           along with failure message
    Step3: Calculate the testcase impact,Error count and coverage count based on value obtained in step2
    """
    # Commented need to add while integrating.
    # is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    # if is_ajax:
    #     if request.method == 'POST':
    #         data = json.load(request)
    #         trainname = data.get("trainname")
    #         build = data.get("build")
    #         category = data.get("category")
    # logdata = Trainlogdata.objects.get(build=build, trainname=trainname)
    # print(logdata.logurl)
    # watchmenfolder = logdata.logurl.split("/")[-1]

    # category hardcoded need to remove while integrating
    # Also move this to if loop.
    category = 'error'
    failures={} # It will hold testcase name as key with error message a value.
    failure_count = {} # It will hold suite name as key with error message a value.
    total_count = {} # It will hold suite name as key and its respective total testcase count.
    error_count = {} # It will hold error message as key and its respective count
    coverage_count = defaultdict(list) # It will hold suites as key with list of all testcases in it.
    total = 0 # For calculating the total number of testcases in a train.
    suite_error_count = defaultdict(list) # It will hold error message as key and list of suite impacted by it.
    final_list = [] # Values at the end will contain all the required values.
    junit_url_info = defaultdict(list) # Holds the suite with its junit url info.

    # need to remove the hardcoded value of watchmenfolder.
    watchmenfolder = "watchmen-2024-7-4-16-47-20-ujitpg/"
    # Mapping the suite with the junit file from watchmen train log.
    folder = "/home/cohesity/data/cohesityShare/watchmen_logs/" + watchmenfolder
    cmd = "ls " + folder
    client = paramiko.client.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(settings.PLUTOURL, username=settings.PLUTOUSERNAME, password=settings.PLUTOPASSWORD)
    _stdin, _stdout, _stderr = client.exec_command(cmd)
    suitelist = _stdout.read().decode().splitlines()
    print(suitelist)
    if len(suitelist) > 0:
        suite_dict = {}
        for val in suitelist:
            suitename = val.split('-')[0]
            cmd1 = cmd + '/' + val
            _stdin, _stdout, _stderr = client.exec_command(cmd1 + '\n' "ls" '\n')
            sub_link_list = _stdout.read().decode().splitlines()
            for sub_list in sub_link_list:
                if sub_list.split('-')[0] == suitename:
                    suite_dict[val] = sub_list
    else:
        print("need to uncomment while integrating..")
        #return HttpResponseNotFound(trainname + " analysis result is not avaialble for " + build + " build!")
    suite_junit_list = {}
    for i, j in suite_dict.items():
        url_updated = ("https://" + settings.PLUTOURL + "/cohesityShare/watchmen_logs/" +
                       watchmenfolder + "/" + i + "/" + j + "/" + "jUnit.xml")
        suite_junit_list[i.split('-')[0]] = url_updated
    client.close()

    # Looping over list of suites with respective junit file to
    # get the failure details.
    for suitename, junit_url in suite_junit_list.items():
        try:
            # code to open and process the junit file.
            file_name = urlopen_with_retry(junit_url)
            data = file_name.read()
            file_name.flush()
            file_name.close()

            data1 = xmltodict.parse(data)
            # Getting the count of Total,failed and pased testcases.
            total += int(data1['testsuite']['@tests'])
            for i in data1['testsuite']['testcase']:
                failure_count[data1['testsuite']['@name']] = data1['testsuite']['@failures']
                total_count[data1['testsuite']['@name']] = data1['testsuite']['@tests']
                coverage_count[data1['testsuite']['@name']].append(i['@name'])
                if 'failure' in i:
                    failure_info = re.sub(r'^/home.*\n?', '', i['failure']['#text'], flags=re.MULTILINE)
                    # Mapping failure info with the suites
                    failures[i['@name']] = i['failure']['#text']
                    # Appending the list of suites impacted with the specific error.
                    suite_error_count[failure_info].append(data1['testsuite']['@name'])
                    # Encrypting the junit file to give as input to next page.
                    junit_bytes = junit_url.encode("ascii")
                    junit_base64_bytes = base64.b64encode(junit_bytes)
                    junit_encoded = junit_base64_bytes.decode("ascii")
                    junit_url_info[failure_info].append(junit_encoded)
                    # Incrementing the error message if it is same text
                    # or adding it to new one.
                    if failure_info in error_count.keys():
                        error_count[failure_info] += 1
                    else:
                        error_count[failure_info] = 1
        except urllib.request.HTTPError as err:
            print(f'An HTTP error occurred: {err}')

    # Calculating the values based on error category
    if category == 'error':
        for key, value in error_count.items():
            # Suite_impact is calculated by length of unique suites affcted.
            # Testcase impact is calculated by error count/total testcase count in train
            junit_details = "#@#".join(junit_url_info[key])
            testcase_imp = int(value) / total * 100
            # Encrypting the error message for input for next page.
            error_bytes = key.encode("utf-8")
            error_base64_bytes = base64.b64encode(error_bytes)
            error_decrypt = error_base64_bytes.decode("utf-8")
            final_list.append({"error": key, "suite_impact": len(set(suite_error_count[key])),
                               "testcase_impact": round(testcase_imp, 2), "failure_count": error_count[key],
                               "junit": junit_details, "error_decrypt": error_decrypt})
        # return JsonResponse({"errordata": final_list})
    # Calculating the values based on suite category
    elif category == 'suite':
        for key, value in failure_count.items():
            if int(value) != 0:
                suite_tc_imp = int(value) / total * 100
                try:
                    coverage = (100 - round(int(total_count[key])/len(coverage_count[key]) * 100, 2))
                except ZeroDivisionError as e:
                    print("Error: Cannot divide by zero")
                    coverage = "can't be calculated as one of parameter is zero"
                final_list.append(
                    {"suite": key, "suite_impact": 1, "testcase_impact": round(suite_tc_imp, 2),
                     "coverage_impact": coverage, "failure_count": failure_count[key]})
        # return JsonResponse(["test"], safe=False)
    print(final_list)
    return HttpResponseBadRequest('Invalid request')





def train_analyze_error_signature(request):
    """
    step1: From train watchmen url we will take the junit file with respective suite name
    step2: Loop over the junit file of each suite and will take the failure and coverage counts
           along with failure message
    Step3: Calculate the testcase impact,Error count and coverage count based on value obtained in step2
    """
    # Commented need to add while integrating.
    # is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    # if is_ajax:
    #     if request.method == 'POST':
    #         data = json.load(request)
    #         trainname = data.get("trainname")
    #         build = data.get("build")
    #         category = data.get("category")
    #         logdata = Trainlogdata.objects.filter(build=build, trainname=trainname).order_by('-id')
    #         watchmenfolder = logdata[0].logurl.split("/")[-1]

    total_tc_count_in_train = 0  # For calculating the total number of testcases in a train.
    total_tc_count_in_suite = {}  # It will hold suite name as key and its respective total testcase count.
    total_executed_tc_count_in_suite = {}
    suites_impacted_by_error = defaultdict(list)
    suite_failure_count = {}  # It will hold suite name as key with error message a value.
    final_list = []
    testcase_status_info = [] # Will hold all the data of testcase
    error_signature_in_train = {} # hold error signature as key and list of testcase affected by it as value
    error_signature_impact = {} # To calculate the testcase impacted by error signature
    total_tc_count_in_train_error = 0 # Will hold the total number of testcase in train
    suites_impacted_by_error_signature = defaultdict(list) # # Will hold suites impacted in train
    junit_url_info = defaultdict(list)
    cleaned_msg_with_junit = {}
    # # Mapping the suite with the junit file from watchmen train log.
    # need to comment the hardcoded value
    watchmenfolder = "watchmen-2024-7-17-22-10-22-adhrgi/"
    train_root_folder = "/home/cohesity/data/cohesityShare/watchmen_logs/" + watchmenfolder
    list_of_suite_cmd = "ls " + train_root_folder
    client = paramiko.client.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(settings.PLUTOURL, username=settings.PLUTOUSERNAME, password=settings.PLUTOPASSWORD)
    _stdin, _stdout, _stderr = client.exec_command(list_of_suite_cmd)
    train_suite_list = _stdout.read().decode().splitlines()

    if len(train_suite_list) > 0:
        train_junit_paths = {}
        for suite_folder in train_suite_list:
            suitename = suite_folder.split('-')[0]
            list_tc_with_junit_folder_cmd = list_of_suite_cmd + '/' + suite_folder
            _stdin, _stdout, _stderr = client.exec_command(list_tc_with_junit_folder_cmd + '\n' "ls" '\n')
            list_of_tcs_with_junit_folders = _stdout.read().decode().splitlines()
            for junit_folder in list_of_tcs_with_junit_folders:
                if junit_folder.split('-')[0] == suitename:
                    junit_path = ("https://" + settings.PLUTOURL + "/cohesityShare/watchmen_logs/" +
                        watchmenfolder + "/" + suite_folder + "/" + junit_folder + "/" + "jUnit.xml")
                    train_junit_paths[suitename] = junit_path
        client.close()
    else:
        # return HttpResponseNotFound(trainname + " analysis result is not avaialble for " + build + " build!")
        return HttpResponseBadRequest('Invalid request')
            # Looping over list of suites with respective junit file to
            # get the failure details.
    # need to remove hardcoded value
    category = 'error'
    for suitename, junit_url in train_junit_paths.items():
        try:
            # code to open and process the junit file.
            read_junit_file = urlopen_with_retry(junit_url)
            junit_data = read_junit_file.read()
            read_junit_file.flush()
            read_junit_file.close()
            junit_dict = xmltodict.parse(junit_data)
            # For loop for looping over testcase to separate them based on status.
            # Getting the count of Total,failed and pased testcases.
            if junit_dict['testsuite']['@tests'] == '0':
                continue
            total_tc_count_in_train += len(junit_dict['testsuite']['testcase']) if int(
                junit_dict['testsuite']['@tests']) < len(junit_dict['testsuite']['testcase']) else int(
                junit_dict['testsuite']['@tests'])
            suite_name_from_xml = junit_dict['testsuite']['@name']
            suite_failure_count[suite_name_from_xml] = int(junit_dict['testsuite']['@failures'])
            total_tc_count_in_suite[suite_name_from_xml] = junit_dict['testsuite']['@tests']
            total_executed_tc_count_in_suite[suite_name_from_xml] = len(junit_dict['testsuite']['testcase']) if \
            junit_dict['testsuite']['@tests'] != "1" else 1
            if total_tc_count_in_suite[suite_name_from_xml] == "1" and (
                    type(junit_dict['testsuite']['testcase']) is str or type(
                    junit_dict['testsuite']['testcase']) is dict):
                junit_dict['testsuite']['testcase'] = [junit_dict['testsuite']['testcase']]

            for xmltag in junit_dict['testsuite']['testcase']:
                if xmltag["@name"] == "AfterSuite":
                    total_executed_tc_count_in_suite[suite_name_from_xml] = len(junit_dict['testsuite']['testcase']) - 1
                if 'failure' in xmltag:
                    total_tc_count_in_train_error += 1
                    failure_msg = re.sub(r'^/home.*\n?', '', xmltag['failure']['#text'], flags=re.MULTILINE)
                    cleaned_failure_msg = cleanup_text(failure_msg)
                    # comparing the database with cleaned error message.
                    try:
                        error_query = OptimalSolution.objects.get(cleaned_error_msg=cleaned_failure_msg)
                        readable_sig = error_query.err_sig_readable
                        optimal_solution = error_query.optimal_solution
                        error_msg_signature = error_query.error_msg_signature
                        junit_bytes = junit_url.encode("ascii")
                        junit_base64_bytes = base64.b64encode(junit_bytes)
                        junit_encoded = junit_base64_bytes.decode("ascii")
                        if error_msg_signature in cleaned_msg_with_junit.keys():
                            for error_message in cleaned_msg_with_junit[error_msg_signature]:
                                if cleaned_failure_msg in error_message.keys():
                                    error_message[cleaned_failure_msg].append(junit_encoded)
                                else:
                                    error_message[cleaned_failure_msg]=[junit_encoded]
                        else:
                            cleaned_msg_with_junit[error_msg_signature] = [{cleaned_failure_msg:[junit_encoded]}]
                        testcase_status_info.append({"status":"failed","cleaned_error_msg":cleaned_failure_msg,"optimal_soln":optimal_solution,"suite": xmltag['@classname'],"error_msg":failure_msg,
                                                "error_signature":error_msg_signature,"readable_error_signature":readable_sig,
                                                "junit":junit_encoded,"testcase_name":xmltag['@name']})
                    except ObjectDoesNotExist:
                        readable_sig = "No error signature exists"
                        error_msg_signature = "No error signature exists"
                        junit_bytes = junit_url.encode("ascii")
                        junit_base64_bytes = base64.b64encode(junit_bytes)
                        junit_encoded = junit_base64_bytes.decode("ascii")
                        if error_msg_signature in cleaned_msg_with_junit.keys():
                            for error_message in cleaned_msg_with_junit[error_msg_signature]:
                                if cleaned_failure_msg in error_message.keys():
                                    error_message[cleaned_failure_msg].append(junit_encoded)
                                else:
                                    error_message[cleaned_failure_msg]=[junit_encoded]
                        else:
                            cleaned_msg_with_junit[error_msg_signature] = [{cleaned_failure_msg:[junit_encoded]}]
                        optimal_solution = "No optimal solution exists"
                        testcase_status_info.append({"status":"failed","cleaned_error_msg":cleaned_failure_msg,"optimal_soln":optimal_solution,"suite": xmltag['@classname'],"error_msg":failure_msg,
                                                "error_signature":error_msg_signature,"readable_error_signature":readable_sig,
                                                "junit":junit_encoded,"testcase_name":xmltag['@name']})
                elif 'skipped' in xmltag:
                    total_tc_count_in_train_error += 1
                    testcase_status_info.append({"status":"skipped","suite": xmltag['@classname'],"testcase_name":xmltag['@name']})
                else:
                    total_tc_count_in_train_error += 1
                    testcase_status_info.append({"status":"passed","suite": xmltag['@classname'],"testcase_name":xmltag['@name']})
        except urllib.request.HTTPError as err:
            print(f'An HTTP error occurred: {err}')
    # Calculating the values based on error category
    if category == 'error':
        for i in testcase_status_info:
            if i['status'] == 'failed':
                if i['error_signature'] in error_signature_in_train.keys():

                    error_signature_in_train[i["error_signature"]].append({"cleaned_error_msg": i["cleaned_error_msg"],"optimal_soln": i["optimal_soln"],"suite": i['suite'], "error_msg":i['error_msg'],"readable_error_signature":i['readable_error_signature'],
                                            "junit":i["junit"],"testcase_name":i['testcase_name']})
                else:
                    error_processing_list = []
                    error_processing_list.append({"cleaned_error_msg": i["cleaned_error_msg"],"optimal_soln": i["optimal_soln"],"suite": i['suite'], "error_msg":i['error_msg'],"readable_error_signature":i['readable_error_signature'],
                                            "junit":i["junit"],"testcase_name":i['testcase_name']})
                    error_signature_in_train[i["error_signature"]] = error_processing_list
        for i in error_signature_in_train.keys():
            error_signature_impact[i] = round(len(error_signature_in_train[i]) / total_tc_count_in_train_error * 100, 2)
            for j in error_signature_in_train[i]:
                if j['suite'] not in suites_impacted_by_error_signature[i]:
                    suites_impacted_by_error_signature[i].append(j['suite'])

        for i in error_signature_in_train.keys():
           final_list.append({"error_signature": i,"suite_impact": len(suites_impacted_by_error_signature[i]),
                              "error_signature_impact": error_signature_impact[i],"error_count":len(error_signature_in_train[i]),"cleaned_msg_with_junit":cleaned_msg_with_junit[i],
                              "train_data":error_signature_in_train[i]})
    elif category == 'suite':
            for suitename, failure_count in suite_failure_count.items():
                # if int(failure_count) != 0 and total_tc_count_in_train != 0:
                if int(failure_count) > int(total_tc_count_in_train):
                    suite_tc_imp = round((total_tc_count_in_train / int(failure_count)) * 100, 2)
                elif int(failure_count) < int(total_tc_count_in_train):
                    suite_tc_imp = round((int(failure_count) / total_tc_count_in_train) * 100, 2)
                else:
                    suite_tc_imp = 0.00
                if int(total_executed_tc_count_in_suite[suitename]) > int(total_tc_count_in_suite[suitename]):
                    coverage_imp = round(int(total_tc_count_in_suite[suitename]) / int(total_executed_tc_count_in_suite[suitename]) * 100, 2)
                elif int(total_executed_tc_count_in_suite[suitename]) < int(total_tc_count_in_suite[suitename]):
                    coverage_imp = round((int(total_executed_tc_count_in_suite[suitename]) / int(total_tc_count_in_suite[suitename])) * 100, 2)
                else:
                    coverage_imp = 0.00
                final_list.append(
                    {"suite": suitename, "testcase_impact": suite_tc_imp,
                     "coverage_impact": coverage_imp, "failure_count": suite_failure_count[suitename]})
            sorted_final_list = sorted(final_list, key=itemgetter('failure_count'), reverse=True)
    print("final list is ....",final_list)
    return HttpResponseBadRequest('Invalid request')

