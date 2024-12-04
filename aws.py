import subprocess
import json
import sys
import time
from enum import Enum

import paramiko
import requests
from paramiko.ssh_exception import BadHostKeyException, AuthenticationException, SSHException, NoValidConnectionsError


class InstanceInfo(Enum):
    INSTANCE_ID = 0
    IMAGE_ID = 1
    INSTANCE_TYPE = 2
    KEY_NAME = 3
    LAUNCH_TIME = 4
    AVAILABILITY_ZONE = 5  # Placement.AvailabilityZone
    STATE_NAME = 6
    PRIVATE_IP_ADDRESS = 7
    PUBLIC_IP_ADDRESS = 8
    SUBNET_ID = 9
    VPC_ID = 10
    SECURITY_GROUPS = 11  # SecurityGroups[*].GroupName
    TAGS = 12  # Tags[*]


def read_config():
    try:
        with open('config/config.json', 'r') as file:
            data = json.load(file)
    except (FileNotFoundError, ValueError):
        write_message('Failed to load config json! Stopping the script')
        return None
    return data


def write_message(message):
    subprocess.call(f'echo {message}', shell=True)


def stop_all_spot_fleet_requests():
    command = "aws ec2 cancel-spot-fleet-requests --spot-fleet-request-ids {} --terminate-instances"
    for Id in get_all_spot_fleet_requests_ids():
        response = parse_response(command.format(Id))
        if len(response.get("SuccessfulFleetRequests")) == 0 or len(response.get("UnsuccessfulFleetRequests")) != 0:
            write_message(f'Error while terminating spot request with ID: {Id}')
        write_message(f'Terminated spot request with ID: {Id}')


def get_all_spot_fleet_requests_ids():
    command = "aws ec2 describe-spot-fleet-requests --query SpotFleetRequestConfigs[*].[SpotFleetRequestState,SpotFleetRequestId]"
    response = parse_response(command)
    output = []
    for instance in response:
        if instance[0] == "active":
            output.append(instance[1])
    write_message(f'All acitve spot fleet requests: {output}')
    return output


def get_running_instance_info(*infos: InstanceInfo):
    command = [
        "aws", "ec2", "describe-instances",
        "--filters", "Name=instance-state-name,Values=running",
        "--query",
        "Reservations[*].Instances[*].[InstanceId,ImageId,InstanceType,KeyName,LaunchTime,Placement.AvailabilityZone,State.Name,PrivateIpAddress,PublicIpAddress,SubnetId,VpcId,SecurityGroups[*].GroupName,Tags[*]]",
        "--output", "json"
    ]
    response = parse_response(command)
    output = []
    if len(response) != 0:
        response = response[0][0]
        for i in range(0, len(infos)):
            output.append(response[infos[i].value])
    return output


def check_connection_to_instance(ip):
    if isinstance(ip, list):
        ip = ip[0]
    connect_counter = 1
    while connect_counter != 6:
        try:
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh.connect(ip, username="ec2-user", key_filename=f'{config_data["key"]}', timeout=180)
            write_message(f'Success connecting using ssh on ip: {ip} ')
            return True
        except (BadHostKeyException, AuthenticationException,
                SSHException):
            write_message(f'#{connect_counter} Failed to connect using ssh on ip: {ip} ')
            connect_counter += 1
            time.sleep(30)
        except NoValidConnectionsError:
            time.sleep(5)
    write_message(f'#Fianl Failed to connect using ssh on ip: {ip} ')
    return False


def connect_to_running_instance(ip, tunneling_arg):
    if isinstance(ip, list):
        ip = ip[0]
    if check_connection_to_instance(ip):
        command = (
            f'start cmd /k "echo ssh -i \"{config_data["key"]}\" ec2-user@{ip} {tunneling_arg} && '
            f'ssh -i \"{config_data["key"]}\" ec2-user@{ip} {tunneling_arg}"'
        )
        subprocess.run(command, shell=True)

        write_message(f'Connected to: {ip} as User')
        return True
    write_message(f'Failed to connect to: {ip} as User')
    return False


def parse_response(command):
    try:
        result = subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        output = json.loads(result.stdout)
        return output
    except subprocess.CalledProcessError as e:
        write_message("Error executing AWS CLI: {e.stderr}")


