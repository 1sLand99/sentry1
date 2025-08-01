import {useEffect, useMemo, useState} from 'react';
import styled from '@emotion/styled';
import keyBy from 'lodash/keyBy';

import {Button} from 'sentry/components/core/button';
import {CompactSelect, type SelectOption} from 'sentry/components/core/compactSelect';
import {EventDrawerHeader} from 'sentry/components/events/eventDrawer';
import {EapSpanSearchQueryBuilderWrapper} from 'sentry/components/performance/spanSearchQueryBuilder';
import {t} from 'sentry/locale';
import {space} from 'sentry/styles/space';
import {trackAnalytics} from 'sentry/utils/analytics';
import {DurationUnit, SizeUnit} from 'sentry/utils/discover/fields';
import {PageAlertProvider} from 'sentry/utils/performance/contexts/pageAlert';
import {decodeScalar} from 'sentry/utils/queryString';
import {MutableSearch} from 'sentry/utils/tokenizeSearch';
import useLocationQuery from 'sentry/utils/url/useLocationQuery';
import {useLocation} from 'sentry/utils/useLocation';
import {useNavigate} from 'sentry/utils/useNavigate';
import useOrganization from 'sentry/utils/useOrganization';
import usePageFilters from 'sentry/utils/usePageFilters';
import useProjects from 'sentry/utils/useProjects';
import type {TabularData} from 'sentry/views/dashboards/widgets/common/types';
import {Samples} from 'sentry/views/dashboards/widgets/timeSeriesWidget/plottables/samples';
import {computeAxisMax} from 'sentry/views/insights/common/components/chart';
// TODO(release-drawer): Move InsightsLineChartWidget into separate, self-contained component
// eslint-disable-next-line no-restricted-imports
import {InsightsLineChartWidget} from 'sentry/views/insights/common/components/insightsLineChartWidget';
import {MetricReadout} from 'sentry/views/insights/common/components/metricReadout';
import * as ModuleLayout from 'sentry/views/insights/common/components/moduleLayout';
import {ReadoutRibbon} from 'sentry/views/insights/common/components/ribbon';
import {SampleDrawerBody} from 'sentry/views/insights/common/components/sampleDrawerBody';
import {SampleDrawerHeaderTransaction} from 'sentry/views/insights/common/components/sampleDrawerHeaderTransaction';
import {useSpanSeries} from 'sentry/views/insights/common/queries/useDiscoverSeries';
import {getDurationChartTitle} from 'sentry/views/insights/common/views/spans/types';
import {useSpanSamples} from 'sentry/views/insights/http/queries/useSpanSamples';
import {InsightsSpanTagProvider} from 'sentry/views/insights/pages/insightsSpanTagProvider';
import {MessageSpanSamplesTable} from 'sentry/views/insights/queues/components/tables/messageSpanSamplesTable';
import {useQueuesMetricsQuery} from 'sentry/views/insights/queues/queries/useQueuesMetricsQuery';
import {Referrer} from 'sentry/views/insights/queues/referrers';
import {
  CONSUMER_QUERY_FILTER,
  MessageActorType,
  PRODUCER_QUERY_FILTER,
  RETRY_COUNT_OPTIONS,
  TRACE_STATUS_OPTIONS,
} from 'sentry/views/insights/queues/settings';
import decodeRetryCount from 'sentry/views/insights/queues/utils/queryParameterDecoders/retryCount';
import decodeTraceStatus from 'sentry/views/insights/queues/utils/queryParameterDecoders/traceStatus';
import {ModuleName, SpanFields, type SpanResponse} from 'sentry/views/insights/types';

