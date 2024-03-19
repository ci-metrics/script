"""Script to use in GitHub actions with CIMetrics"""
import os
import json
import requests

ADDR = "https://cimetrics.io/"
CI_METRICS_HEADER = "### CI Metrics"
GITHUB_REPO_API = "https://api.github.com/repos/"
TIMEOUT = 10


def login():
    """Acquires session token"""
    print("Logging in")

    url = f"{ADDR}login"
    print(f"url: {url}")

    headers = {"Content-Type": "application/json"}
    print(f"headers: {headers}")

    payload = json.dumps(
        {
            "public_key": public_key,
            "private_key": private_key,
        }
    )
    print(f"payload: {payload}")

    response = requests.post(url=url, data=payload, headers=headers, timeout=TIMEOUT)
    print(f"response: {response}")
    assert response.status_code == 200

    return response.cookies


def upload(sha, data):
    """Uploads metrics"""
    print("Running upload.")

    payload = json.dumps(
        {
            "sha": sha,
            "repo": repo,
            "metrics": data,
        }
    )
    print(f"payload: {payload}")

    response = requests.post(
        url=f"{ADDR}metrics",
        data=payload,
        headers={"Content-Type": "application/json"},
        cookies=session_cookie,
        timeout=TIMEOUT,
    )
    print(f"response: {response}")
    assert response.status_code == 200


def diff():
    """Gets metrics diff between commits"""
    print("Running diff.")

    response = requests.post(
        url=f"{ADDR}commits",
        data=json.dumps({"commits": [base, head]}),
        headers={"Content-Type": "application/json"},
        cookies=session_cookie,
        timeout=TIMEOUT,
    )
    print(f"response: {response}")

    assert response.status_code == 200

    response_json = response.json()
    print(f"response_json: {response_json}")

    assert base in response_json
    assert head in response_json

    changes = {}
    commit_one = response_json[base]
    for key, value in commit_one.items():
        changes[key] = {"from": value, "to": None}

    commit_two = response_json[head]
    for key, value in commit_two.items():
        if key in changes:
            changes[key]["to"] = value
        else:
            changes[key] = {"from": None, "to": value}

    print(f"changes: {changes}")

    table_set = []
    for key, value in changes.items():
        x = value["from"]
        y = value["to"]
        if x is not None and y is not None:
            d = y - x
            pd = f"{100 * float(d) / float(x):+.2f}" if x != 0 else "NaN"
            table_set.append(
                (
                    key,
                    pd,
                    f"{d:+,}",
                    f"{x:,}",
                    f"{y:,}",
                )
            )
        else:
            table_set.append(
                (
                    key,
                    "NaN",
                    "NaN",
                    "None" if x is None else f"{x:,}",
                    "None" if y is None else f"{y:,}",
                )
            )
    print(f"table_set: {table_set}")

    # Sort diff by %
    def get_sort_key(x):
        if x[1] == "NaN":
            return float(-1)
        return abs(float(x[1]))

    table_set.sort(reverse=True, key=get_sort_key)

    print(f"table_set: {table_set}")

    table_str = "Metric|∆%|∆|Old|New\n---|--:|--:|--:|--:\n"
    for components in table_set:
        table_str += "|".join(components)
        table_str += "\n"

    return table_str


def post(table):
    """Posts a metrics comment on a PR"""
    print("Running post.")

    github_headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    # Get list of comments
    response = requests.get(
        url=f"{GITHUB_REPO_API}{repo}/issues/{issue}/comments",
        headers=github_headers,
        timeout=TIMEOUT,
    )
    print(f"response: {response}")
    assert response.status_code == 200

    response_json = response.json()
    print(f"response_json: {response_json}")

    comment_id = None
    for comment in response_json:
        if comment["body"].startswith(CI_METRICS_HEADER):
            comment_id = comment["id"]
    print(f"comment_id: {comment_id}")

    payload = json.dumps(
        {
            "body": f"{CI_METRICS_HEADER}\n{table}\n🔍 View full report in CIMetrics at \
                `{ADDR}{repo}/<your branch>/{base}/{head}`."
        }
    )

    # If CI metrics comment is not present, post it.
    if comment_id is None:
        response = requests.post(
            url=f"{GITHUB_REPO_API}{repo}/issues/{issue}/comments",
            data=payload,
            headers=github_headers,
            timeout=TIMEOUT,
        )
        print(f"response: {response}")
        assert response.status_code == 201
    # Else if CI metrics comment present, update it.
    else:
        response = requests.patch(
            url=f"{GITHUB_REPO_API}{repo}/issues/comments/{comment_id}",
            data=payload,
            headers=github_headers,
            timeout=TIMEOUT,
        )
        print(f"response: {response}")
        assert response.status_code == 200


print(f"os.environ: {os.environ}")

public_key = os.environ["PUBLIC_KEY"]
print(f"public_key: {public_key}")
private_key = os.environ["PRIVATE_KEY"]
print(f"private_key: {private_key}")
head = os.environ["HEAD"]
print(f"head: {head}")

DATA_TEXT = "DATA_TEXT"
DATA_FILE = "DATA_FILE"
REPO = "GITHUB_REPOSITORY"

data_text_opt = os.environ.get(DATA_TEXT)
print(f"data_text_opt: {data_text_opt}")
data_file_opt = os.environ.get(DATA_FILE)
print(f"data_file_opt: {data_file_opt}")
repo_opt = os.environ[REPO]
print(f"repo_opt: {repo_opt}")

session_cookie = login()

match data_text_opt, data_file_opt, repo_opt:
    case None, data_file, repo:
        with open(data_file, "r", encoding="utf-8") as file:
            data_str = file.read()
            print(f"data_str: {data_str}")
            upload(head, data_str)
    case data_text, None, repo:
        upload(head, data_text)
    case None, None, None:
        print(f"Neither `{DATA_TEXT}`, `{DATA_FILE}` or `{REPO}` set, skipping upload.")
    case data_text, data_file, _:
        raise ValueError(
            f"`{DATA_TEXT}` ({data_text}) and `{DATA_FILE}` ({data_file}) must not both be set."
        )

BASE = "BASE"
ISSUE = "ISSUE"
TOKEN = "TOKEN"

base_opt = os.environ.get(BASE)
issue_opt = os.environ.get(ISSUE)
token_opt = os.environ.get(TOKEN)

match base_opt, issue_opt, token_opt, repo_opt:
    case base, issue, token, repo:
        post(diff())
    case None, None, None, _:
        print(f"None of `{BASE}`, `{ISSUE}` or `{TOKEN}` set, skipping diff.")
    case _:
        raise ValueError(
            f"`{BASE}` ({base_opt}), `{ISSUE}` ({issue_opt}) and `{TOKEN}` ({token_opt}) must all \
                be set when any are set."
        )
