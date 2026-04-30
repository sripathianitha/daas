from django import template
from restapi.models import SevereDetail
import requests, json

register = template.Library()


@register.filter
def watchmentag(trainurl):
    tag = trainurl.split("/")[-1]
    return tag

@register.filter
def suitename(suitewithtestcase):
    suitename = suitewithtestcase.split("###")[0]
    return suitename

@register.filter
def testcasename(suitewithtestcase):
    tcname = suitewithtestcase.split("###")[1]
    return tcname

@register.filter
def screenshot_url(logsdata):
    workflowurl = list(logsdata.values())[0]
    split_path  = workflowurl.split("/")
    del split_path[-1]
    joined_path = "/".join(split_path)
    replaced_path = joined_path.replace("https","http").replace(".com",".com:5000")
    return replaced_path


@register.simple_tag
def buggy_severe_log(signature):
    if signature != "":
        jira_server = ""
        slog_data = SevereDetail.objects.get(cleaned_error=signature)
        if slog_data.bug_id:
            jira_server_url = "https://jira.cohesity.com/rest/api/2/issue/"+slog_data.bug_id+"?fields=status"
            # jira_server_username = "devx"
            # jira_server_password = "TSjdcOyYJMNtHby0g6N6M0BcigKJlP7r6kwYBj"
            jira_server_header = {'Authorization':'Basic ZGV2eDpUU2pkY095WUpNTnRIYnkwZzZONk0wQmNpZ0tKbFA3cjZrd1lCag=='}
            r = requests.get(jira_server_url,headers=jira_server_header)
            jira_data = json.loads(r.content)
            return slog_data.bug_id, jira_data['fields']['status']['name']

@register.filter
def colorcode(percentage):
    suite_color_code = ""
    if percentage > 93:
        suite_color_code = "background-color: #058850;"
    elif 68 <= percentage <= 93:
        suite_color_code = "background-color: #FF9800;"
    elif percentage < 68:
        suite_color_code = "background-color: #FB0909;"
    return suite_color_code


@register.filter
def length(data):
    return len(data)


@register.filter
def cleanup(text):
    return text.upper().replace("_"," ")


@register.filter
def screenshot_url_from_log(logurl):
    split_path  = logurl.split("/")
    del split_path[-1]
    del split_path[-1]
    split_path.append("workflow_logs")
    joined_path = "/".join(split_path)
    replaced_path = joined_path.replace("https","http").replace(".com",".com:5000")
    return replaced_path

