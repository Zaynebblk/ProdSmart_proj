import json
import os
import urllib.request
import urllib.error

DEFAULT_BASE_URL = "http://127.0.0.1:8000"


class ApiError(Exception):
    def __init__(self, message, status=None):
        super().__init__(message)
        self.status = status


def _settings_path():
    return os.path.join(os.getcwd(), "settings.json")


def load_settings():
    path = _settings_path()
    if os.path.exists(path):
        try:
            with open(path, "r") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_settings(data):
    path = _settings_path()
    try:
        with open(path, "w") as f:
            json.dump(data, f, indent=4)
    except Exception:
        pass


def get_base_url():
    data = load_settings()
    base = str(data.get("cloud_base_url") or "").strip()
    return base or DEFAULT_BASE_URL


def set_base_url(url):
    data = load_settings()
    data["cloud_base_url"] = (url or "").strip() or DEFAULT_BASE_URL
    save_settings(data)


def get_token():
    data = load_settings()
    return data.get("cloud_token")


def set_token(token, user_id=None, username=None):
    data = load_settings()
    data["cloud_token"] = token
    if user_id is not None:
        data["cloud_user_id"] = user_id
    if username is not None:
        data["cloud_username"] = username
    save_settings(data)


def clear_token():
    data = load_settings()
    for key in ("cloud_token", "cloud_user_id", "cloud_username"):
        if key in data:
            data.pop(key, None)
    save_settings(data)


def _request(method, path, payload=None, token=None, timeout=8):
    base_url = get_base_url().rstrip("/")
    url = f"{base_url}{path}"
    headers = {"Content-Type": "application/json"}
    auth_token = token or get_token()
    if auth_token:
        headers["Authorization"] = f"Bearer {auth_token}"
    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8") if resp.readable() else ""
            if not body:
                return None
            try:
                return json.loads(body)
            except Exception:
                return None
    except urllib.error.HTTPError as e:
        body = ""
        try:
            body = e.read().decode("utf-8")
        except Exception:
            body = ""
        message = f"HTTP {e.code}"
        if body:
            try:
                data = json.loads(body)
                if isinstance(data, dict) and data.get("detail"):
                    message = str(data.get("detail"))
                else:
                    message = body
            except Exception:
                message = body
        raise ApiError(message, status=e.code)
    except urllib.error.URLError as e:
        raise ApiError(f"Network error: {e.reason}")


def api_register(username, password):
    return _request("POST", "/auth/register", {"username": username, "password": password})


def api_login(username, password):
    res = _request("POST", "/auth/login", {"username": username, "password": password})
    if isinstance(res, dict) and res.get("token"):
        set_token(res.get("token"), res.get("user_id"), res.get("username"))
    return res


def api_me():
    return _request("GET", "/me")


def api_ping():
    return _request("GET", "/")


def api_list_teams():
    return _request("GET", "/teams")


def api_create_team(name):
    return _request("POST", "/teams", {"name": name})


def api_join_team(code):
    return _request("POST", "/teams/join", {"code": code})


def api_get_team(team_id):
    return _request("GET", f"/teams/{team_id}")


def api_list_team_tasks(team_id):
    return _request("GET", f"/teams/{team_id}/tasks")


def api_create_team_task(team_id, title, description="", due_date=None, is_important=None, task_type=None):
    payload = {
        "title": title,
        "description": description or "",
        "due_date": due_date,
        "is_important": is_important,
        "task_type": task_type,
    }
    return _request("POST", f"/teams/{team_id}/tasks", payload)


def api_update_team_task(team_id, task_id, **fields):
    return _request("PATCH", f"/teams/{team_id}/tasks/{task_id}", fields)


def api_delete_team_task(team_id, task_id):
    return _request("DELETE", f"/teams/{team_id}/tasks/{task_id}")


def api_get_team_pomodoro(team_id):
    return _request("GET", f"/teams/{team_id}/pomodoro")


def api_start_team_pomodoro(team_id, phase, duration_min):
    payload = {"phase": phase, "duration_min": duration_min}
    return _request("POST", f"/teams/{team_id}/pomodoro/start", payload)


def api_stop_team_pomodoro(team_id):
    return _request("POST", f"/teams/{team_id}/pomodoro/stop", {})
