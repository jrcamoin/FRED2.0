# HumanFrame Robotics LinkedIn posts

## Draft a post in your browser

Open `marketing/index.html` in a browser. Enter a topic and optional details, then select **Generate draft**. Review the editable text, select **Copy post**, and paste it into a new LinkedIn post. **Fill example** provides a quick test. This page runs locally and does not publish or send data to LinkedIn. A normal webpage cannot fill LinkedIn's composer directly; the copy step keeps you in control of the final post.

## Optional API posting queue

Keep this separate from the robot server: the `marketing/` directory holds a small company-page posting queue. Nothing is published until a post is marked `approved: true`, its UTC `publish_at` time has arrived, and the runner is invoked with `--live`. The example copy is a starting draft; check every public claim before approving it.

1. Copy `queue.example.json` to `queue.json` and edit the text and date. `queue.json` is ignored by Git.
2. Create a LinkedIn developer app with access to `w_organization_social`, authorize a member who can post for the company page, and obtain a member OAuth access token. Find the page's numeric organization ID. LinkedIn's [Posts API](https://learn.microsoft.com/en-us/linkedin/marketing/community-management/shares/posts-api) and [access guide](https://learn.microsoft.com/en-us/linkedin/marketing/increasing-access) describe these requirements.
3. Set `LINKEDIN_ORGANIZATION_ID`, `LINKEDIN_ACCESS_TOKEN`, and `LINKEDIN_API_VERSION` in the runner's environment. Choose a currently supported `YYYYMM` version from LinkedIn's documentation; tokens expire and must be renewed through the authorized OAuth flow. Never commit tokens.
4. Review with `python3 marketing/linkedin.py list` and `python3 marketing/linkedin.py run`. When ready, run `python3 marketing/linkedin.py run --live` manually once. The returned LinkedIn post ID is recorded in the queue.

For scheduled posting, invoke `python3 /absolute/path/to/marketing/linkedin.py run --live` from a dedicated scheduler (such as cron or a CI job) after providing its environment variables securely. Running it every 15 minutes publishes only due, approved, pending entries. A failed API request leaves the entry pending for inspection and retry. Avoid simultaneous runners against the same queue file.

This first version handles text posts only. It does not generate copy or scrape LinkedIn. Add drafts to the queue as needed and approve them before publishing.
