import pprint
import urllib.error

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from retry import retry
from urllib.request import urlopen
import nltk, re
import asyncio
from nltk.tokenize import word_tokenize
from nltk.corpus import stopwords
import xmltodict



def retry_session(retries, session=None, backoff_factor=0.5):
    session = session or requests.Session()
    retry = Retry(
        total=retries,
        read=retries,
        connect=retries,
        backoff_factor=backoff_factor,
        status_forcelist=[500, 502, 503, 504]
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    return session

@retry(urllib.error.URLError, tries=5, delay=3, backoff=2)
def urlopen_with_retry(url):
    return urlopen(url)


def cleanup_text(text):
    # Lowercase
    text = text.lower()
    # Remove non-alphanumeric characters
    text = ''.join([char for char in text if char.isalpha() or char == ' '])
    # Tokenization (split text into words)
    tokens = word_tokenize(text)
    # Remove stopwords
    stop_words = set(stopwords.words('english'))
    tokens = [token for token in tokens if token not in stop_words]
    # Join tokens back into a single string
    cleaned_text = ' '.join(tokens)
    return cleaned_text


def cleaned_testcase_name(name):
    testcase_name = name.strip().lower()
    replacing_string = ["##tr", "tr##", ":", "#", ",", " ", "__tr", "tr__", "_", r"prepare",
                        r"execute", r"result", "-", r"c(\d)+", r"^(\d)+"]
    for rs in replacing_string:
        testcase_name = re.sub(rs, "", testcase_name)
    return testcase_name

def compare_similarity_of_string(source_str, comparing_str):
    source_string_len = len(source_str)
    matched_count = 0
    for st, ct in list(zip(source_str,comparing_str)):
        if st == ct:
            matched_count += 1
        else:
            break
    return round((matched_count/source_string_len)*100, 2)

def get_testcase_name(name,clusterlist):
    for cluster_name in clusterlist:
        if ":"+cluster_name.lower() in name:
            # print(name.split(cluster_name))
            return name.split(":"+cluster_name.lower())[0]
    else:
        return name

async def matching_logs(suite,results):
    # print(suite)
    if results.get('testcase_results') is not None:
        for db_tc in results['testcase_results']:
            if db_tc['status'] == "Passed" or db_tc['status'] == "Failed":
                db_tc_name = db_tc['test_name']
                db_tc_name = re.sub(r"^(Prepare-)|(Result-)|(Execute-)", "", db_tc_name)
                db_tc_name = db_tc_name.replace(" ","_")
                for log_tc_name in results['tc_name_only'].keys():
                    if log_tc_name in db_tc_name:
                        tc_log = results['suite_log_url'] + "/" + results['tc_name_only'][log_tc_name] + "VanillaGinkgo.INFO"
                        # log_res = requests.head(tc_log)
                        # if log_res.status_code == 200:
                        db_tc['log'] = tc_log
                        # else:
                        #     db_tc['log'] = results['suite_log_url'] + "/suite_summary.html"
                        del results['tc_name_only'][log_tc_name]
                        break
                else:
                    db_tc['log'] = results['suite_log_url'] + "/suite_summary.html"

        if "AfterSuite_logs/" in results['tc_name_only']:
            db_tc["AfterSuite"] = suite['suite_log_url'] + "/AfterSuite_logs/"
        if "BeforeSuite_logs/" in results['tc_name_only']:
            db_tc["BeforeSuite"] = suite['suite_log_url'] + "/BeforeSuite_logs/"


async def mapping_errors(suite,results):
    # print(suite)
    if results.get("junit_url") is not None:
        e_junit_res = requests.head(results.get("junit_url"))
        if e_junit_res.status_code == 200:
            try:
                e_read_junit_file = urlopen(results["junit_url"])
                e_junit_data = e_read_junit_file.read()
                e_read_junit_file.flush()
                e_read_junit_file.close()
            except urllib.request.HTTPError as err:
                print(f'An HTTP error occurred: {err}')

            e_junit_dict = xmltodict.parse(e_junit_data)
            if e_junit_dict['testsuite'].get('testcase') is None:
                return
            if type(e_junit_dict['testsuite']['testcase']) is str or type(e_junit_dict['testsuite']['testcase']) is dict:
                e_junit_dict['testsuite']['testcase'] = [e_junit_dict['testsuite']['testcase']]
            for xmltag in e_junit_dict['testsuite']['testcase']:
                if 'failure' in xmltag:
                    for db_tc in results['testcase_results']:
                        xml_tc_name = re.sub(r"[_#]{2}TR[:Cc0-9,\s]+(TR[_#]{2})?", "", xmltag['@name'].strip())
                        # if suite == "PhysicalBlockCentOS7xIPv4OnlySanitySuite":
                        #     print(db_tc['test_name'].strip(),"<<<<<<>>>>>",xml_tc_name)
                        if db_tc['test_name'].strip() == xml_tc_name and db_tc['status'] == "Failed" and db_tc.get('error_msg') is None:
                            db_tc['error_msg'] = xmltag['failure']['#text']
                            # if suite == "PhysicalBlockCentOS7xIPv4OnlySanitySuite":
                            #     print("=====",db_tc['error_msg'])
                            break

def clean_severe_content(text):
    # Lowercase
    text = text.lower()
    text = re.sub(r"(?=http[s])(.*)(?=\/)","",text)
    text = re.sub(r"\.[a-z0-9]+.js","", text)
    text = re.sub(r"\\\"[a-z0-9]+\\\"","",text)
    text = re.sub(r"\/[a-z0-9]+[\s:]","",text)
    # Remove non-alphanumeric characters
    text = ''.join([char for char in text if char.isalpha() or char == ' '])
    # Tokenization (split text into words)
    tokens = word_tokenize(text)
    # Remove stopwords
    # stop_words = set(stopwords.words('english'))
    # tokens = [token for token in tokens if token not in stop_words]
    tokens = [token for token in tokens]
    # Join tokens back into a single string
    cleaned_text = ' '.join(tokens)
    return cleaned_text