export function MessageSpanSamplesPanel() {
  const navigate = useNavigate();
  const location = useLocation();
  const query = useLocationQuery({
    fields: {
      project: decodeScalar,
      destination: decodeScalar,
      transaction: decodeScalar,
      retryCount: decodeRetryCount,
      traceStatus: decodeTraceStatus,
      spanSearchQuery: decodeScalar,
      'span.op': decodeScalar,
    },
  });
  const {projects} = useProjects();
  const {selection} = usePageFilters();

  const project = projects.find(p => query.project === p.id);

  const organization = useOrganization();

  const [highlightedSpanId, setHighlightedSpanId] = useState<string | undefined>(
    undefined
  );

  // `detailKey` controls whether the panel is open. If all required properties are available, concat them to make a key, otherwise set to `undefined` and hide the panel
  const detailKey = query.transaction
    ? [query.destination, query.transaction].filter(Boolean).join(':')
    : undefined;

  const handleTraceStatusChange = (newTraceStatus: SelectOption<string>) => {
    trackAnalytics('performance_views.sample_spans.filter_updated', {
      filter: 'trace_status',
      new_state: newTraceStatus.value,
      organization,
      source: ModuleName.QUEUE,
    });
    navigate({
      pathname: location.pathname,
      query: {
        ...location.query,
        traceStatus: newTraceStatus.value,
      },
    });
  };

  const handleRetryCountChange = (newRetryCount: SelectOption<string>) => {
    trackAnalytics('performance_views.sample_spans.filter_updated', {
      filter: 'retry_count',
      new_state: newRetryCount.value,
      organization,
      source: ModuleName.QUEUE,
    });
    navigate({
      pathname: location.pathname,
      query: {
        ...location.query,
        retryCount: newRetryCount.value,
      },
    });
  };

  const isPanelOpen = Boolean(detailKey);

  const messageActorType =
    query['span.op'] === 'queue.publish'
      ? MessageActorType.PRODUCER
      : MessageActorType.CONSUMER;
  const queryFilter =
    messageActorType === MessageActorType.PRODUCER
      ? PRODUCER_QUERY_FILTER
      : CONSUMER_QUERY_FILTER;

  const timeseriesFilters = new MutableSearch(queryFilter);
  timeseriesFilters.addFilterValue('transaction', query.transaction);
  timeseriesFilters.addFilterValue('messaging.destination.name', query.destination);
  const timeseriesReferrer = Referrer.QUEUES_SAMPLES_PANEL_DURATION_CHART;

  const sampleFilters = new MutableSearch(queryFilter);
  sampleFilters.addFilterValue('transaction', query.transaction);
  sampleFilters.addFilterValue('messaging.destination.name', query.destination);

  // filter by key-value filters specified in the search bar query
  sampleFilters.addStringMultiFilter(query.spanSearchQuery);

  if (query.traceStatus.length > 0) {
    sampleFilters.addFilterValue('trace.status', query.traceStatus);
  }

  // Note: only consumer panels should allow filtering by retry count
  if (messageActorType === MessageActorType.CONSUMER) {
    if (query.retryCount === '0') {
      sampleFilters.addFilterValue('measurements.messaging.message.retry.count', '0');
    } else if (query.retryCount === '1-3') {
      sampleFilters.addFilterValues('measurements.messaging.message.retry.count', [
        '>=1',
        '<=3',
      ]);
    } else if (query.retryCount === '4+') {
      sampleFilters.addFilterValue('measurements.messaging.message.retry.count', '>=4');
    }
  }

  const {data: transactionMetrics, isFetching: aretransactionMetricsFetching} =
    useQueuesMetricsQuery({
      destination: query.destination,
      transaction: query.transaction,
      enabled: isPanelOpen,
      referrer: Referrer.QUEUES_SAMPLES_PANEL,
    });

  const avg = transactionMetrics?.[0]?.['avg(span.duration)'];

  const {
    isFetching: isDurationDataFetching,
    data: durationData,
    error: durationError,
  } = useSpanSeries(
    {
      search: timeseriesFilters,
      yAxis: [`avg(span.duration)`],
      enabled: isPanelOpen,
      transformAliasToInputFormat: true,
    },
    timeseriesReferrer
  );

  const durationAxisMax = computeAxisMax([durationData?.[`avg(span.duration)`]]);

  const {
    data: spanSamplesData,
    isFetching: isDurationSamplesDataFetching,
    error: durationSamplesDataError,
    refetch: refetchDurationSpanSamples,
  } = useSpanSamples({
    search: sampleFilters,
    min: 0,
    max: durationAxisMax,
    enabled: isPanelOpen && durationAxisMax > 0,
    fields: [
      SpanFields.ID,
      SpanFields.TRACE,
      SpanFields.SPAN_DESCRIPTION,
      SpanFields.MESSAGING_MESSAGE_BODY_SIZE,
      SpanFields.MESSAGING_MESSAGE_RECEIVE_LATENCY,
      SpanFields.MESSAGING_MESSAGE_RETRY_COUNT,
      SpanFields.MESSAGING_MESSAGE_ID,
      SpanFields.TRACE_STATUS,
      SpanFields.SPAN_DURATION,
    ],
  });

  const spanSamplesById = useMemo(() => {
    return keyBy(spanSamplesData?.data ?? [], 'id');
  }, [spanSamplesData]);

  const handleSearch = (newSpanSearchQuery: string) => {
    navigate({
      pathname: location.pathname,
      query: {
        ...location.query,
        spanSearchQuery: newSpanSearchQuery,
      },
    });
  };

  const samplesPlottable = useMemo(() => {
    if (!spanSamplesData) {
      return undefined;
    }

    return new Samples(spanSamplesData as TabularData, {
      attributeName: 'span.self_time',
      baselineValue: avg,
      baselineLabel: t('Average'),
      onHighlight: sample => {
        setHighlightedSpanId(sample.id);
      },
      onDownplay: () => {
        setHighlightedSpanId(undefined);
      },
    });
  }, [avg, spanSamplesData, setHighlightedSpanId]);

  useEffect(() => {
    if (highlightedSpanId && samplesPlottable) {
      const spanSample = spanSamplesById[highlightedSpanId]!;
      samplesPlottable.highlight(spanSample);
    }

    return () => {
      if (!highlightedSpanId) {
        return;
      }

      const spanSample = spanSamplesById[highlightedSpanId]!;
      samplesPlottable?.downplay(spanSample);
    };
  }, [samplesPlottable, spanSamplesById, highlightedSpanId]);

  return (
    <PageAlertProvider>
      <InsightsSpanTagProvider>
        <EventDrawerHeader>
          <SampleDrawerHeaderTransaction
            project={project}
            transaction={query.transaction}
            subtitle={
              messageActorType === MessageActorType.PRODUCER
                ? t('Producer')
                : t('Consumer')
            }
          />
        </EventDrawerHeader>

        <SampleDrawerBody>
          <ModuleLayout.Layout>
            <ModuleLayout.Full>
              <MetricsRibbonContainer>
                {messageActorType === MessageActorType.PRODUCER ? (
                  <ProducerMetricsRibbon
                    metrics={transactionMetrics}
                    isLoading={aretransactionMetricsFetching}
                  />
                ) : (
                  <ConsumerMetricsRibbon
                    metrics={transactionMetrics}
                    isLoading={aretransactionMetricsFetching}
                  />
                )}
              </MetricsRibbonContainer>
            </ModuleLayout.Full>

            <ModuleLayout.Full>
              <PanelControls>
                <CompactSelect
                  searchable
                  value={query.traceStatus}
                  options={TRACE_STATUS_SELECT_OPTIONS}
                  onChange={handleTraceStatusChange}
                  triggerProps={{
                    prefix: t('Status'),
                  }}
                />
                {messageActorType === MessageActorType.CONSUMER && (
                  <CompactSelect
                    value={query.retryCount}
                    options={RETRY_COUNT_SELECT_OPTIONS}
                    onChange={handleRetryCountChange}
                    triggerProps={{
                      prefix: t('Retries'),
                    }}
                  />
                )}
              </PanelControls>
            </ModuleLayout.Full>

            <ModuleLayout.Full>
              <InsightsLineChartWidget
                showLegend="never"
                queryInfo={{search: timeseriesFilters, referrer: timeseriesReferrer}}
                title={getDurationChartTitle('queue')}
                isLoading={isDurationDataFetching}
                error={durationError}
                series={[durationData[`avg(span.duration)`]]}
                samples={samplesPlottable}
              />
            </ModuleLayout.Full>

            <ModuleLayout.Full>
              <EapSpanSearchQueryBuilderWrapper
                searchSource={`${ModuleName.QUEUE}-sample-panel`}
                initialQuery={query.spanSearchQuery}
                onSearch={handleSearch}
                placeholder={t('Search for span attributes')}
                projects={selection.projects}
              />
            </ModuleLayout.Full>

            <ModuleLayout.Full>
              <MessageSpanSamplesTable
                data={spanSamplesData?.data ?? []}
                isLoading={isDurationDataFetching || isDurationSamplesDataFetching}
                highlightedSpanId={highlightedSpanId}
                onSampleMouseOver={sample => setHighlightedSpanId(sample.span_id)}
                onSampleMouseOut={() => setHighlightedSpanId(undefined)}
                error={durationSamplesDataError}
                // Samples endpoint doesn't provide meta data, so we need to provide it here
                meta={{
                  fields: {
                    [SpanFields.SPAN_DURATION]: 'duration',
                    [SpanFields.MESSAGING_MESSAGE_BODY_SIZE]: 'size',
                    [SpanFields.MESSAGING_MESSAGE_RETRY_COUNT]: 'number',
                  },
                  units: {
                    [SpanFields.SPAN_DURATION]: DurationUnit.MILLISECOND,
                    [SpanFields.MESSAGING_MESSAGE_BODY_SIZE]: SizeUnit.BYTE,
                  },
                }}
                type={messageActorType}
              />
            </ModuleLayout.Full>

            <ModuleLayout.Full>
              <Button
                onClick={() => {
                  trackAnalytics(
                    'performance_views.sample_spans.try_different_samples_clicked',
                    {organization, source: ModuleName.QUEUE}
                  );
                  refetchDurationSpanSamples();
                }}
              >
                {t('Try Different Samples')}
              </Button>
            </ModuleLayout.Full>
          </ModuleLayout.Layout>
        </SampleDrawerBody>
      </InsightsSpanTagProvider>
    </PageAlertProvider>
  );
}

