import os
import re
import json
import pexpect
import requests
import xml.etree.ElementTree as ET
from datetime import datetime

ticket = os.getenv('TICKET')
username = os.getenv('USERNAME')
if 'redhat.com' in username:
    user = re.search(r'[^@]+', username).group(0)
else:
    user = username

# open the password file
password_file = open('/secret/passwordfile', 'r')
password = password_file.read()

remote_directory = '/srv/cases/0' + ticket[0:2] + '/' + ticket[2:5] + '/' + ticket[5:8] + '/attachments'
if int(ticket) > 1599999:
    remote_directory = '/srv/cases/0' + ticket[0:2] + '/' + '/'.join(
        [ticket[i + 2:i + 3] for i in range(len(ticket) - 1)]) + 'attachments'

# create a storage for the ticket
try:
    os.makedirs('/cases/' + ticket)
except IOError as e:
    pass 

# scp_command = 'sshpass -f /secret/passwordfile scp -o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no -r ' + user + '@s01.gss.hst.phx2.redhat.com:' + remote_directory + ' /cases/' + ticket
# scp_process = subprocess.check_call(scp_command.split(' '))

child = pexpect.spawn('scp -o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no -r ' + user +'@s01.gss.hst.phx2.redhat.com:' + remote_directory + ' /cases/' + ticket)
child.expect("Warning: Permanently added 's01.gss.hst.phx2.redhat.com,10.5.63.11' (RSA) to the list of known hosts.") 
child.expect(user+"@s01.gss.hst.phx2.redhat.com's password:")
child.sendline(password)


# Run Citellus on the Customer Ticket sos-report
# if os.path.isdir('/cases/' + ticket + '/attachments'):
os.system('python3 citellus/citellus.py /cases/' + ticket + '/attachments/sosreport-osp12-controller-0-containers.tar.xz-5040f0b8-615b-4696-b805-e1374f6c7b3e')

# Read the json result file to parse.
f = open('/cases/' + ticket + '/attachments/citellus.json')
report = json.load(f)

hash_map = []
solution_data = []
api_endpoint = "https://api.access.redhat.com/rs/solutions/"

for hash_key, plugin in report['results'].items():
    if plugin.get('result').get('rc') == 20:
        if plugin.get('kb') and 'https://access.redhat.com/solutions' in plugin.get('kb'):
            kbase_id = re.search(r'\d+$', plugin.get('kb')).group(0)
            if kbase_id not in hash_map:
                hash_map.append(kbase_id)
                url = api_endpoint + kbase_id
                response = requests.get(url, auth=(username, password))
                if response.status_code == 200:
                    xml = response.text
                    tree = ET.fromstring(xml)
                    try:
                        resolution = tree.find('{http://www.redhat.com/gss/strata}resolution')
                        solution = resolution.find('{http://www.redhat.com/gss/strata}text').text
                    except:
                        pass
                    if solution:
                        plugin['result']['solution'] = solution
                else:
                    print(response.status_code, '\n', response.text)
        solution_data.append(plugin)

# if solution_data:
solution_data = sorted(solution_data, key=lambda val: val['priority'], reverse=True)

comment = "HI,\n"
link = ""
for sol in solution_data:
    if 'solution' in sol.get('result'):
        comment += "Problem looks to be: " + sol.get('description') + "\n" + "and " + sol.get('result').get('err')
        comment += "\nMay be this can help: " + sol.get('result').get('solution') + "\n"
        link = sol.get('kb')
    elif sol.get('kb'):
        comment += "Problem looks to be: " + sol.get('description') + "\n" + "and " + sol.get('result').get('err')
        comment += "\nMay be this can help: " + sol.get('kb') + "\n"
        link = sol.get('kb')
    else:
        comment += "\nProblem looks to be: " + sol.get('description') + "\n" + "and " + sol.get('result').get(
            'err') + "\n"
    break

time = datetime.now().strftime('%Y-%m-%dT%H:%M:%SZ')
comment_endpoint = 'https://api.access.redhat.com/rs/cases/' + str(ticket) + '/comments'
payload = {
    "label": "Solution by the bot",
    "text": comment,
    "uri": link,
    "draft": False,
    "caseNumber": str(ticket),
    "public": False
}

comment_response = requests.post(comment_endpoint, json=payload, auth=(username, password))
print('comment status: ',comment_response.status_code)
