import os
import string
import random
import requests
import xml.etree.ElementTree as ET
from flask import Flask
from flask import render_template
from flask import request

app = Flask(__name__)
ocl_url = os.getenv('OCL_URL')
ocl_token = os.getenv('OCL_TOKEN')
ocl_namespace = os.getenv('OCL_NAMESPACE')


@app.route('/')
def home():
    return render_template('index.html')


@app.route('/process_ticket', methods=['GET', 'POST'])
def process_ticket():
    success = False
    next = request.values.get('next', '')
    if request.method == 'POST':
        namespace = ocl_namespace if ocl_namespace else '' #set default here
        url = ocl_url if ocl_url else '' #set default here
        access_token = ocl_token if ocl_token else '' #set default here
        
        # login
        ocl_response = os.system('oc login {} --insecure-skip-tls-verify=true --token {}'.format(url,access_token))

        # secret
        secret_name = 'sbr-{}'.format(''.join(random.choices(string.ascii_lowercase + string.digits, k=6)))
        secret_response = os.system('oc create secret --namespace {} generic {} \
            --from-literal=password={request.form.get("password")} \
            --from-literal=username={request.form.get("username")}\
            --from-literal=ticket={str(request.form.get("ticket"))}\
            --from-literal=server={str(request.form.get("server"))}\
            --type=kubernetes.io/basic-auth'.format(namespace,secret_name))

        job_name = 'sbr-job-{}'.format(''.join(random.choices(string.ascii_lowercase + string.digits, k=6)))
        job_response = os.system('oc new-app --namespace {} --template={}/sbr-newjob -p SBRSECRET={} -p SBEJOBNAME={}'.format(namespace,namespace,secret_name,job_name))

        status_check = ['1', 'Running']
        if not job_response:
            while status_check[1] == 'Running' and status_check[0] == '1':
                job_status = os.popen('oc describe job sbr').read()
                job = job_status.split('\n')
                status = list
                for param in job:
                    if ':' in param:
                        key, val = param.split(':', 1)
                        if key == 'Pods Statuses':
                            status = [stat.strip().split(' ') for stat in val.split('/')]
                            break
                solution = ""
                url = 'https://access.redhat.com/support/cases/#/case/{}'.format(str(request.form.get("ticket")))
                if status:
                    for stat in status:
                        status_check = stat
                        print('status_check', status_check)
                        if stat[1] == 'Running' and stat[0] == '1':
                            break
                        elif stat[1] == 'Succeeded' and stat[0] == '1':
                            success = True
                            comment_url = 'https://api.access.redhat.com/rs/cases/{}/comments'.format(str(request.form.get("ticket")))
                            response = requests.get(comment_url, auth=(request.form.get("username"), request.form.get("password")))
                            if response.status_code == 200:
                                xml = response.text
                                tree = ET.fromstring(xml)
                                try:
                                    solution = tree[1][4].text
                                    print(solution.split('\n'))
                                except:
                                    pass
                            break
                        else:
                            success = False
                else:
                    success = False

    return render_template('end.html', success=success, ticket=str(request.form.get("ticket")), url=url, solution=solution)


if __name__ == '__main__':
    app.run(host="0.0.0.0",port=8080, debug=True)
