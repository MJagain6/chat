<div align="center">
  <h1>ChatMock
  <div align="center">
<a href="https://github.com/RayBytes/ChatMock/stargazers"><img src="https://img.shields.io/github/stars/RayBytes/ChatMock" alt="Stars Badge"/></a>
<a href="https://github.com/RayBytes/ChatMock/network/members"><img src="https://img.shields.io/github/forks/RayBytes/ChatMock" alt="Forks Badge"/></a>
<a href="https://github.com/RayBytes/ChatMock/pulls"><img src="https://img.shields.io/github/issues-pr/RayBytes/ChatMock" alt="Pull Requests Badge"/></a>
<a href="https://github.com/RayBytes/ChatMock/issues"><img src="https://img.shields.io/github/issues/RayBytes/ChatMock" alt="Issues Badge"/></a>
<a href="https://github.com/RayBytes/ChatMock/graphs/contributors"><img alt="GitHub contributors" src="https://img.shields.io/github/contributors/RayBytes/ChatMock?color=2b9348"></a>
<a href="https://github.com/RayBytes/ChatMock/blob/master/LICENSE"><img src="https://img.shields.io/github/license/RayBytes/ChatMock?color=2b9348" alt="License Badge"/></a>
</div>
  </h1>
  
  <p><b>OpenAI & Ollama compatible API powered by your ChatGPT plan.</b></p>
  <p>Use your ChatGPT Plus/Pro account to call OpenAI models from code or alternate chat UIs.</p>
  <br>
</div>

## What It Does

ChatMock runs a local server that creates an OpenAI/Ollama compatible API, and requests are then fulfilled using your authenticated ChatGPT login with the oauth client of Codex, OpenAI's coding CLI tool. This allows you to use GPT-5, GPT-5-Codex, and other models right through your OpenAI account, without requiring an api key. You are then able to use it in other chat apps or other coding tools. <br>
This does require a paid ChatGPT account.

## Quickstart

### Mac Users

#### GUI Application

