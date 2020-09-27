#!/usr/bin/python3

import boto3
import sys
import re
import pprint
import argparse
import time
import urllib.request
import math

parser = argparse.ArgumentParser(description='Perform blue-green deployment.')
parser.add_argument('--tag', help='container tag from git hash')
parser.add_argument('--rule', help='ARN of ALB rule that has the TG weights')
parser.add_argument('--svc_green', help='ARN of green service')
parser.add_argument('--svc_blue', help='ARN of blue service')
parser.add_argument('--tg_green', help='ARN of green target group')
parser.add_argument('--tg_blue', help='ARN of blue target group')
parser.add_argument('--url_blue', help='URL for blue testing')
parser.add_argument('--url_green', help='URL for green testing')
parser.add_argument('--url_grep', help='string to grep in testing release test URL')
parser.add_argument('--deploy_only', help='if "TRUE" exit after new task is running without live traffic shift.')
parser.add_argument('--canary_delay', type=int, help='Extra number of seconds to delay after first step of live traffic shift, default 0')
parser.add_argument('--step_delay', type=int, help='Base number of seconds to delay after each step-up of live traffic shift, default 45')
parser.add_argument('--testing_delay', type=int, help='Seconds to delay for testing before first step of live traffic shift, default 0')
parser.add_argument('--release_num_steps', type=int, help='Number of steps to go to 100% live traffic on new release. 1 or more, default to 3.')

parser.add_argument('-v','--verbose', action='count', dest='log_level', default=0, help='print extra debug information, -vv and -vvv also supported')
args = parser.parse_args()



# these could be tightened but should work
blue = re.compile('.*blue*')
green = re.compile('.*green*')

# hardcoded things.. >> load_config --config config_file from TF perhaps prep_env.sh
cluster = 'actest'
family = 'apache'
exec_role = 'arn:aws:iam::141517001380:role/ecsTaskExecutionRole'
ecr_prefix = '141517001380.dkr.ecr.us-east-1.amazonaws.com/my-apache2:'

# which service to update
new_service = None
old_service = None

# key blue/green service ARN in here, svc_name could be parameterized
ctx = {'blue':  {'svc_arn': '', 'svc_name': 'acblue',  'tg_arn': '', 'new_wt': 0, 'test_url': ''},
       'green': {'svc_arn': '', 'svc_name': 'acgreen', 'tg_arn': '', 'new_wt': 0, 'test_url': ''}}

# process_args funct or subroutine perhaps with context 
debug = 0
uberdebug = 0
superuberdebug = 0
if args.log_level == 1:
    debug = 1
    print('Verbose mode on.')
elif args.log_level == 2:
        debug = 1
        uberdebug = 1
        print ('Uber verbose mode on.')
elif args.log_level >= 3:
        debug = 1
        uberdebug = 1
        superuberdebug = 1
        print ('SuperUber verbose mode on.')

if (uberdebug):
    pp = pprint.PrettyPrinter(indent=4)

if (args.tag):
    tag = args.tag
    if (debug):
        print("Using supplied tag: ", tag)
else:
    tag = "latest"
    if (debug):
        print("Using default tag: ", tag)
    
    
print('tag is: ', tag)
image = ecr_prefix + tag
print('image is: ', image)


if (args.rule):
    rule = args.rule
else:
    sys.exit('Exiting, no ALB rule ARN supplied.')

if(args.svc_green):
    ctx['green']['svc_arn'] = args.svc_green
    if (debug):
        print("Got --svc_green = ctx['green']['svc_arn']) = ", ctx['green']['svc_arn'])
else:
    sys.exit('Exiting, no --svc_green for ARN of green ECS service supplied')
    
if(args.svc_blue):
    ctx['blue']['svc_arn'] = args.svc_blue
    if (debug):
        print("Got --svc_blue  = ctx['blue']['svc_arn'] = ", ctx['blue']['svc_arn'])
else:
    sys.exit('Exiting, no --svc_blue for ARN of blue ECS service supplied')
    
if(args.tg_blue):
    ctx['blue']['tg_arn'] = args.tg_blue
    if (debug):
        print("Got --tg_blue  = ctx['blue']['tg_arn'] = ", ctx['blue']['tg_arn'])
else:
    sys.exit('Exiting, no --tg_blue for ARN of blue ECS service target group')
    
if(args.tg_green):
    ctx['green']['tg_arn'] = args.tg_green
    if (debug):
        print("Got --tg_green  = ctx['green']['tg_arn'] = ", ctx['green']['tg_arn'])
else:
    sys.exit('Exiting, no --tg_green for ARN of green ECS service target group')
    

if(args.url_blue):
    ctx['blue']['test_url'] = args.url_blue
    if (debug):
        print("Got --url_blue  = ctx['blue']['test_url'] = ", ctx['blue']['test_url'])
