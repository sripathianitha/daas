import paramiko
import re
import csv
import requests
import xml.etree.ElementTree as ET
from collections import defaultdict

def url_getting():
    host = "sv4-pluto.eng.cohesity.com"
    username = "cohesity"
    password = "fr8shst8rt"
    suitelist = []

    folder = "/home/cohesity/data/cohesityShare/watchmen_logs/"
    url = "https://sv4-pluto.eng.cohesity.com/cohesityShare/watchmen_logs/watchmen-2024-5-27-15-37-50-imxteg/"
    folder2 = folder + "watchmen-2024-5-27-15-37-50-imxteg"
    cmd = "cd " + folder2
    client = paramiko.client.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(host, username=username, password=password)
    _stdin, _stdout,_stderr = client.exec_command(cmd + '\n' "ls" '\n')
    suitelist = _stdout.read().decode().splitlines()
    suite_dict = {}
    for val in suitelist:
        suitename = val.split('-')[0]
        cmd1 = cmd + '/' + val
        _stdin, _stdout, _stderr = client.exec_command(cmd1 + '\n' "ls" '\n')
        sub_link_list = _stdout.read().decode().splitlines()
        for sub_list in sub_link_list:
            if sub_list.split('-')[0] == suitename:
                suite_dict[val] = sub_list
    url_list = []
    for i,j in suite_dict.items():
        url_updated = url + i + "/" + j + "/" + "jUnit.xml"
        url_list.append(url_updated)
    client.close()

    return url_list

def failure_data(url_lists):
    # create element tree object
    # create empty list for news items
    failures = {}
    failure_count = {}
    total_count = {}
    suite_impact = {}
    testcase_impact = {}
    error_count = {}
    error_impact = {}
    coverage_impact = {}
    coverage_count = defaultdict(list)
    coverage_total_count = {}
    total  = 0
    suite_error_count = defaultdict(list)
    suite_impact_count = {}
    final_list = []
    for url in url_lists:
        resp = requests.get(url)

        # saving the xml file
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
                    if failure_info in error_count.keys():
                        error_count[failure_info] += 1
                    else:
                        error_count[failure_info] = 1

    # Calculating the failure testcase per train and suite wise.
    for key, value in failure_count.items():
        testcase_impact[key] = int(value)/total * 100
        suite_impact[key] = int(value)/int(total_count[key]) * 100
    for key, value in coverage_count.items():
        coverage_total_count[key] = len(value)
    for key, value in error_count.items():
        error_impact[key] = int(value)/total * 100
    # Calculating the error testcase per train
    for key,value in coverage_total_count.items():
        coverage_impact[key] = int(value)/int(total_count[key]) * 100
    for key, value in suite_error_count.items():
        suite_impact_count[key] = len(value)
    # Appending the suite and error info in list.
    for key,value in error_count.items():
        final_list.append({"error":key,"suite_impact":suite_impact_count[key],"error_impact":round(error_impact[key],2),"error_count":error_count[key]})
    for key, value in failure_count.items():
        final_list.append({"suite":key,"suiteimpact":1,"testcase_impact":round(testcase_impact[key],2),"coverage_impact":round(coverage_impact[key],2),"failure_count":failure_count[key]})
    print("Final list",final_list)
    return failures

def main():

    url_lists = url_getting()
    failures = failure_data(url_lists)

if __name__ == "__main__":
    # calling main function
    main()