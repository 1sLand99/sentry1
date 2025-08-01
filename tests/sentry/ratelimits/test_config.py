from unittest import TestCase, mock

from sentry.ratelimits.config import RateLimitConfig, get_default_rate_limits_for_group
from sentry.types.ratelimit import RateLimit, RateLimitCategory


class TestRateLimitConfig(TestCase):
    @mock.patch(
        "sentry.ratelimits.config._get_group_defaults",
        return_value={"blz": {RateLimitCategory.ORGANIZATION: RateLimit(limit=420, window=69)}},
    )
    def test_grouping(self, *m) -> None:
        config = RateLimitConfig(group="blz")
        assert config.get_rate_limit("GET", RateLimitCategory.ORGANIZATION) == RateLimit(
            limit=420, window=69
        )

    def test_defaults(self) -> None:
        config = RateLimitConfig()
        for c in RateLimitCategory:
            for method in ("POST", "GET", "PUT", "DELETE"):
                assert isinstance(config.get_rate_limit(method, c), RateLimit)

    def test_override(self) -> None:
        config = RateLimitConfig(
            group="default",
            limit_overrides={"GET": {RateLimitCategory.IP: RateLimit(limit=1, window=1)}},
        )
        assert config.get_rate_limit("GET", RateLimitCategory.IP) == RateLimit(limit=1, window=1)
        assert config.get_rate_limit(
            "POST", RateLimitCategory.IP
        ) == get_default_rate_limits_for_group("default", RateLimitCategory.IP)
        assert config.get_rate_limit(
            "GET", RateLimitCategory.ORGANIZATION
        ) == get_default_rate_limits_for_group("default", RateLimitCategory.ORGANIZATION)

    def test_backwards_compatibility(self) -> None:
        override_dict = {"GET": {RateLimitCategory.IP: RateLimit(limit=1, window=1)}}
        assert RateLimitConfig.from_rate_limit_override_dict(override_dict) == RateLimitConfig(
            group="default", limit_overrides=override_dict
        )

    def test_invalid_config(self) -> None:
        config = RateLimitConfig(group="default", limit_overrides={"GET": {"invalid": "invalid"}})  # type: ignore[dict-item]
        ret = config.get_rate_limit("bloop", "badcategory")  # type: ignore[arg-type]
        assert ret == get_default_rate_limits_for_group("default", RateLimitCategory.ORGANIZATION)
