import csv
import sys

from requests import get
from requests import post
from argparse import ArgumentParser
from pathlib import Path
from time import sleep
from config import *

URL = 'https://api360.yandex.net'
FETCH_RATE = 0.1

headers = {
    "Authorization": f"OAuth {TOKEN}",
    "content-type": "application/json",
}

parser = ArgumentParser()
parser.add_argument("-f", "--file", dest="input_file", default='delegate_in.csv',
                    help="Input csv file to process")
parser.add_argument("-q", "--query", dest="query_mode", default=False,
                    action="store_true", help="Query current configuration")
args = parser.parse_args()

MESSAGES = {
    "connection_error": "Can't connect to org. Please check configuration and scope access rights",
    "key_error": "Cannot process response from server"
}

duplicate_found = False


def count_pages():
    """Get number of pages in users list response"""

    print(f"Counting users pages for organization: {ORG_ID}")
    path = URL + f"/directory/v1/org/{ORG_ID}/users?page=1&perPage={PER_PAGE}"
    response = get(path, headers=headers)
    if response.status_code == 200:
        response_json = response.json()
        try:
            pages_count = response_json['pages']
            print(f"Users pages in response: {pages_count}")
            return pages_count
        except KeyError:
            raise KeyError(MESSAGES['key_error'])
    else:
        raise ConnectionError(MESSAGES['connection_error'])


def fetch_all_users(total_pages):
    """Fetch all users per page."""
    users = []
    for page in range(1, total_pages + 1):
        users.extend(fetch_users_by_page(page))
        sleep(FETCH_RATE)
    print(f"Total fetched users: {len(users)}")
    return users


def fetch_users_by_page(page):
    """Fetch all users from exact page"""

    print(f"Fetching users page {page}")
    path = URL + f"/directory/v1/org/{ORG_ID}/users?page={page}&perPage={PER_PAGE}"

    response = get(path, headers=headers)
    if response.status_code == 200:
        response_json = response.json()
        try:
            users = []
            for org_user in response_json['users']:
                user_id = org_user['id']
                email = org_user['email']
                users.append({'user_id': user_id, 'email': email})

            return users
        except KeyError:
            raise KeyError(MESSAGES['key_error'])
    else:
        raise ConnectionError(MESSAGES['connection_error'])


def check_request_parameters():
    """Function will check if input file is provided as -f parameter and if not will try to open default file.
    Will not tess file in -q Query mode"""
    if not args.query_mode:
        input_file = Path(args.input_file)
        if not input_file.is_file():
            raise FileNotFoundError(f'Input file {input_file} not found')
        else:
            print(f'Users will be loaded from {input_file} file')


def get_delegate_mailboxes():
    mailboxes = []

    with open(args.input_file, encoding='utf-8') as input_csv:
        reader = csv.reader(input_csv, delimiter=",")
        count = 0
        for in_row in reader:
            if count == 0:
                # print(f'Input file columns: {", ".join(row)}')
                print(f'Reading delegate config from input file')
            else:
                try:
                    # print(f"Processing record {count} record {in_row[0]}")
                    mailboxes.append(
                        {'resource_mail': in_row[0],
                         'actor_mail': in_row[1],
                         'imap_full_access': in_row[2] == 'true',
                         'send_as': in_row[3] == 'true',
                         'send_on_behalf': in_row[4] == 'true'}
                    )
                except IndexError:
                    raise IndexError(f"Incorrect input file: {args.input_file}")

            count += 1
        print(f'Input file records count: {count}')
    return mailboxes


def map_delegate_config(processed_users, delegate_mailboxes):
    delegate_config = []
    for delegate_mailbox in delegate_mailboxes:
        resource_id = ''
        actor_id = ''

        for y_user in processed_users:
            # print(f'y_user {y_user}')
            if y_user['email'] == delegate_mailbox['actor_mail']:
                # print(f'Email {y_user['email']}: user_id: {y_user['user_id']}')
                actor_id = y_user['user_id']
            if y_user['email'] == delegate_mailbox['resource_mail']:
                resource_id = y_user['user_id']

        if (len(resource_id) > 0) and (len(actor_id) > 0):
            delegate_config.append(
                {
                    "resource_mail": delegate_mailbox['resource_mail'],
                    "resource_id": resource_id,
                    "actor_mail": delegate_mailbox['actor_mail'],
                    "actor_id": actor_id,
                    "imap_full_access": delegate_mailbox['imap_full_access'],
                    "send_as": delegate_mailbox['send_as'],
                    "send_on_behalf": delegate_mailbox['send_on_behalf']
                }
            )
        else:
            print(
                f"No userId found for record: {delegate_mailbox['resource_mail']} -> {delegate_mailbox['actor_mail']}")
    return delegate_config


def map_users_csv(org_all_users):
    delegate_mailboxes = get_delegate_mailboxes()
    processed_users = []
    for org_user in org_all_users:
        for delegate_mailbox in delegate_mailboxes:
            if (org_user['email'] == delegate_mailbox['resource_mail']
                    or org_user['email'] == delegate_mailbox['actor_mail']):
                processed_users.append(org_user)
    return map_delegate_config(processed_users, delegate_mailboxes)


