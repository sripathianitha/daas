import paramiko
import re
import csv
import requests
import xml.etree.ElementTree as ET
import xlsxwriter
from collections import defaultdict

def error_info():
    host = "sv4-pluto.eng.cohesity.com"
    username = "cohesity"
    password = "fr8shst8rt"
    failure_url_list = []
    suitelist = []
    error_url = []
    suite_info_list = []
    error_info_list = []

    folder2_dict = defaultdict(list)
    folder_level_1 = "/home2/cohesity/data/cohesityShare/watchmen_logs/"
    cd_add = "cd "
    client = paramiko.client.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(host, username=username, password=password)
    _stdin, _stdout, _stderr = client.exec_command(cd_add + folder_level_1 + '\n' "ls" '\n')
    watchmen_folder = _stdout.read().decode().splitlines()
    split_list = []
    for folder_level_2 in watchmen_folder:
        if "watchmen-2024-6-" in folder_level_2:
            split_list.append(folder_level_2)
            client1 = paramiko.client.SSHClient()
            client1.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            client1.connect(host, username=username, password=password)

            _stdin, _stdout, _stderr = client1.exec_command(cd_add + folder_level_1 + folder_level_2 + '/' + '\n' "ls" '\n')
            suite_folder = _stdout.read().decode().splitlines()
            for i in suite_folder:
                if "." not in i and "Rlaas" not in i:
                    folder2_dict[folder_level_2].append(i)

            client1.close()
    for key,value in folder2_dict.items():
        for i in value:
            _stdin, _stdout, _stderr = client.exec_command(cd_add + folder_level_1 + key + '/' + i + '/' + '\n' "ls" '\n')
            inner_suite_folder = _stdout.read().decode().splitlines()
            for j in inner_suite_folder:
                if i.split('-')[0] in j:
                    failure_url = folder_level_1 + key + '/' + i + '/' + j + '/' + "jUnit.xml"
                    failure_url_list.append(failure_url)
    for url in failure_url_list:
        updated_url = re.sub("/home2/cohesity/data/", "https://sv4-pluto.eng.cohesity.com/", url)
        resp = requests.get(updated_url)

        if resp.status_code == 200:
            # saving the xml file
            with open('topnewsfeed.xml', 'wb') as f:
                f.write(resp.content)
            tree = ET.parse('topnewsfeed.xml')
            # get suite element
            suite = tree.getroot()
            for tcname in suite:
                for failure in tcname:
                    if failure.tag == "failure":
                        error_info_list.append(failure.text)
#    Adding list data to new excel
    import pandas as pd
    df = pd.DataFrame(error_info_list, columns=["Error"])
    excel_file = "errorjun.xlsx"
    df.to_excel(excel_file, index=False)
    print("error info list..",error_info_list)
    client.close()
    return error_info_list

def main():

   url_lists = error_info()

if __name__ == "__main__":
    # calling main function
    main()