import random

import pytest

from echos_lab.common.utils import async_cache


class TestAsyncCache:
    @pytest.mark.asyncio
    async def test_wrap_string_key(self):
        """
        Tests successfully wrapping a async function with a string
        parameter as the cache key
        """

        # Create wrapped cache function
        @async_cache()
        async def test_func(key: str) -> float:
            return random.random()

        # Call twice with the same key - it should return the sam evalue
        result1 = await test_func("key1")
        result2 = await test_func("key1")
        assert result1 == result2

        # Call with a different key - it should return a different value
        result3 = await test_func("different-key")
        assert result1 != result3

    @pytest.mark.asyncio
    async def test_wrap_int_key(self):
        """
        Tests successfully wrapping a async function with a string
        parameter as the cache key
        """

        # Create wrapped cache function
        @async_cache()
        async def test_func(key: int) -> float:
            return random.random()

        # Call twice with the same key - it should return the sam evalue
        result1 = await test_func(1)
        result2 = await test_func(1)
        assert result1 == result2

        # Call with a different key - it should return a different value
        result3 = await test_func(999)
        assert result1 != result3

    @pytest.mark.asyncio
    async def test_kwargs_key(self):
        """
        Tests successfully caching while using a kwargs key
        """

        @async_cache()
        async def test_func(key_param: str) -> float:
            return random.random()

        result1 = await test_func(key_param="key1")
        result2 = await test_func(key_param="key1")
        assert result1 == result2

    @pytest.mark.asyncio
    async def test_multiple_params(self):
        """
        Tests successfully caching while using multiple keys
        """

        @async_cache()
        async def test_func(paramA: str, paramB: int) -> float:
            return random.random()

        result1 = await test_func(paramA="key1", paramB=1)
        result2 = await test_func(paramB=1, paramA="key1")
        result3 = await test_func("key1", 1)
        assert result1 == result2 == result3

        result4 = await test_func(1, "key1")  # type: ignore
        assert result4 != result1

    @pytest.mark.asyncio
    async def test_invalid_key_type(self):
        """
        Tests trying to cache with an invalid key type (dict in this case)
        """

        with pytest.raises(RuntimeError) as error_info:

            @async_cache()
            async def test_func(key: dict) -> float:
                return random.random()

            assert "This cache can only be used on string or int keys" in str(error_info.value)

    @pytest.mark.asyncio
    async def test_none_response(self):
        """
        Tests a None response from the cached function
        """

        @async_cache()
        async def test_func(key: str) -> None:
            return None

        result1 = await test_func("key")
        assert result1 is None