If you're on **macOS**, you can download the GUI app from the [GitHub releases](https://github.com/RayBytes/ChatMock/releases).  
> **Note:** Since ChatMock isn't signed with an Apple Developer ID, you may need to run the following command in your terminal to open the app:
>
> ```bash
> xattr -dr com.apple.quarantine /Applications/ChatMock.app
> ```
>
> *[More info here.](https://github.com/deskflow/deskflow/wiki/Running-on-macOS)*

#### Command Line (Homebrew)

You can also install ChatMock as a command-line tool using [Homebrew](https://brew.sh/):
```
brew tap RayBytes/chatmock
brew install chatmock
```

### Python
If you wish to just simply run this as a python flask server, you are also freely welcome too.

Clone or download this repository, then cd into the project directory. Then follow the instrunctions listed below.

1. Sign in with your ChatGPT account and follow the prompts
```bash
python chatmock.py login
```
You can make sure this worked by running `python chatmock.py info`

2. After the login completes successfully, you can just simply start the local server

```bash
python chatmock.py serve
```
Then, you can simply use the address and port as the baseURL as you require (http://127.0.0.1:8000 by default)

**Reminder:** When setting a baseURL in other applications, make you sure you include /v1/ at the end of the URL if you're using this as a OpenAI compatible endpoint (e.g http://127.0.0.1:8000/v1)

### Multi-account round-robin (single ChatMock process)

ChatMock can rotate across multiple ChatGPT accounts from one running server.

1. Prepare multiple `auth.json` files (one per account).
2. Set `CHATGPT_LOCAL_AUTH_FILES` to a comma-separated list of those files.
3. Start `serve` as usual.

Example:

```bash
CHATGPT_LOCAL_AUTH_FILES=/data/acc1/auth.json,/data/acc2/auth.json python chatmock.py serve
```

Behavior:
- Round-robin account selection per request.
- Automatic failover to the next account on `401/403/429/5xx`.
- Request-level retry rounds (`CHATGPT_LOCAL_REQUEST_RETRY`, default `3`).
- Exponential backoff between rounds with cooldown (`CHATGPT_LOCAL_MAX_RETRY_INTERVAL`, default `30s`).
- Routing strategy configurable by `CHATGPT_LOCAL_ROUTING_STRATEGY=round-robin|random|first`.
- Backward compatible with single-account mode when `CHATGPT_LOCAL_AUTH_FILES` is unset.

### Built-in Dashboard

ChatMock now includes a web dashboard inspired by the openclaw control panel.

- URL: `http://127.0.0.1:8000/dashboard`
- APIs: `/api/health`, `/api/accounts`, `/api/models`, `/api/config`, `/api/logs`

Optional env vars:
- `CHATMOCK_DASHBOARD_LOG_PATH`: log file path used by `/api/logs`
- `CHATMOCK_SERVICE_NAME`: if set, enables service start/stop/restart buttons via `systemctl`
- `CHATMOCK_DASHBOARD_ALLOW_UPLOAD`: set `0` to disable dashboard credential upload API
- `CHATMOCK_DASHBOARD_AUTH_DIR`: where uploaded `auth.json` files are stored (default `/tmp/chatmock-accounts`)

### Docker

Read [the docker instrunctions here](https://github.com/RayBytes/ChatMock/blob/main/DOCKER.md)

### Render (cloud deploy)

You can deploy ChatMock to Render as a Python web service.

1. Push this repo to GitHub.
2. In Render, create a **Web Service** from your repo.
3. Render will detect `render.yaml` automatically (or set manually):
   - Build command: `pip install -r requirements.txt`
   - Start command: `bash scripts/render-start.sh`
4. Add env vars in Render:
   - `CHATMOCK_AUTH_JSONS_BASE64` (recommended, multi-account)
   - Optional proxy vars if needed: `HTTP_PROXY`, `HTTPS_PROXY`, `ALL_PROXY`, `NO_PROXY`

#### Build `CHATMOCK_AUTH_JSONS_BASE64` from local auth files

Run this locally in your ChatMock folder (PowerShell):

```powershell
python -c "import base64, pathlib; files=['acc01/auth.json','acc03/auth.json','acc04/auth.json','acc05/auth.json']; print(','.join(base64.b64encode(pathlib.Path(f).read_bytes()).decode() for f in files))"
```

Copy the output string into Render env var `CHATMOCK_AUTH_JSONS_BASE64`.

After deploy, your endpoint is:

- Base URL: `https://<your-render-service>.onrender.com/v1`
- API key: any non-empty string

# Examples

### Python 

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://127.0.0.1:8000/v1",
    api_key="key"  # ignored
)

resp = client.chat.completions.create(
    model="gpt-5",
    messages=[{"role": "user", "content": "hello world"}]
)

print(resp.choices[0].message.content)
```

### curl

```bash
curl http://127.0.0.1:8000/v1/chat/completions \
  -H "Authorization: Bearer key" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-5",
    "messages": [{"role":"user","content":"hello world"}]
  }'
```

# What's supported

- Tool/Function calling 
- Vision/Image understanding
- Thinking summaries (through thinking tags)
- Thinking effort

## Notes & Limits

- Requires an active, paid ChatGPT account.
- Some context length might be taken up by internal instructions (but they dont seem to degrade the model) 
- Use responsibly and at your own risk. This project is not affiliated with OpenAI, and is a educational exercise.

# Supported models
- `gpt-5`
- `gpt-5.1`
- `gpt-5.2`
- `gpt-5-codex`
- `gpt-5.2-codex`
- `gpt-5.3-codex`
- `gpt-5.1-codex`
- `gpt-5.1-codex-max`
- `gpt-5.1-codex-mini`
- `codex-mini`

# Customisation / Configuration

### Thinking effort

- `--reasoning-effort` (choice of minimal,low,medium,high,xhigh)<br>
GPT-5 has a configurable amount of "effort" it can put into thinking, which may cause it to take more time for a response to return, but may overall give a smarter answer. Applying this parameter after `serve` forces the server to use this reasoning effort by default, unless overrided by the API request with a different effort set. The default reasoning effort without setting this parameter is `medium`.<br>
    The `gpt-5.1` family (including codex) supports `low`, `medium`, and `high` while `gpt-5.1-codex-max` adds `xhigh`. The `gpt-5.2` and `gpt-5.3` families (including codex) support `low`, `medium`, `high`, and `xhigh`. 

### Thinking summaries

- `--reasoning-summary` (choice of auto,concise,detailed,none)<br>
Models like GPT-5 do not return raw thinking content, but instead return thinking summaries. These can also be customised by you.

### OpenAI Tools

- `--enable-web-search`<br>
You can also access OpenAI tools through this project. Currently, only web search is available.
You can enable it by starting the server with this parameter, which will allow OpenAI to determine when a request requires a web search, or you can use the following parameters during a request to the API to enable web search:
<br><br>
`responses_tools`: supports `[{"type":"web_search"}]` / `{ "type": "web_search_preview" }`<br>
`responses_tool_choice`: `"auto"` or `"none"`

#### Example usage
```json
{
  "model": "gpt-5",
  "messages": [{"role":"user","content":"Find current METAR rules"}],
  "stream": true,
  "responses_tools": [{"type": "web_search"}],
  "responses_tool_choice": "auto"
}
```

### Expose reasoning models

- `--expose-reasoning-models`<br>
If your preferred app doesn’t support selecting reasoning effort, or you just want a simpler approach, this parameter exposes each reasoning level as a separate, queryable model. Each reasoning level also appears individually under ⁠/v1/models, so model pickers in your favorite chat apps will list all reasoning options as distinct models you can switch between.

## Notes
If you wish to have the fastest responses, I'd recommend setting `--reasoning-effort` to low, and `--reasoning-summary` to none. <br>
All parameters and choices can be seen by sending `python chatmock.py serve --h`<br>
The context size of this route is also larger than what you get access to in the regular ChatGPT app.<br>

When the model returns a thinking summary, the model will send back thinking tags to make it compatible with chat apps. **If you don't like this behavior, you can instead set `--reasoning-compat` to legacy, and reasoning will be set in the reasoning tag instead of being returned in the actual response text.**


## Star History

[![Star History Chart](https://api.star-history.com/svg?repos=RayBytes/ChatMock&type=Timeline)](https://www.star-history.com/#RayBytes/ChatMock&Timeline)
