def error_basis_triage_old(request):
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


def train_analyze_result(request):
    """
    step1: From train watchmen url we will take the junit file with respective suite name
    step2: Loop over the junit file of each suite and will take the failure and coverage counts
           along with failure message
    Step3: Calculate the testcase impact,Error count and coverage count based on value obtained in step2
    """
    # Commented need to add while integrating.
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    if is_ajax:
        if request.method == 'POST':
            data = json.load(request)
            trainname = data.get("trainname")
            build = data.get("build")
            category = data.get("category")
            logdata = Trainlogdata.objects.filter(build=build, trainname=trainname).order_by('-id')
            watchmenfolder = logdata[0].logurl.split("/")[-1]

            total_tc_count_in_train = 0  # For calculating the total number of testcases in a train.
            total_tc_count_in_suite = {}  # It will hold suite name as key and its respective total testcase count.
            total_executed_tc_count_in_suite = {}
            suites_impacted_by_error = defaultdict(list)
            suite_failure_count = {}  # It will hold suite name as key with error message a value.
            errors_count_in_train = {}  # It will hold error message as key and its respective count
            failures={} # It will hold testcase name as key with error message a value.
            coverage_count = defaultdict(list) # It will hold suites as key with list of all testcases in it.
            raw_error_msg_mapping = {}

            final_list = [] # Values at the end will contain all the required values.
            junit_url_info = defaultdict(list) # Holds the suite with its junit url info.

            # Mapping the suite with the junit file from watchmen train log.
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
                return HttpResponseNotFound(trainname + " analysis result is not avaialble for " + build + " build!")

            # Looping over list of suites with respective junit file to
            # get the failure details.
            for suitename, junit_url in train_junit_paths.items():
                try:
                    # code to open and process the junit file.
                    read_junit_file = urlopen_with_retry(junit_url)
                    junit_data = read_junit_file.read()
                    read_junit_file.flush()
                    read_junit_file.close()

                    junit_dict = xmltodict.parse(junit_data)
                    # Getting the count of Total,failed and pased testcases.
                    if junit_dict['testsuite']['@tests'] == '0':
                        continue
                    total_tc_count_in_train += len(junit_dict['testsuite']['testcase']) if int(junit_dict['testsuite']['@tests']) < len(junit_dict['testsuite']['testcase']) else int(junit_dict['testsuite']['@tests'])
                    suite_name_from_xml = junit_dict['testsuite']['@name']
                    suite_failure_count[suite_name_from_xml] = int(junit_dict['testsuite']['@failures'])
                    total_tc_count_in_suite[suite_name_from_xml] = junit_dict['testsuite']['@tests']
                    total_executed_tc_count_in_suite[suite_name_from_xml] = len(junit_dict['testsuite']['testcase']) if junit_dict['testsuite']['@tests'] != "1" else 1
                    if total_tc_count_in_suite[suite_name_from_xml] == "1" and (type(junit_dict['testsuite']['testcase']) is str or type(junit_dict['testsuite']['testcase']) is dict):
                        junit_dict['testsuite']['testcase'] = [junit_dict['testsuite']['testcase']]

                    for xmltag in junit_dict['testsuite']['testcase']:
                        if xmltag["@name"] == "AfterSuite":
                            total_executed_tc_count_in_suite[suite_name_from_xml] = len(junit_dict['testsuite']['testcase']) -1
                        if 'failure' in xmltag:
                            failure_msg = re.sub(r'^/home.*\n?', '', xmltag['failure']['#text'], flags=re.MULTILINE)
                            cleaned_failure_msg = cleanup_text(failure_msg)
                            raw_error_msg_mapping[cleaned_failure_msg] = failure_msg
                            # Mapping failure info with the suites
                            failures[xmltag['@name']] = xmltag['failure']['#text']
                            # Appending the list of suites impacted with the specific error.
                            suites_impacted_by_error[cleaned_failure_msg].append(junit_dict['testsuite']['@name'])
                            # Encrypting the junit file to give as input to next page.
                            junit_bytes = junit_url.encode("ascii")
                            junit_base64_bytes = base64.b64encode(junit_bytes)
                            junit_encoded = junit_base64_bytes.decode("ascii")
                            junit_url_info[cleaned_failure_msg].append(junit_encoded)
                            # Incrementing the error message if it is same text
                            # or adding it to new one.
                            if cleaned_failure_msg in errors_count_in_train.keys():
                                errors_count_in_train[cleaned_failure_msg] += 1
                            else:
                                errors_count_in_train[cleaned_failure_msg] = 1
                except urllib.request.HTTPError as err:
                    pprint.pprint(urllib.request)
                    print(f'An HTTP error occurred: {err}')
                    continue

            # Calculating the values based on error category
            if category == 'error':
                for cleaned_err_msg, err_msg_count in errors_count_in_train.items():
                    # Suite_impact is calculated by length of unique suites affcted.
                    # Testcase impact is calculated by error count/total testcase count in train
                    junit_details = "#@#".join(junit_url_info[cleaned_err_msg])
                    testcase_imp = int(err_msg_count) / total_tc_count_in_train * 100
                    # Encrypting the error message for input for next page.
                    error_bytes = raw_error_msg_mapping[cleaned_err_msg].encode("utf-8")
                    error_base64_bytes = base64.b64encode(error_bytes)
                    error_decrypt = error_base64_bytes.decode("utf-8")
                    final_list.append({"error": raw_error_msg_mapping[cleaned_err_msg], "suite_impact": len(set(suites_impacted_by_error[cleaned_err_msg])),
                                       "testcase_impact": round(testcase_imp, 2), "failure_count": errors_count_in_train[cleaned_err_msg],
                                       "junit": junit_details, "error_decrypt": error_decrypt})

                json_data = json.dumps(raw_error_msg_mapping)
                json_bytes = json_data.encode('utf-8')
                encoded_bytes = base64.b64encode(json_bytes)
                encoded_string = encoded_bytes.decode('utf-8')
                request.session["errormsgdata"] = encoded_string

                sorted_final_list = sorted(final_list, key=itemgetter('failure_count'), reverse=True)
                return JsonResponse({"errordata": sorted_final_list})
            # Calculating the values based on suite category
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
                return JsonResponse({"suitedata": sorted_final_list})
            return JsonResponse(["test"], safe=False)
        else:
            return HttpResponseBadRequest('Invalid request')
