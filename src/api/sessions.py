_sessions: dict[tuple[str, str], dict] = {}


def get_session(platform: str, user_id: str) -> dict:
    return _sessions.get((platform, user_id), {})


def save_session(platform: str, user_id: str, session_state: dict) -> None:
    _sessions[(platform, user_id)] = session_state