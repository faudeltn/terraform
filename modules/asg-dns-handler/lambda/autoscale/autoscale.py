import json
import logging
import boto3
import sys
import os

logger = logging.getLogger()
logger.setLevel(logging.INFO)

autoscaling = boto3.client('autoscaling')
ec2 = boto3.client('ec2')
route53 = boto3.client('route53')

HOSTNAME_TAG_NAME = "asg:hostname_pattern"
ZONE_ID = os.environ['ZONE_ID']
LIFECYCLE_KEY = "LifecycleHookName"
ASG_KEY = "AutoScalingGroupName"
DOMAIN = os.environ['DOMAIN']

def fetch_private_ip_from_ec2(instance_id):
    logger.info("Fetching private IP for instance-id: %s", instance_id)
    ec2_response = ec2.describe_instances(InstanceIds=[instance_id])
    logger.info("EC2 RESPONSE: %s", ec2_response)
    ip_address = ec2_response['Reservations'][0]['Instances'][0]['NetworkInterfaces'][0]['PrivateIpAddress']
    logger.info("Found private IP for instance-id %s: %s", instance_id, ip_address)
    return ip_address
    
def getRecordAIP(hostname):
    response = route53.list_resource_record_sets(
        StartRecordName=hostname,
        StartRecordType='A',
        HostedZoneId=ZONE_ID,
    )
    logger.info("Record A IP: %s", response)
    ip = None
    for response in response['ResourceRecordSets']:
        logger.info("Response: %s", response)
        logger.info("ResourceRecords: %s",response['ResourceRecords'])
        name = response['Name'][:-1]
        if name == hostname and response['Type'] == 'A':
            logger.info("Hostname: %s",hostname)
            record = response['ResourceRecords'][0]
            logger.info("Record A: %s", record['Value'])
            ip = record['Value']
    logger.info("Return Record A: %s", ip)
    return ip

def update_record(hostname, value, operation):
 logger.info("VALUE: %s", value)
 logger.info("Changing record with %s for %s -> %s in %s", operation, hostname, value, ZONE_ID)
 route53.change_resource_record_sets(
    HostedZoneId=ZONE_ID,
    ChangeBatch={
        'Changes': [
            {
                'Action': operation,
                'ResourceRecordSet': {
                    'Name': hostname,
                    'Type': 'A',
                    'TTL': 300,
                    'ResourceRecords': [
                        {
                            'Value': value
                        }
                    ]
                }
            }
        ]
    }
 )

def process_message(message):
    if LIFECYCLE_KEY in message and ASG_KEY in message:
        logger.info("Processing event: %s ", message['LifecycleTransition'] )
        if message['LifecycleTransition'] == "autoscaling:EC2_INSTANCE_LAUNCHING":
            operation = "UPSERT"
        elif message['LifecycleTransition'] == "autoscaling:EC2_INSTANCE_TERMINATING" or message['LifecycleTransition'] == "autoscaling:EC2_INSTANCE_LAUNCH_ERROR":
            operation = "DELETE"
        else:
            logger.error("Encountered unknown event type: %s", message['LifecycleTransition'])
        if operation == "DELETE":
            asg_name = message['AutoScalingGroupName']
            instance_id =  message['EC2InstanceId']
            #value = fetch_private_ip_from_ec2(instance_id)
            #logger.info("EC2 PRIVATE IP: %s", value)
            #value = ''.join(value.split())
            hostname = str( asg_name + '-' + instance_id + '.' + DOMAIN ) 
            logger.info("Hostname to remove: %s", hostname)
            record_to_delete = getRecordAIP(hostname)
            logger.info("Record to delete: %s", record_to_delete)
            update_record(hostname, record_to_delete, operation)
        elif operation == "UPSERT":
            asg_name = message['AutoScalingGroupName']
            instance_id =  message['EC2InstanceId']
            hostname = str( asg_name + '-' + instance_id + '.' + DOMAIN ) 
            logger.info("Hostname to add: %s", hostname)
            private_ip = fetch_private_ip_from_ec2(instance_id)
          # update_record(hostname, private_ip, operation) # Moved to the user-data script
    else:
        logger.error("No valid JSON message to process") 

def process_record(record):
    process_message(json.loads(record['Sns']['Message']))

def lambda_handler(event, context):
    #logger.info("Processing SNS event: " + json.dumps(event))
    for record in event['Records']:
        process_record(record)
        
    logger.info("Finishing ASG action")
    message =json.loads(record['Sns']['Message'])
    if LIFECYCLE_KEY in message and ASG_KEY in message :
        response = autoscaling.complete_lifecycle_action (
            LifecycleHookName = message['LifecycleHookName'],
            AutoScalingGroupName = message['AutoScalingGroupName'],
            InstanceId = message['EC2InstanceId'],
            LifecycleActionToken = message['LifecycleActionToken'],
            LifecycleActionResult = 'CONTINUE'
        )
        logger.info("ASG action complete: %s", response)    
    #else:
    #    logger.error("No valid JSON message")        

if __name__ == "__main__":
    logging.basicConfig()
    lambda_handler(json.load(sys.stdin), None)
