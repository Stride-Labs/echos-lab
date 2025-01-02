from functools import wraps
from inspect import signature
from typing import Any, Awaitable, Callable, TypeVar, cast

from echos_lab.db.db_setup import SessionLocal

T = TypeVar("T")  # Return type of the decorated function


def async_cache() -> Callable:
    """
    Custom async cache decorator to cache based on the functions string and int parameters
    Parameters with types other than string or int WILL NOT be used in the cache key

    This is needed when dealing with async functions because lru_cache will cache the full
    coroutine which will break the event loop
    """
    cache: dict[str, Any] = {}

    def decorator(func: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
        sig = signature(func)

        # At decoration time, grab all the int and string parameters that will be used
        # as the cache key
        cache_key_params = []
        for name, param in sig.parameters.items():
            param_type = param.annotation
            if param_type == param.empty:
                raise RuntimeError("Type annotations must be provided when using async_cache")

            if param_type in (str, int):
                cache_key_params.append(name)

        # There must be at least 1 string or int argument
        if not cache_key_params:
            raise RuntimeError("At least one string or int argument is required")

        @wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            # Bind the passed arguments to their parameter names
            # This normalizes the arguments, regardless of whether they were
            # passed with args or kwards
            bound_args = sig.bind(*args, **kwargs)
            bound_args.apply_defaults()

            # Only include params that we validated at decoration time
            param_values = [
                (name, str(value)) for name, value in bound_args.arguments.items() if name in cache_key_params
            ]

            # Create cache key by sorting by parameter name
            key = ":".join(f"{name}={value}" for name, value in sorted(param_values))

            # If the cache key hits, return the result
            if key in cache:
                return cast(T, cache[key])

            # Otherwise call the function and cache the result
            result = await func(*args, **kwargs)
            if result is not None:
                cache[key] = result

            return cast(T, result)

        return wrapper

    return decorator


def with_db(func: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
    """
    Decorator that provides a database session to the decorated function.
    Automatically handles session cleanup.

    Args:
        func: Async function that takes a db session as first parameter.

    Returns:
        Wrapped function that injects db session and handles cleanup.
    """

    @wraps(func)
    async def wrapper(*args, **kwargs) -> T:
        db = SessionLocal()
        try:
            return await func(db, *args, **kwargs)
        finally:
            db.close()

    return wrapper


def wrap_xml_tag(tag: str, info: str | None) -> str:
    """
    Builds an xml string of the form:
        <tag>
        info
        </tag>
    Or an empty string if the info is None
    """
    return f"\n<{tag}>\n{info}\n</{tag}>\n" if info else ""