else:
    sys.exit('Exiting, no --url_blue for testing deployments to the blue service')
    
if(args.url_green):
    ctx['green']['test_url'] = args.url_green
    if (debug):
        print("Got --url_green  = ctx['green']['test_url'] = ", ctx['green']['test_url'])
else:
    sys.exit('Exiting, no --url_green for testing deployments to the green service')
    
if(args.url_grep):
    test_grep = args.url_grep
    if (debug):
        print("Got --url_grep  = test_grep = ", test_grep)
else:
    sys.exit('Exiting, no --url_grep for testing deployment prior to cutover')

if(args.deploy_only):
    if (args.deploy_only == 'TRUE'):
        deploy_only = True
    else:
        deploy_only = False
if (debug):
    print('Set deploy_only flag: ', deploy_only)

if(args.canary_delay):
    # some type checking would be nice here
    canary_delay = args.canary_delay
    if (debug):
        print("Got --canary_delay ", canary_delay)
else:
        canary_delay = 0
        if (debug):
            print('Set canary_delay ', canary_delay)

if(args.step_delay):
    # some type checking would be nice here
    step_delay = args.step_delay
    if (debug):
        print("Got --step_delay ", step_delay)
else:
        step_delay = 45
        if (debug):
            print('Set step_delay ', step_delay)

# may need existence check here for bulletproof, or default set in argparse            
if(args.testing_delay >= 0):
    # some type checking would be nice here
    testing_delay = args.testing_delay
    if (debug):
        print("Got --testing_delay ", testing_delay)
else:
        testing_delay = 0
if (debug):
    print('Set testing_delay ', testing_delay)

if(args.release_num_steps):
    release_num_steps = args.release_num_steps
    if (debug):
        print("Got --release_num_steps ", release_num_steps)
else:
    release_num_steps = 3
    if (debug):
        print('No release_num_steps, defaulting to 3')


## END parse args> needs func/sub

# See which service we will deploy to, the zero weight one
lb = boto3.client('elbv2')
ecs = boto3.client('ecs')

rules = lb.describe_rules(
    RuleArns=[
        rule,
    ],
    Marker='marker',
    PageSize=25
)

#pp = pprint.PrettyPrinter(indent=4)
#pp.pprint(rules)
#print(rules['Rules']['Actions']['ForwardConfig']['TargetGroups'][0])
#print(rules['Rules']['Actions']['ForwardConfig']['TargetGroups'][1])
#pp.pprint(rules["Rules"][0]['Actions'][0]['ForwardConfig']['TargetGroups'])

# setup array of dicts to have everthing we need e.g. ctx['blue']['task_def_arn'] = blah , svc, from tf vars output> ini file

# set releasing_to = 'blue|green' based on 0 weight or exit
for tg in rules['Rules'][0]['Actions'][0]['ForwardConfig']['TargetGroups']:
    print('{:3d}'.format(tg['Weight']), " % --> ",  tg['TargetGroupArn'])
    if(tg['Weight'] == 0):
        if(blue.match(tg['TargetGroupArn'])):
            new_service = 'blue'
            old_service = 'green'
        if(green.match(tg['TargetGroupArn'])):
            new_service = 'green'
            old_service = 'blue'
    
# if service is None still exit with no clear service to release to
if(new_service == None):
    sys.exit('Exiting, no clear zero weight service to release to, proceed manually maybe move this after task def update')

print('Will deploy build to the zero weight service which is: ', new_service, 'ARN: ', ctx[new_service]['svc_arn'])


# update the task definition to the new image tag
rtdr = ecs.register_task_definition(
    family=family,
    executionRoleArn=exec_role,
    networkMode='awsvpc',
    containerDefinitions=[
        {
            'name': 'apache2',
            'image': image,
            'cpu': 256,
            'memory': 512,
            "portMappings": [
                {
                    "containerPort": 80,
                    "hostPort": 80
                }
            ],
            'essential': True,
        },
    ],
    requiresCompatibilities=[
        'FARGATE',
    ],
    cpu='256',
    memory='512',
)

#print('task update response is: ', rtdr)
if(superuberdebug):
    print('uberdebug: task update response is: ')
    pp.pprint(rtdr)

new_td = rtdr['taskDefinition']['taskDefinitionArn']
if (debug):
    print('new_td = ', new_td)

