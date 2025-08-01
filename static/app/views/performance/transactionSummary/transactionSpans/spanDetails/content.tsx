import {Fragment} from 'react';
import type {Location} from 'history';

import Feature from 'sentry/components/acl/feature';
import IdBadge from 'sentry/components/idBadge';
import * as Layout from 'sentry/components/layouts/thirds';
import type {Organization} from 'sentry/types/organization';
import type {Project} from 'sentry/types/project';
import DiscoverQuery from 'sentry/utils/discover/discoverQuery';
import type EventView from 'sentry/utils/discover/eventView';
import type {ChildrenProps as SpanExamplesProps} from 'sentry/utils/performance/suspectSpans/spanExamplesQuery';
import SpanExamplesQuery from 'sentry/utils/performance/suspectSpans/spanExamplesQuery';
import type {ChildrenProps as SuspectSpansProps} from 'sentry/utils/performance/suspectSpans/suspectSpansQuery';
import SuspectSpansQuery from 'sentry/utils/performance/suspectSpans/suspectSpansQuery';
import type {SpanSlug} from 'sentry/utils/performance/suspectSpans/types';
import {setGroupedEntityTag} from 'sentry/utils/performanceForSentry';
import {decodeScalar} from 'sentry/utils/queryString';
import useRouteAnalyticsEventNames from 'sentry/utils/routeAnalytics/useRouteAnalyticsEventNames';
import useRouteAnalyticsParams from 'sentry/utils/routeAnalytics/useRouteAnalyticsParams';
import Breadcrumb from 'sentry/views/performance/breadcrumb';
import Tab from 'sentry/views/performance/transactionSummary/tabs';
import SpanSummary from 'sentry/views/performance/transactionSummary/transactionSpans/spanSummary/content';
import {SpanSortOthers} from 'sentry/views/performance/transactionSummary/transactionSpans/types';
import {getTotalsView} from 'sentry/views/performance/transactionSummary/transactionSpans/utils';
import {getSelectedProjectPlatforms} from 'sentry/views/performance/utils';

import SpanChart from './chart';
import SpanDetailsControls from './spanDetailsControls';
import SpanDetailsHeader from './spanDetailsHeader';
import SpanTable from './spanDetailsTable';
import {ZoomKeys} from './utils';

type Props = {
  eventView: EventView;
  location: Location;
  organization: Organization;
  project: Project | undefined;
  spanSlug: SpanSlug;
  transactionName: string;
};

