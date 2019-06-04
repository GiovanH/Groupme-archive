#!/bin/python3

"""
curl 'https://api.groupme.com/v3/groups/47158453/
messages?acceptFiles=1&before_id=155043683618610791&limit=100'
-H 'Origin: https://web.groupme.com'
-H 'Accept-Encoding: gzip, deflate, br'
-H 'Accept-Language: en-US,en;q=0.9'
-H 'User-Agent: Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/72.0.3626.82 Safari/537.36 Vivaldi/2.3.1440.41'
-H 'Accept: application/json, text/plain, */*'
-H 'Referer: https://web.groupme.com/'
-H 'Connection: keep-alive'
-H 'X-Access-Token: X09Hwlcj6LUH8O2STHquJ7xJZD4plY9MAGrFTJ1Q'
-H 'DNT: 1' --compressed
"""

import requests
import json
from slugify import slugify
import selenium_login


mtot_fields = ['created_at', 'name', 'text']


def mtot(m):
    return tuple(m.get(f) for f in mtot_fields)


def timestamp():
    import datetime
    """Just give a human-readable timestamp.
    Format is %Y-%m-%d %I:%M%p, i.e. "2018-01-02 9:12 PM"
    
    Returns:
        str: Timestamp
    """
    return datetime.datetime.now().strftime("%Y-%m-%d %I-%M%p")


class GroupMe(object):
    """docstring for GroupMe"""

    def __init__(self, access_token):
        super(GroupMe, self).__init__()
        self.access_token = access_token
        self._groups = None

    def apiGet(self, apibase, api_params, **kwargs):
        apibase_formatted = apibase.format(
            params="&".join(
                [
                    "{}={}".format(k, api_params[k])
                    for k in api_params
                ]
            ),
            **kwargs
        )
        # print(apibase, api_params, kwargs, apibase_formatted)
        return requests.get(
            apibase_formatted,
            headers={'X-Access-Token': self.access_token}
        )

    @property
    def groups(self):
        if not self._groups:
            self._groups = self.getGenericApi('groups')
        return self._groups

    def dumpChat(self, group_id):
        import os

        (this_group_name,) = [g['name'] for g in self.groups if g['group_id'] == group_id]

        folder = group_id + " " + slugify(this_group_name)  # + " " + timestamp()
        os.makedirs(folder, exist_ok=True)
        jsonpath = os.path.join(folder, "group_{}_{}.json".format(group_id, timestamp()))

        # message_api_base = "https://api.groupme.com/v3/groups/{group_id}/messages?{params}"
        # api_params = {
        #     'acceptFiles': 1,
        #     'limit': 100
        # }
        # first = self.apiGet(message_api_base, api_params, group_id=group_id)
        # first_timestamp = first.json()['response']['messages'][0]['created_at']
        # last_timestamp = json.load(open(jsonpath))

        messages = self.getAllMessages(group_id)

        json.dump(messages, open(jsonpath, "w"), indent=2)

        sm = sorted([mtot(m) for m in messages])

        with open(os.path.join(folder, "messages_{}.csv".format(timestamp())), "w", encoding='utf-8') as csv:
            csv.write(",".join(mtot_fields) + "\n")
            csv.writelines(",".join(map(lambda m: '"{}"'.format(m), msg)) + "\n" for msg in sm)

        filedir = os.path.join(folder, "files")
        os.makedirs(filedir, exist_ok=True)
        for message in messages:
            for attachment in message.get("attachments"):
                url = attachment.get('url')
                if not url:
                    continue
                outfile = os.path.join(filedir, "{4}.{3}".format(*url.split(".")))
                if os.path.exists(outfile):
                    continue
                print("#", end="")
                response = requests.get(url, stream=True)
                response.raise_for_status()
                with open(outfile, 'wb') as handle:
                    for block in response.iter_content(1024):
                        handle.write(block)

        print("#")

    def getGenericApi(self, page):

        # messages = set()
        messages = []

        page_no = 1
        generic_get_base = "https://api.groupme.com/v3/" + page + "?{params}"

        while True:

            api_params = {
                'page': page_no,
                'per_page': 100
            }

            try:
                resp = self.apiGet(generic_get_base, api_params)
                if resp.status_code != 200:
                    break
                metacode = resp.json().get('meta').get("code")
                if metacode != 200:
                    break
                resp_json = resp.json().get('response')
                if not resp_json:
                    break
            except Exception:
                import traceback
                traceback.print_exc()
                break
            # messages.update([mtot(m) for m in resp_json.get('messages')])
            messages += resp_json
            page_no += 1
            print("#", end="")

        print("#")
        return messages

    def getAllMessages(self, group_id, limit=None):
        # messages = set()
        messages = []
        message_api_base = "https://api.groupme.com/v3/groups/{group_id}/messages?{params}"
        downloaded = 0
        api_params = {
            'acceptFiles': 1,
            'limit': 100
        }
        first = self.apiGet(message_api_base, api_params, group_id=group_id)
        resp = first
        while True:

            try:
                if resp.status_code != 200:
                    break
                resp_json = resp.json().get('response')
            except Exception:
                import traceback
                traceback.print_exc()
                break
            # messages.update([mtot(m) for m in resp_json.get('messages')])
            messages += resp_json.get('messages')

            before_id = resp_json.get('messages')[-1].get('id')
            downloaded += resp_json.get('count')
            # print(resp_json.get('messages')[-1])
            api_params = {
                'acceptFiles': 1,
                'limit': 100,
                'before_id': before_id
            }
            resp = self.apiGet(message_api_base, api_params, group_id=group_id)
            print("#", end="")

        print("#")
        return messages


if __name__ == "__main__":
    import argparse

    args = argparse.ArgumentParser()
    args.add_argument("--all", action="store_true")
    args.add_argument("--group_ids", nargs="+", default=[])
    args = args.parse_args()

    sessiondata = selenium_login.login(
        "https://groupme.com/signin",
        lambda browser: browser.current_url == "https://web.groupme.com/chats"
    )

    access_token = sessiondata.get("cookies").get("token")

    groupme = GroupMe(access_token)

    group_ids_to_save = args.group_ids
    if args.all:
        all_groups = groupme.getGenericApi('groups')
        group_ids_to_save += [g['group_id'] for g in all_groups]

    for group_id in group_ids_to_save:
        print("Saving group", group_id)
        groupme.dumpChat(group_id)
