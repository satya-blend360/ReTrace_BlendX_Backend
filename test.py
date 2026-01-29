import requests


def _fetch_token():
    print("========== FETCHING TOKEN ===========")
    url = f"https://login.microsoftonline.com/b1aae949-a5ef-4815-b7af-/oauth2/v2.0/token"
    headers = {
        "Content-Type": "application/x-www-form-urlencoded"
    }
    body = {
        "client_id": "56328864-9b05-477f-9616-",
        "scope": "https://graph.microsoft.com/.default",
        "client_secret": "Gif8Q~ScPtY-ikUICaeyk5y2.~qiAcbo",
        "grant_type": "client_credentials"
    }

    response = requests.post(url, headers=headers, data=body, verify=False)

    if response.status_code == 200:
        response_data = response.json()
        access_token = response_data["access_token"]
        return access_token
    else:
        raise Exception("Fetch Access Token API Error : Failed to retrieve access token", response.text)



def add_user_to_group(user_email, group_id, access_token):
    try:
        url = f'https://graph.microsoft.com/v1.0/groups/{group_id}/members/$ref'
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        data = {
            '@odata.id': f'https://graph.microsoft.com/v1.0/users/{user_email}'
        }
        response = requests.post(url, headers=headers, json=data, verify=False)

        print(f"Group Assign : User {user_email} : to ad group {group_id}")

        if response.status_code == 204:
            status = "Success"
            response = response
        else:
            status = "Failure"
            response = response.text

        return {
            'Status': status,
            'Response': response
        }
    except Exception as e:
        print(f"Error Adding User {user_email} to ad group {group_id}")
        return {
            'Status': 'Failure',
            'Response': str(e)
        }


# Email to search
email_to_find = "indiarecruitment@Blend360.com"

url = "https://graph.microsoft.com/v1.0/groups"
params = {
    "$filter": f"mail eq '{email_to_find}'"
}

headers = {
    "Authorization": f"Bearer {_fetch_token()}",
    "Content-Type": "application/json"
}

response = requests.get(url, headers=headers, params=params)

if response.status_code == 200:
    groups = response.json().get("value", [])
    print("Found groups:")
    for g in groups:
        print(g["id"], g.get("displayName"), g.get("mail"))
else:
    print("Error:", response.status_code, response.text)