export default function SpanDetailsContentWrapper(props: Props) {
  const {location, organization, eventView, project, transactionName, spanSlug} = props;
  const minExclusiveTime = decodeScalar(location.query[ZoomKeys.MIN]);
  const maxExclusiveTime = decodeScalar(location.query[ZoomKeys.MAX]);

  // customize the route analytics event we send
  useRouteAnalyticsEventNames(
    'performance_views.span_summary.view',
    'Performance Views: Span Summary page viewed'
  );
  useRouteAnalyticsParams({
    project_platforms: project ? getSelectedProjectPlatforms(location, [project]) : '',
  });

  const hasNewSpansUIFlag =
    organization.features.includes('performance-spans-new-ui') &&
    organization.features.includes('insights-initial-modules');

  // TODO: When this feature is rolled out to GA, we will no longer need the entire `spanDetails` directory and can switch to `spanSummary`
  if (hasNewSpansUIFlag) {
    return <SpanSummary {...props} />;
  }

  return (
    <Fragment>
      <Layout.Header>
        <Layout.HeaderContent>
          <Breadcrumb
            organization={organization}
            location={location}
            transaction={{
              project: project?.id ?? '',
              name: transactionName,
            }}
            tab={Tab.SPANS}
            spanSlug={spanSlug}
          />
          <Layout.Title>
            {project && (
              <IdBadge
                project={project}
                avatarSize={28}
                hideName
                avatarProps={{hasTooltip: true, tooltip: project.slug}}
              />
            )}
            {transactionName}
          </Layout.Title>
        </Layout.HeaderContent>
      </Layout.Header>
      <Layout.Body>
        <Layout.Main fullWidth>
          <DiscoverQuery
            eventView={getTotalsView(eventView)}
            orgSlug={organization.slug}
            location={location}
            referrer="api.performance.transaction-spans"
            cursor="0:0:1"
            noPagination
          >
            {({tableData}) => {
              const totalCount: number | null =
                (tableData?.data?.[0]?.['count()'] as number) ?? null;

              if (totalCount) {
                setGroupedEntityTag('spans.totalCount', 1000, totalCount);
              }

              return (
                <SuspectSpansQuery
                  location={location}
                  orgSlug={organization.slug}
                  eventView={getSpansEventView(eventView)}
                  perSuspect={0}
                  spanOps={[spanSlug.op]}
                  spanGroups={[spanSlug.group]}
                  cursor="0:0:1"
                  minExclusiveTime={minExclusiveTime}
                  maxExclusiveTime={maxExclusiveTime}
                >
                  {suspectSpansResults => (
                    <SpanExamplesQuery
                      location={location}
                      orgSlug={organization.slug}
                      eventView={eventView}
                      spanOp={spanSlug.op}
                      spanGroup={spanSlug.group}
                      limit={10}
                      minExclusiveTime={minExclusiveTime}
                      maxExclusiveTime={maxExclusiveTime}
                    >
                      {spanExamplesResults => (
                        <SpanDetailsContent
                          location={location}
                          organization={organization}
                          project={project}
                          eventView={eventView}
                          spanSlug={spanSlug}
                          totalCount={totalCount}
                          suspectSpansResults={suspectSpansResults}
                          spanExamplesResults={spanExamplesResults}
                        />
                      )}
                    </SpanExamplesQuery>
                  )}
                </SuspectSpansQuery>
              );
            }}
          </DiscoverQuery>
        </Layout.Main>
      </Layout.Body>
    </Fragment>
  );
}

type ContentProps = {
  eventView: EventView;
  location: Location;
  organization: Organization;
  project: Project | undefined;
  spanExamplesResults: SpanExamplesProps;
  spanSlug: SpanSlug;
  suspectSpansResults: SuspectSpansProps;
  totalCount: number;
};

function SpanDetailsContent(props: ContentProps) {
  const {
    location,
    organization,
    project,
    eventView,
    spanSlug,
    totalCount,
    suspectSpansResults,
    spanExamplesResults,
  } = props;

  // There should always be exactly 1 result
  const suspectSpan = suspectSpansResults.suspectSpans?.[0];
  const examples = spanExamplesResults.examples?.[0]?.examples;
  const transactionCountContainingSpan = suspectSpan?.frequency;

  return (
    <Fragment>
      <Feature features="performance-span-histogram-view">
        <SpanDetailsControls
          organization={organization}
          location={location}
          eventView={eventView}
        />
      </Feature>
      <SpanDetailsHeader
        spanSlug={spanSlug}
        totalCount={totalCount}
        suspectSpan={suspectSpan}
      />
      <SpanChart
        totalCount={transactionCountContainingSpan}
        organization={organization}
        eventView={eventView}
        spanSlug={spanSlug}
      />
      <SpanTable
        location={location}
        organization={organization}
        project={project}
        suspectSpan={suspectSpan}
        isLoading={spanExamplesResults.isLoading}
        examples={examples ?? []}
        pageLinks={spanExamplesResults.pageLinks}
      />
    </Fragment>
  );
}

function getSpansEventView(eventView: EventView): EventView {
  // TODO: There is a bug where if the sort is not avg occurrence,
  // then the avg occurrence will never be added to the fields
  eventView = eventView.withSorts([{field: SpanSortOthers.AVG_OCCURRENCE, kind: 'desc'}]);
  eventView.fields = [
    {field: 'count()'},
    {field: 'count_unique(id)'},
    {field: 'equation|count() / count_unique(id)'},
    {field: 'sumArray(spans_exclusive_time)'},
    {field: 'percentileArray(spans_exclusive_time, 0.50)'},
    {field: 'percentileArray(spans_exclusive_time, 0.75)'},
    {field: 'percentileArray(spans_exclusive_time, 0.95)'},
    {field: 'percentileArray(spans_exclusive_time, 0.99)'},
  ];
  return eventView;
}
