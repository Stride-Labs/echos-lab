import contextvars
from typing import Any, Dict

env_context: contextvars.ContextVar[Dict[str, Any]] = contextvars.ContextVar("env_context", default={})


def set_env_var(key, value):
    # get the current context or start with an empty dict if none exists
    env_vars = env_context.get({})
    # update the specific variable
    env_vars[key] = value
    # set the updated env_vars back to env_context
    env_context.set(env_vars)


def get_env_var(key):
    # get the current context or start with an empty dict if none exists
    env_vars = env_context.get({})
    # return the value of the specific variable
    return env_vars.get(key, '')
