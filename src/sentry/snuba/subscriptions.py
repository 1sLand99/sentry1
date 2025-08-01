import logging
from collections.abc import Collection, Iterable, Sequence
from datetime import timedelta

from django.db import router, transaction

from sentry.models.environment import Environment
from sentry.models.project import Project
from sentry.snuba.dataset import Dataset
from sentry.snuba.models import QuerySubscription, SnubaQuery, SnubaQueryEventType
from sentry.snuba.tasks import (
    create_subscription_in_snuba,
    delete_subscription_from_snuba,
    update_subscription_in_snuba,
)

logger = logging.getLogger(__name__)


def create_snuba_query(
    query_type: SnubaQuery.Type,
    dataset: Dataset,
    query: str,
    aggregate: str,
    time_window: timedelta,
    resolution: timedelta,
    environment: Environment | None,
    event_types: Collection[SnubaQueryEventType.EventType] = (),
    group_by: Sequence[str] | None = None,
):
    """
    Constructs a SnubaQuery which is the postgres representation of a query in snuba

    :param query_type: The SnubaQuery.Type of this query
    :param dataset: The snuba dataset to query and aggregate over
    :param query: An event search query that we can parse and convert into a
    set of Snuba conditions
    :param aggregate: An aggregate to calculate over the time window
    :param time_window: The time window to aggregate over
    :param resolution: How often to receive updates/bucket size
    :param environment: An optional environment to filter by
    :param event_types: A (currently) optional list of event_types that apply to this
    query. If not passed, we'll infer a default value based on the dataset.
    :return: A list of QuerySubscriptions
    """
    snuba_query = SnubaQuery.objects.create(
        type=query_type.value,
        dataset=dataset.value,
        query=query,
        aggregate=aggregate,
        time_window=int(time_window.total_seconds()),
        resolution=int(resolution.total_seconds()),
        environment=environment,
        group_by=group_by,
    )
    if not event_types:
        if dataset == Dataset.Events:
            event_types = [SnubaQueryEventType.EventType.ERROR]
        elif dataset == Dataset.Transactions:
            event_types = [SnubaQueryEventType.EventType.TRANSACTION]

    if event_types:
        sq_event_types = [
            SnubaQueryEventType(snuba_query=snuba_query, type=event_type.value)
            for event_type in set(event_types)
        ]
        SnubaQueryEventType.objects.bulk_create(sq_event_types)
    return snuba_query


def update_snuba_query(
    snuba_query,
    query_type,
    dataset,
    query,
    aggregate,
    time_window,
    resolution,
    environment,
    event_types,
):
    """
    Updates a SnubaQuery. Triggers updates to any related QuerySubscriptions.

    :param snuba_query: The `SnubaQuery` to update.
    :param query_type: The SnubaQuery.Type of this query
    :param dataset: The snuba dataset to query and aggregate over
    :param query: An event search query that we can parse and convert into a
    set of Snuba conditions
    :param aggregate: An aggregate to calculate over the time window
    :param time_window: The time window to aggregate over
    :param resolution: How often to receive updates/bucket size
    :param environment: An optional environment to filter by
    :param event_types: A (currently) optional list of event_types that apply to this
    query. If not passed, we'll use the existing event types on the query.
    :return: A list of QuerySubscriptions

    TODO: Ensure update handles activated alert rule updates
    eg. insert start_time into query, insert release version into query, etc.
    """
    current_event_types = set(snuba_query.event_types)
    if not event_types:
        event_types = current_event_types

    new_event_types = set(event_types) - current_event_types
    removed_event_types = current_event_types - set(event_types)
    old_query_type = SnubaQuery.Type(snuba_query.type)
    old_dataset = Dataset(snuba_query.dataset)
    old_query = snuba_query.query
    old_aggregate = snuba_query.aggregate
    with transaction.atomic(router.db_for_write(SnubaQuery)):
        query_subscriptions = list(snuba_query.subscriptions.all())
        snuba_query.update(
            type=query_type.value,
            dataset=dataset.value,
            query=query,
            aggregate=aggregate,
            time_window=int(time_window.total_seconds()),
            resolution=int(resolution.total_seconds()),
            environment=environment,
        )
        if new_event_types:
            SnubaQueryEventType.objects.bulk_create(
                [
                    SnubaQueryEventType(snuba_query=snuba_query, type=event_type.value)
                    for event_type in set(new_event_types)
                ]
            )
        if removed_event_types:
            SnubaQueryEventType.objects.filter(
                snuba_query=snuba_query, type__in=[et.value for et in removed_event_types]
            ).delete()

        bulk_update_snuba_subscriptions(
            query_subscriptions, old_query_type, old_dataset, old_aggregate, old_query
        )


