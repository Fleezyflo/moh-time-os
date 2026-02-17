def bad_query(user_input):
    from lib.state_store import StateStore
    store = StateStore()
    # SQL injection vulnerability
    result = store.query(f"SELECT * FROM tasks WHERE id = '{user_input}'")
    return result
