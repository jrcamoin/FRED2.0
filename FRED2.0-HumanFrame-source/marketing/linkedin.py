"""Small, review-first LinkedIn company-page posting queue."""

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


QUEUE = Path(__file__).with_name("queue.json")


def payload(organization_id, text):
    return {
        "author": f"urn:li:organization:{organization_id}",
        "commentary": text,
        "visibility": "PUBLIC",
        "distribution": {
            "feedDistribution": "MAIN_FEED",
            "targetEntities": [],
            "thirdPartyDistributionChannels": [],
        },
        "lifecycleState": "PUBLISHED",
        "isReshareDisabledByAuthor": False,
    }


def load_queue(path):
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("Queue must be a JSON array")
    return data


def save_queue(path, data):
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temporary.replace(path)


def publish(post, organization_id, token, version):
    request = Request(
        "https://api.linkedin.com/rest/posts",
        data=json.dumps(payload(organization_id, post["text"])).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "X-Restli-Protocol-Version": "2.0.0",
            "Linkedin-Version": version,
        },
        method="POST",
    )
    with urlopen(request, timeout=20) as response:
        if response.status != 201:
            raise RuntimeError(f"LinkedIn returned HTTP {response.status}")
        return response.headers.get("x-restli-id", "")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["list", "run"])
    parser.add_argument("--queue", type=Path, default=QUEUE)
    parser.add_argument("--live", action="store_true", help="Actually publish due, approved posts")
    args = parser.parse_args()
    posts = load_queue(args.queue)
    now = datetime.now(timezone.utc)
    due = []
    for post in posts:
        if not all(key in post for key in ("id", "text", "publish_at", "approved", "status")):
            raise ValueError("Every post needs id, text, publish_at, approved, and status")
        scheduled = datetime.fromisoformat(post["publish_at"].replace("Z", "+00:00"))
        if scheduled.tzinfo is None:
            raise ValueError(f"Post {post['id']} needs a timezone in publish_at")
        if post["status"] == "pending" and post["approved"] is True and scheduled <= now:
            due.append(post)
    if args.command == "list":
        for post in posts:
            print(f"{post['id']}: {post['status']}, approved={post['approved']}, at={post['publish_at']}")
        return
    for post in due:
        print(f"Due: {post['id']} — {post['text']}")
    if not args.live:
        print(f"Dry run: {len(due)} approved post(s) due. Add --live to publish.")
        return
    if not due:
        return
    organization_id = os.environ.get("LINKEDIN_ORGANIZATION_ID", "")
    token = os.environ.get("LINKEDIN_ACCESS_TOKEN", "")
    version = os.environ.get("LINKEDIN_API_VERSION", "")
    if not (organization_id.isdecimal() and token and len(version) == 6 and version.isdecimal()):
        raise ValueError("Set LINKEDIN_ORGANIZATION_ID, LINKEDIN_ACCESS_TOKEN, and LINKEDIN_API_VERSION (YYYYMM)")
    for post in due:
        try:
            post_id = publish(post, organization_id, token, version)
        except (HTTPError, URLError) as exc:
            raise RuntimeError(f"LinkedIn publish failed for {post['id']}: {exc}") from exc
        post["status"] = "published"
        post["linkedin_post_id"] = post_id
        post["published_at"] = datetime.now(timezone.utc).isoformat()
        save_queue(args.queue, posts)
        print(f"Published {post['id']}: {post_id}")


if __name__ == "__main__":
    main()
