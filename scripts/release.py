#!/usr/bin/python3

import boto3
import sys
import re
import pprint
import argparse

parser = argparse.ArgumentParser(description='Perform blue-green deployment.')
parser.add_argument('--tag', help='container tag from git hash')
parser.add_argument('--rule', help='ARN of ALB rule that has the TG weights')
parser.add_argument('--svc_green', help='ARN of green service')
parser.add_argument('--svc_blue', help='ARN of blue service')
parser.add_argument('-v','--verbose', action='count', dest='log_level', default=0, help='print extra debug information')
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
service = None

# key blue/green service ARN in here, svc_name could be parameterized
ctx = {'blue':  {'svc_arn': '', 'svc_name': 'acblue'},
       'green': {'svc_arn': '', 'svc_name': 'acgreen'}}

# process_args funct or subroutine perhaps with context 
debug = 0
uberdebug = 0
if (args.log_level == 1 ):
    debug = 1
    print('Verbose mode on.')
else:
    if (args.log_level > 1):
        debug = 1
        uberdebug = 1
        print ('Uber verbose mode on.')

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
    ctx['blue']['svc_arn'] = args.svc_green
    if (debug):
        print("Got --svc_blue  = ctx['blue']['svc_arn'] = ", ctx['blue']['svc_arn'])
else:
    sys.exit('Exiting, no --svc_blue for ARN of blue ECS service supplied')
    
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
            service = 'blue'
        if(green.match(tg['TargetGroupArn'])):
            service = 'green'
    
# if service is None still exit with no clear service to release to
if(service == None):
    sys.exit('Exiting, no clear zero weight service to release to, proceed manually maybe move this after task def update')

print('Will deploy build to the zero weight service which is: ', service, 'ARN: ', ctx[service]['svc_arn'])

# prob need the blue and green service ARN's in variable / dict from TF > env > command line parameter    
#################sys.exit('Exiting, early testing')


    
# unnecessary?
#tds = ecs.list_task_definitions(
#    familyPrefix=family,
#    maxResults=35,
#)
#print(tds)
#td_arn= tds['taskDefinitionArns'][0]
#print('TD ARN is: ', td_arn)
# end unecessary?

# needs to be in a sub or func... memory/cpu could be parameterized
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
if(uberdebug):
    print('uberdebug: task update response is: ')
    pp.pprint(rtdr)

new_td = rtdr['taskDefinition']['taskDefinitionArn']
if (debug):
    print('new_td = ', new_td)

## Update the 0 weight service
usr = ecs.update_service(
    cluster=cluster,
    service=ctx[service]['svc_arn'],
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
    healthCheckGracePeriodSeconds=5
)

if(uberdebug):
    pp.pprint(usr)

## Test new svc

## exit or canary/slow cutover of weighted rule

