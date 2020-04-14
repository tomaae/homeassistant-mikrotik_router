# Original code created by @ludeeus

import re
import sys
from github import Github

BODY = """

{changes}
"""

CHANGES = """
## Changes

{integration_changes}

"""

CHANGE = "- [{line}]({link}) @{author}\n"
NOCHANGE = "_No changes in this release._"

GITHUB = Github(sys.argv[2])


def new_commits(repo, sha):
    """Get new commits in repo."""
    from datetime import datetime

    dateformat = "%a, %d %b %Y %H:%M:%S GMT"
    release_commit = repo.get_commit(sha)
    since = datetime.strptime(release_commit.last_modified, dateformat)
    commits = repo.get_commits(since=since)
    if len(list(commits)) == 1:
        return False
    return reversed(list(commits)[:-1])


def last_integration_release(github, skip=True):
    """Return last release."""
    repo = github.get_repo("tomaae/homeassistant-mikrotik_router")
    tag_sha = None
    data = {}
    tags = list(repo.get_tags())
    reg = "(v|^)?(\\d+\\.)?(\\d+\\.)?(\\*|\\d+)$"
    if tags:
        for tag in tags:
            tag_name = tag.name
            if re.match(reg, tag_name):
                tag_sha = tag.commit.sha
                if skip:
                    skip = False
                    continue
                break
    data["tag_name"] = tag_name
    data["tag_sha"] = tag_sha
    return data


def get_integration_commits(github, skip=True):
    changes = ""
    repo = github.get_repo("tomaae/homeassistant-mikrotik_router")
    commits = new_commits(repo, last_integration_release(github, skip)["tag_sha"])

    if not commits:
        changes = NOCHANGE
    else:
        for commit in commits:
            msg = repo.get_git_commit(commit.sha).message
            if "flake" in msg:
                continue
            if " workflow" in msg:
                continue
            if " test" in msg:
                continue
            if "docs" in msg:
                continue
            if "dev debug" in msg:
                continue
            if "Merge branch " in msg:
                continue
            if "Merge pull request " in msg:
                continue
            if "\n" in msg:
                msg = msg.split("\n")[0]
            changes += CHANGE.format(
                line=msg, link=commit.html_url, author=commit.author.login
            )

    return changes


# Update release notes:
UPDATERELEASE = str(sys.argv[4])
REPO = GITHUB.get_repo("tomaae/homeassistant-mikrotik_router")
if UPDATERELEASE == "yes":
    VERSION = str(sys.argv[6]).replace("refs/tags/", "")
    RELEASE = REPO.get_release(VERSION)
    RELEASE.update_release(
        name=f"Mikrotik Router {VERSION}",
        message=BODY.format(
            version=VERSION,
            changes=CHANGES.format(
                integration_changes=get_integration_commits(GITHUB),
            ),
        ),
    )
else:
    integration_changes = get_integration_commits(GITHUB, False)
    if integration_changes != NOCHANGE:
        VERSION = last_integration_release(GITHUB, False)["tag_name"]
        VERSION = f"{VERSION[:-1]}{int(VERSION[-1])+1}"
        REPO.create_issue(
            title=f"Create release {VERSION}?",
            labels=["New release"],
            assignee="tomaae",
            body=CHANGES.format(integration_changes=integration_changes,),
        )
    else:
        print("Not enough changes for a release.")