def get_actor_delegations(delegate_config):
    global duplicate_found
    for delegate_record in delegate_config:
        actor_id = delegate_record['actor_id']
        path = URL + f"/admin/v1/org/{ORG_ID}/mail/delegated/{actor_id}/resources"
        response = get(path, headers=headers)
        if response.status_code == 200:
            response_json = response.json()
            try:
                for resource in response_json['resources']:
                    resource_id = resource['resourceId']
                    if resource_id == delegate_record['resource_id']:
                        duplicate_found = True
                        print(f"Found existing record: {delegate_record['resource_mail']} "
                              f"({delegate_record['resource_id']}) "
                              f"-> {delegate_record['actor_mail']} ({delegate_record['actor_id']})")

            except KeyError:
                raise KeyError(MESSAGES['key_error'])
        else:
            raise ConnectionError(MESSAGES['connection_error'])
        sleep(FETCH_RATE)


def get_resource_delegations(users):
    delegate_records = []
    for user in users:
        resource_id = user['user_id']
        path = URL + f"/admin/v1/org/{ORG_ID}/mail/delegated/{resource_id}/actors"
        response = get(path, headers=headers)

        if response.status_code == 200:
            response_json = response.json()
            actors = response_json['actors']
            if len(actors) > 0:
                delegate_record = {}
                for actor in actors:
                    actor_email = ""
                    for actor_user in users:
                        if actor['actorId'] == actor_user['user_id']:
                            actor_email = actor_user['email']
                            break
                    print(f"Resource: ID: {resource_id} Email: {user['email']} -> Actor: ID: {actor['actorId']} "
                          f"Email: {actor_email} Rights: ", end=' ')
                    delegate_record['resourceId'] = resource_id
                    delegate_record['resourceEmail'] = user['email']
                    delegate_record['actorId'] = actor['actorId']
                    delegate_record['actorEmail'] = actor_email
                    delegate_record['ImapFullAccess'] = False
                    delegate_record['SendAs'] = False
                    delegate_record['SendOnBehalf'] = False

                    rights = actor['rights']
                    for right in rights:
                        if right == "imap_full_access":
                            delegate_record['ImapFullAccess'] = True
                        elif right == "send_as":
                            delegate_record['SendAs'] = True
                        elif right == "send_on_behalf":
                            delegate_record['SendOnBehalf'] = True

                        print(right, end=' ')
                    print(end="\n")
                delegate_records.append(delegate_record)

        sleep(FETCH_RATE)
    return delegate_records


def post_delegation_config(delegate_config):
    for delegate_record in delegate_config:
        print(f"Processing record: {delegate_record['resource_mail']} "
              f"({delegate_record['resource_id']}) "
              f"-> {delegate_record['actor_mail']} ({delegate_record['actor_id']})", end=' ')
        path = URL + (f"/admin/v1/org/{ORG_ID}/mail/delegated?resourceId="
                      f"{delegate_record['resource_id']}&actorId={delegate_record['actor_id']}")
        rights = []
        if delegate_record['imap_full_access']:
            rights.append("imap_full_access")
        if delegate_record['send_as']:
            rights.append("send_as")
        if delegate_record['send_on_behalf']:
            rights.append("send_on_behalf")
        body = {"rights": rights}

        response = post(path, headers=headers, json=body)
        if response.status_code == 200:
            response_json = response.json()
            try:
                print(f"Ok. taskId: {response_json['taskId']}")

            except KeyError:
                raise KeyError(MESSAGES['key_error'])
        else:
            print(f"Response code: {response.status_code}")
            raise ConnectionError(MESSAGES['connection_error'])
        sleep(FETCH_RATE)


def save_records_to_csv(delegate_records):
    with open('current_records.csv', 'w', newline='') as f:
        keys = delegate_records[0].keys()
        w = csv.DictWriter(f, keys)
        w.writeheader()
        w.writerows(delegate_records)


if __name__ == '__main__':

    if not args.query_mode:
        try:
            check_request_parameters()
            pages = count_pages()
            all_users = fetch_all_users(pages)
            config = map_users_csv(all_users)
            print(f"Records ready to process: {len(config)}")
            for row in config:
                print(f"{row['resource_mail']} ({row['resource_id']}) -> {row['actor_mail']} ({row['actor_id']}) -> "
                      f"{row['imap_full_access']} |  {row['send_as']} | {row['send_on_behalf']}")

            get_actor_delegations(config)
            if len(config) > 0:
                if duplicate_found:
                    print("Duplicate records will be replaced")
                start = input('Configure mailbox delegation in your organization? (y/n): ')
                if start.lower() == 'y':
                    post_delegation_config(config)
                    print("Done")
            else:
                print("Nothing to do...")

        except Exception as err:
            print(f"{err}")
            sys.exit(1)
    else:
        pages = count_pages()
        all_users = fetch_all_users(pages)
        records = get_resource_delegations(all_users)
        save_records_to_csv(records)
