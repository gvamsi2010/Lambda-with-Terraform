import boto3
import json
import urllib.request
import time
from botocore.exceptions import ClientError

def get_managed_prefix_list_current_version(prefix_list_id):
    ec2 = boto3.client('ec2')
    response = ec2.describe_managed_prefix_lists(PrefixListIds=[prefix_list_id])
    
    if 'PrefixLists' in response:
        prefix_list = response['PrefixLists'][0]
        return prefix_list.get('Version')
    else:
        return None

def convert_range_to_cidrs(start_ip, end_ip):
    start_octets = list(map(int, start_ip.split('.')))
    end_octets = list(map(int, end_ip.split('.')))

    start_ip_int = (start_octets[0] << 24) + (start_octets[1] << 16) + (start_octets[2] << 8) + start_octets[3]
    end_ip_int = (end_octets[0] << 24) + (end_octets[1] << 16) + (end_octets[2] << 8) + end_octets[3]

    cidr_list = []
    while start_ip_int <= end_ip_int:
        cidr = '.'.join(map(str, [start_ip_int >> 24, (start_ip_int >> 16) & 0xFF, (start_ip_int >> 8) & 0xFF, start_ip_int & 0xFF])) + '/32'
        cidr_list.append(cidr)
        start_ip_int += 1

    return cidr_list

def get_ipv4_prefixes_for_country(country_code, date):
    url = f"https://stat.ripe.net/data/country-resource-list/data.json?resource={country_code}&time={date}"
    
    response = urllib.request.urlopen(url)
    if response.status == 200:
        data = json.loads(response.read().decode('utf-8'))
        ipv4_prefixes = data.get('data', {}).get('resources', {}).get('ipv4')
        if ipv4_prefixes:
            sorted_ipv4_prefixes = sorted(ipv4_prefixes)
            return sorted_ipv4_prefixes
        else:
            return None
    else:
        print(f"Error: {response.status} - {response.reason}")
        return None

def update_managed_prefix_list(prefix_list_id, prefixes):
    ec2 = boto3.client('ec2')

    # Split prefixes into batches of 100
    for i in range(0, len(prefixes), 100):
        batch = prefixes[i:i+100]
        entries = []
        for prefix in batch:
            if '-' in prefix:  # Check if the prefix is a range
                start_ip, end_ip = prefix.split('-')
                cidr_list = convert_range_to_cidrs(start_ip, end_ip)
                entries.extend({'Cidr': cidr} for cidr in cidr_list)
            else:
                entries.append({'Cidr': prefix})
        try:
            response = ec2.modify_managed_prefix_list(
                PrefixListId=prefix_list_id,
                CurrentVersion=get_managed_prefix_list_current_version(prefix_list_id),
                AddEntries=entries
            )
            print(f"Managed Prefix List updated with ID: {prefix_list_id} (Batch {i//100 + 1})")
        except ClientError as e:
            if e.response['Error']['Code'] == 'InvalidPrefixListModification':
                print(f"Skipped updating batch {i//100 + 1}: {e.response['Error']['Message']}")
            elif e.response['Error']['Code'] == 'InvalidParameterValue' and 'cannot contain more than 100 entry additions or removals' in e.response['Error']['Message']:
                # If the error is due to exceeding the maximum number of entries, split the batch further
                update_managed_prefix_list(prefix_list_id, batch)
            else:
                raise
        # Wait for 1 second between batches
        time.sleep(2)

    return response


def lambda_handler(event, context):
    prefix_list_id = event.get('prefix_list_id')
    prefix_list_name = event.get('prefix_list_name')

    if not prefix_list_id or not prefix_list_name:
        return {
            'statusCode': 400,
            'body': "Prefix List ID or Name is missing in the input."
        }

    country_code = event.get('country_code', 'in') 
    date = event.get('date', '2020-12-01') 

    ipv4_prefixes = get_ipv4_prefixes_for_country(country_code, date)
    if ipv4_prefixes:
        update_managed_prefix_list(prefix_list_id, ipv4_prefixes)
        return {
            'statusCode': 200,
            'body': f"Prefix List '{prefix_list_name}' updated with new prefixes."
        }
    else:
        return {
            'statusCode': 404,
            'body': "No IPv4 prefixes found for the specified country and date."
        }