def create_spot_fleet() -> bool:
    command = "aws ec2 request-spot-fleet --spot-fleet-request-config file://config/spot-fleet-config.json"
    response = parse_response(command)
    if response.get('SpotFleetRequestId') is None:
        write_message("Failed to start a fleet request")
        return False
    write_message(f'Started new spot fleet: {response.get("SpotFleetRequestId")}')
    return True


def get_sg_inbound_info(name):
    command = f'aws ec2 describe-security-groups --filters "Name=group-name,Values={name}" --query SecurityGroups[*].[GroupId]'
    write_message("Looking for security group rules")
    output = parse_response(command)
    if len(output) == 0:
        write_message("Could not find security group")
        return None
    output = output[0]
    if len(output) == 0:
        write_message("No inbound rules in this group")
        return None
    rules = []
    group_id = output[0]
    command = f'aws ec2 describe-security-group-rules  --filters "Name=group-id,Values={group_id}" --query "SecurityGroupRules[*].[SecurityGroupRuleId, IpProtocol, FromPort, ToPort, CidrIpv4, Description]"'
    output = parse_response(command)
    for rule in output:
        rules.append(
            {"rule_id": rule[0], "protocol": rule[1], "from_port": rule[2], "to_port": rule[3], "ipv4": rule[4],
             "description": rule[5]})
    write_message(f'Found group [{group_id}] with ids: {rules}')
    return group_id, rules


def update_security_group_inbound_ip():
    write_message("Updating security group inbound rools (Adding IP)")
    sg_id, sg_rules = get_sg_inbound_info(f'{config_data["sg_name"]}')
    try:
        response = requests.get("https://api.ipify.org?format=text")
        my_ip = response.text
    except Exception as e:
        write_message("Failed to find public IP of this device")
        return False

    target_rule = None
    for rule in sg_rules:
        if rule.get('description') == f'{config_data["description"]}' and rule.get('to_port') == 22:
            target_rule = rule
            if my_ip == rule.get('ipv4').split("/")[0]:
                write_message("Ip already in inbound rules")
                return True
            break

    if target_rule == None:
        write_message(f'Could not find specific rule (description == {config_data["description"]})')
        return False
    config = None
    with open('config/security-group-config-form.json', mode="r") as data:
        config = json.load(data)
        # Adding /32 to specify that I want only one ip
        config["GroupId"] = sg_id
        config["SecurityGroupRules"][0]["SecurityGroupRuleId"] = target_rule.get("rule_id")
        config["SecurityGroupRules"][0]["SecurityGroupRule"]["CidrIpv4"] = my_ip + '/32'
        config["SecurityGroupRules"][0]["SecurityGroupRule"]["Description"] = config_data["description"]

    with open('config/security-group-config.json', mode="w") as data:
        json.dump(config, data, indent=4)

    command = f'aws ec2 modify-security-group-rules --group-id {sg_id} --cli-input-json file://config/security-group-config.json'
    response = parse_response(command)
    if response == None or not response.get("Return"):
        write_message("Failed to change IP, request error!")
        return False

    write_message("Successfully changed Security Group Rule ID")
    return True


config_data = read_config()
if config_data is None:
    exit(1)

args = sys.argv
tunneling = ""

if "-t" in args:
    tunneling = '-L 8188:127.0.0.1:8188'

if '-create' in args:
    if len(get_running_instance_info(InstanceInfo.INSTANCE_ID)) > 0:
        write_message("There is already running instance!")
        exit(1)
    create_spot_fleet()

if '-connect' in args:
    counter = 1
    while True:
        if len(get_running_instance_info(InstanceInfo.PUBLIC_IP_ADDRESS)) == 0:
            write_message(f"#{counter} No running instances... waiting")
            counter += 1
            time.sleep(30)
        else:
            break
    if not update_security_group_inbound_ip():
        exit(1)
    connect_to_running_instance(get_running_instance_info(InstanceInfo.PUBLIC_IP_ADDRESS), tunneling)

if '-stop' in args:
    stop_all_spot_fleet_requests()
    write_message("Removed all instances")