function ProducerMetricsRibbon({
  metrics,
  isLoading,
}: {
  isLoading: boolean;
  metrics: Array<Partial<SpanResponse>>;
}) {
  const errorRate = 1 - (metrics[0]?.['trace_status_rate(ok)'] ?? 0);
  return (
    <ReadoutRibbon>
      <MetricReadout
        title={t('Published')}
        value={metrics?.[0]?.['count_op(queue.publish)']}
        unit={'count'}
        isLoading={isLoading}
      />
      <MetricReadout
        title={t('Error Rate')}
        value={errorRate}
        unit={'percentage'}
        isLoading={isLoading}
      />
    </ReadoutRibbon>
  );
}

function ConsumerMetricsRibbon({
  metrics,
  isLoading,
}: {
  isLoading: boolean;
  metrics: Array<Partial<SpanResponse>>;
}) {
  const errorRate = 1 - (metrics[0]?.['trace_status_rate(ok)'] ?? 0);
  return (
    <ReadoutRibbon>
      <MetricReadout
        title={t('Processed')}
        value={metrics?.[0]?.['count_op(queue.process)']}
        unit={'count'}
        isLoading={isLoading}
      />
      <MetricReadout
        title={t('Error Rate')}
        value={errorRate}
        unit={'percentage'}
        isLoading={isLoading}
      />
      <MetricReadout
        title={t('Avg Time In Queue')}
        value={metrics[0]?.['avg(messaging.message.receive.latency)']}
        unit={DurationUnit.MILLISECOND}
        isLoading={false}
      />
      <MetricReadout
        title={t('Avg Processing Time')}
        value={metrics[0]?.['avg_if(span.duration,span.op,equals,queue.process)']}
        unit={DurationUnit.MILLISECOND}
        isLoading={false}
      />
    </ReadoutRibbon>
  );
}

const TRACE_STATUS_SELECT_OPTIONS = [
  {
    value: '',
    label: t('All'),
  },
  ...TRACE_STATUS_OPTIONS.map(status => {
    return {
      value: status,
      label: status,
    };
  }),
];

const RETRY_COUNT_SELECT_OPTIONS = [
  {
    value: '',
    label: t('Any'),
  },
  ...RETRY_COUNT_OPTIONS.map(status => {
    return {
      value: status,
      label: status,
    };
  }),
];

const MetricsRibbonContainer = styled('div')`
  display: flex;
  flex-wrap: wrap;
  gap: ${space(4)};
`;

const PanelControls = styled('div')`
  display: flex;
  gap: ${space(2)};
`;