## Update the 0 weight service to the new task definition
usr = ecs.update_service(
    cluster=cluster,
    service=ctx[new_service]['svc_arn'],
    desiredCount=1,
    taskDefinition=new_td,
    capacityProviderStrategy=[
        {
            'capacityProvider': 'FARGATE',
            'weight': 100,
            'base': 1
        },
    ],
    deploymentConfiguration={
        'maximumPercent': 200,
        'minimumHealthyPercent': 50
    },
    networkConfiguration={
        'awsvpcConfiguration': {
            'subnets': [
                'subnet-0b3ac8c90ce9c3126','subnet-074fc05e463ca7de2','subnet-033a6e87720fdf16d',
            ],
            'securityGroups': [
                'sg-05a15e864d696a25a',
            ],
            'assignPublicIp': 'DISABLED'
        }
    },
    platformVersion='LATEST',
    forceNewDeployment=True,
    healthCheckGracePeriodSeconds=0,
)

if(superuberdebug):
    pp.pprint(usr)

## wait for ready to test: no more draining/ACTIVE... all tasks are PRIMARY
draining = re.compile('.*ACTIVE*')
while True:
    response = ecs.describe_services(
        cluster=cluster,
        services=[
            ctx[new_service]['svc_arn'],
        ],
    )

    if (draining.match(str(response['services'][0]['deployments']))):
        if (superuberdebug):
            pp.pprint(response['services'][0]['deployments'])
        if (debug):
            print('Still draining... will sleep 5...')
        time.sleep(5)
    else:
        if (superuberdebug):
            pp.pprint(response['services'][0]['deployments'])
        if (debug):
            print('No more draining... continue to test & cutover...')
        break

## Test new svc
regex = re.compile(test_grep)

with urllib.request.urlopen(ctx[new_service]['test_url']) as resource:
    html = resource.read()

htmlstring = html.decode("utf-8")
if(regex.search(htmlstring)):
    print('Simple test, matched grep string: ', test_grep, ' in url: ', ctx[new_service]['test_url'], ' continuing to cutover')
else:
    print('Failed simple test: No match grep string: ', test_grep, ' in url: ', ctx[new_service]['test_url'], ' will exit 1 now')
    sys.exit(1)        


# no this is in the lool... maybe new testing_delay before canary option to abort in CircleCI console
## exit or canary +extra canary_delay /slow cutover of weighted rule
if (testing_delay > 0):
    if (debug):
        print('Sleeping for testing_delay = ', testing_delay, ' seconds')
    time.sleep(testing_delay)
    
## depoy_only = true exit here
if (deploy_only == True):
    if (debug):
        print('Exiting now for deploy_only mode. You can shift traffic later manually or with another CircleCI deployment.')
    sys.exit(0)


## Traffic shifting cutover loop/func
pct_change = math.floor(100/release_num_steps)
if (debug):
    print ('Setup pct_change = ', pct_change)

# setup beginning state... maybe should change new_wt to weight for clarity    
if (new_service == 'blue'):
    ctx['blue']['new_wt'] = 0
    ctx['green']['new_wt'] = 100
else:
    ctx['blue']['new_wt'] = 100
    ctx['green']['new_wt'] = 0

for x in range(1, release_num_steps + 1):

    if (x == release_num_steps):
        if (new_service == 'blue'):
            ctx['blue']['new_wt'] = 100
            ctx['green']['new_wt'] = 0
        else:
            ctx['blue']['new_wt'] = 0
            ctx['green']['new_wt'] = 100
    else:
        if (new_service == 'blue'):
            ctx['blue']['new_wt'] += pct_change
            ctx['green']['new_wt'] -= pct_change
        else:
            ctx['blue']['new_wt'] -= pct_change
            ctx['green']['new_wt'] += pct_change 

    if (debug):
        print ('Moving blue tg -> ', ctx['blue']['new_wt'], 'and moving green tg -> ', ctx['green']['new_wt'])

    mrr = lb.modify_rule(
        RuleArn=rule,
        Actions=[
            {
                'Type': 'forward',
                'ForwardConfig': {
                    'TargetGroups': [
                        {
                            'TargetGroupArn': ctx['blue']['tg_arn'],
                            'Weight': ctx['blue']['new_wt']
                        },
                        {
                            'TargetGroupArn': ctx['green']['tg_arn'],
                            'Weight': ctx['green']['new_wt']
                        },
                    ],
                    'TargetGroupStickinessConfig': {
                        'Enabled': True,
                        'DurationSeconds': 60
                    }
                }
            }
        ]
    )
        
    if(superuberdebug):
        print('Modify_rule response: ')
        pp.pprint(mrr)

    if (x == 1):
        if (canary_delay > 0):
            if (debug):
                print('First step, sleeping for extra canary_delay = ', canary_delay, ' seconds')
            time.sleep(canary_delay)

    if (x != release_num_steps):
        if (debug):
            print('Sleeping for step_delay = ', step_delay, ' seconds')
        time.sleep(step_delay)


print('All done, enjoy!')