def bulk_create_snuba_subscriptions(
    projects: Iterable[Project],
    subscription_type: str,
    snuba_query: SnubaQuery,
    query_extra: str | None = None,
) -> list[QuerySubscription]:
    """
    Creates a subscription to a snuba query for each project.

    :param projects: The projects we're applying the query to
    :param subscription_type: Text identifier for the subscription type this is. Used
    to identify the registered callback associated with this subscription.
    :param snuba_query: A `SnubaQuery` instance to subscribe the projects to.
    :return: A list of QuerySubscriptions
    """
    subscriptions = []
    # TODO: Batch this up properly once we care about multi-project rules.
    for project in projects:
        subscriptions.append(
            create_snuba_subscription(project, subscription_type, snuba_query, query_extra)
        )
    return subscriptions


def create_snuba_subscription(
    project: Project,
    subscription_type: str,
    snuba_query: SnubaQuery,
    query_extra: str | None = None,
) -> QuerySubscription:
    """
    Creates a subscription to a snuba query.

    :param project: The project we're applying the query to
    :param subscription_type: Text identifier for the subscription type this is. Used
    to identify the registered callback associated with this subscription.
    :param snuba_query: A `SnubaQuery` instance to subscribe the project to.
    :return: The QuerySubscription representing the subscription
    """
    subscription = QuerySubscription.objects.create(
        status=QuerySubscription.Status.CREATING.value,
        project=project,
        snuba_query=snuba_query,
        type=subscription_type,
        query_extra=query_extra,
    )

    transaction.on_commit(
        lambda: create_subscription_in_snuba.delay(query_subscription_id=subscription.id),
        using=router.db_for_write(QuerySubscription),
    )

    return subscription


def bulk_update_snuba_subscriptions(
    subscriptions, old_query_type, old_dataset, old_aggregate, old_query
):
    """
    Updates a list of query subscriptions.

    :param subscriptions: The subscriptions we're updating
    :param snuba_query: A `SnubaQuery` instance to subscribe the project to.
    :return: A list of QuerySubscriptions
    """
    updated_subscriptions = []
    # TODO: Batch this up properly once we care about multi-project rules.
    for subscription in subscriptions:
        updated_subscriptions.append(
            update_snuba_subscription(
                subscription, old_query_type, old_dataset, old_aggregate, old_query
            )
        )
    return subscriptions


def update_snuba_subscription(subscription, old_query_type, old_dataset, old_aggregate, old_query):
    """
    Updates a subscription to a snuba query.

    :param query: An event search query that we can parse and convert into a
    set of Snuba conditions
    :param old_dataset: The `QueryDataset` that this subscription was associated with
    before the update.
    :return: The QuerySubscription representing the subscription
    """
    with transaction.atomic(router.db_for_write(QuerySubscription)):
        subscription.update(status=QuerySubscription.Status.UPDATING.value)

        transaction.on_commit(
            lambda: update_subscription_in_snuba.delay(
                query_subscription_id=subscription.id,
                old_query_type=old_query_type.value,
                old_dataset=old_dataset.value,
                old_aggregate=old_aggregate,
                old_query=old_query,
            ),
            using=router.db_for_write(QuerySubscription),
        )

    return subscription


def bulk_delete_snuba_subscriptions(subscriptions):
    """
    Deletes a list of snuba query subscriptions.
    :param subscriptions: The subscriptions to delete
    :return:
    """
    for subscription in subscriptions:
        # TODO: Batch this up properly once we care about multi-project rules.
        delete_snuba_subscription(subscription)


def delete_snuba_subscription(subscription):
    """
    Deletes a subscription to a snuba query.
    :param subscription: The subscription to delete
    :return:
    """
    subscription.update(status=QuerySubscription.Status.DELETING.value)

    transaction.on_commit(
        lambda: delete_subscription_from_snuba.delay(query_subscription_id=subscription.id),
        using=router.db_for_write(QuerySubscription),
    )


def bulk_disable_snuba_subscriptions(subscriptions):
    """
    Disables a list of snuba query subscriptions.
    :param subscriptions: The subscriptions to disable
    :return:
    """
    for subscription in subscriptions:
        # TODO: Batch this up properly once we care about multi-project rules.
        disable_snuba_subscription(subscription)


def disable_snuba_subscription(subscription):
    """
    Disables a subscription to a snuba query.
    :param subscription: The subscription to disable
    :return:
    """
    subscription.update(status=QuerySubscription.Status.DISABLED.value)

    transaction.on_commit(
        lambda: delete_subscription_from_snuba.delay(query_subscription_id=subscription.id),
        using=router.db_for_write(QuerySubscription),
    )


def bulk_enable_snuba_subscriptions(subscriptions):
    """
    enables a list of snuba query subscriptions.
    :param subscriptions: The subscriptions to enable
    :return:
    """
    for subscription in subscriptions:
        # TODO: Batch this up properly once we care about multi-project rules.
        enable_snuba_subscription(subscription)


def enable_snuba_subscription(subscription):
    """
    enables a subscription to a snuba query.
    :param subscription: The subscription to enable
    :return:
    """
    subscription.update(status=QuerySubscription.Status.CREATING.value)

    transaction.on_commit(
        lambda: create_subscription_in_snuba.delay(query_subscription_id=subscription.id),
        using=router.db_for_write(QuerySubscription),
    )
