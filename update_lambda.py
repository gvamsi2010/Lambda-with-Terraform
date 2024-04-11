import boto3
import json
import urllib.request
import concurrent.futures
from datetime import date
from botocore.exceptions import ClientError

MAX_BATCH_SIZE = 100
MAX_THREADS = 10

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

def update_prefix_list_batch(ec2, prefix_list_id, current_version, entries):
    try:
        response = ec2.modify_managed_prefix_list(
            PrefixListId=prefix_list_id,
            CurrentVersion=current_version,
            AddEntries=entries
        )
        print(f"Managed Prefix List updated with ID: {prefix_list_id}")
        return response
    except ClientError as e:
        if e.response['Error']['Code'] == 'InvalidPrefixListModification':
            print(f"Skipped updating: {e.response['Error']['Message']}")
        elif e.response['Error']['Code'] == 'InvalidParameterValue' and 'cannot contain more than 100 entry additions or removals' in e.response['Error']['Message']:
            # If the error is due to exceeding the maximum number of entries, split the batch further
            print(f"Batch size exceeded. Splitting the batch further.")
            split_batches = [entries[i:i+MAX_BATCH_SIZE] for i in range(0, len(entries), MAX_BATCH_SIZE)]
            with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_THREADS) as executor:
                futures = []
                for batch in split_batches:
                    futures.append(executor.submit(update_prefix_list_batch, ec2, prefix_list_id, current_version, batch))
                for future in concurrent.futures.as_completed(futures):
                    future.result()
        else:
            raise

def lambda_handler(event, context):
    prefix_list_id = event.get('prefix_list_id')
    prefix_list_name = event.get('prefix_list_name')

    if not prefix_list_id or not prefix_list_name:
        return {
            'statusCode': 400,
            'body': "Prefix List ID or Name is missing in the input."
        }

    country_codes = ['RU', 'UA', 'CN', 'KP', 'IR', 'IQ', 'TR', 'TW']  # List of countries
    today = "2024-04-01"

    ec2 = boto3.client('ec2')

    for country_code in country_codes:
        ipv4_prefixes = get_ipv4_prefixes_for_country(country_code, today)
        if ipv4_prefixes:
            entries = []
            for prefix in ipv4_prefixes:
                if '-' in prefix:  # Check if the prefix is a range
                    start_ip, end_ip = prefix.split('-')
                    cidr_list = convert_range_to_cidrs(start_ip, end_ip)
                    entries.extend({'Cidr': cidr} for cidr in cidr_list)
                else:
                    entries.append({'Cidr': prefix})
            
            # Split entries into batches and update the prefix list
            update_prefix_list_batch(ec2, prefix_list_id, get_managed_prefix_list_current_version(prefix_list_id), entries)
        else:
            print(f"No IPv4 prefixes found for the specified country code '{country_code}' and date '{today}'. Moving to the next country...")
            continue

    return {
        'statusCode': 200,
        'body': f"Prefix List '{prefix_list_name}' updated with new prefixes for countries: {', '.join(country_codes)}."
    }
