import unittest
from datetime import timedelta

from django.utils import timezone

from sentry.api.serializers.snuba import zerofill


class ZeroFillTest(unittest.TestCase):
    def run_test(self, filled_buckets, irregular_buckets, start, end, rollup, zerofilled_buckets):
        filled_buckets = [(start + (rollup * bucket), val) for bucket, val in filled_buckets]
        buckets = [(date.timestamp(), val) for date, val in filled_buckets + irregular_buckets]
        sort_key = lambda row: row[0]
        buckets.sort(key=sort_key)
        zerofilled_buckets = [
            ((start + (rollup * bucket)).timestamp(), []) for bucket in zerofilled_buckets
        ]
        expected = buckets + zerofilled_buckets
        expected.sort(key=sort_key)
        assert zerofill(buckets, start, end, int(rollup.total_seconds())) == expected

    def test_missing_buckets(self) -> None:
        start = timezone.now().replace(minute=0, second=0, microsecond=0)
        rollup = timedelta(minutes=10)
        self.run_test(
            [(0, [0]), (1, [1])], [], start, start + timedelta(minutes=60), rollup, [2, 3, 4, 5]
        )
        self.run_test(
            [(0, [0]), (2, [1]), (4, [4])],
            [],
            start,
            start + timedelta(minutes=60),
            rollup,
            [1, 3, 5],
        )

    def test_non_rollup_buckets(self) -> None:
        start = timezone.now().replace(minute=0, second=0, microsecond=0)
        rollup = timedelta(minutes=10)
        self.run_test(
            filled_buckets=[(0, [0]), (1, [1])],
            irregular_buckets=[
                (start + timedelta(minutes=5), [5]),
                (start + timedelta(minutes=32), [8]),
            ],
            start=start,
            end=start + timedelta(minutes=60),
            rollup=rollup,
            zerofilled_buckets=[2, 3, 4, 5],
        )

    def test_misaligned_last_bucket(self) -> None:
        # the start does NOT align the first bucket due to the zerofill
        start = timezone.now().replace(minute=5, second=0, microsecond=0)
        rollup = timedelta(minutes=10)
        buckets = [
            ((start + timedelta(minutes=1)).timestamp(), [9]),
            ((start + timedelta(minutes=16)).timestamp(), [3]),
        ]
        zerofilled_buckets = zerofill(
            buckets,
            start,
            start + timedelta(minutes=20),
            int(rollup.total_seconds()),
            allow_partial_buckets=True,
        )
        assert zerofilled_buckets == [
            ((start - timedelta(minutes=5)).timestamp(), []),
            ((start + timedelta(minutes=1)).timestamp(), [9]),
            ((start + timedelta(minutes=5)).timestamp(), []),
            ((start + timedelta(minutes=16)).timestamp(), [3]),
        ]
