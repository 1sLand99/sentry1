import styled from '@emotion/styled';

import {Container, Flex} from 'sentry/components/core/layout';
import * as Layout from 'sentry/components/layouts/thirds';
import {DatePageFilter} from 'sentry/components/organizations/datePageFilter';
import {EnvironmentPageFilter} from 'sentry/components/organizations/environmentPageFilter';
import {ProjectPageFilter} from 'sentry/components/organizations/projectPageFilter';
import {t} from 'sentry/locale';
import {ToolbarVisualizeAddChart} from 'sentry/views/explore/components/toolbar/toolbarVisualize';
import {BottomSectionBody, TopSectionBody} from 'sentry/views/explore/logs/styles';
import {MetricPanel} from 'sentry/views/explore/metrics/metricPanel';
import {MetricsQueryParamsProvider} from 'sentry/views/explore/metrics/metricsQueryParams';
import {MetricToolbar} from 'sentry/views/explore/metrics/metricToolbar';
import {MetricSaveAs} from 'sentry/views/explore/metrics/metricToolbar/metricSaveAs';
import {
  MultiMetricsQueryParamsProvider,
  useAddMetricQuery,
  useMultiMetricsQueryParams,
} from 'sentry/views/explore/metrics/multiMetricsQueryParams';
import {
  FilterBarWithSaveAsContainer,
  StyledPageFilterBar,
} from 'sentry/views/explore/metrics/styles';
import type {PickableDays} from 'sentry/views/explore/utils';

const MAX_METRICS_ALLOWED = 4;

type MetricsTabProps = PickableDays;

export function MetricsTabContent({
  defaultPeriod,
  maxPickableDays,
  relativeOptions,
}: MetricsTabProps) {
  return (
    <MultiMetricsQueryParamsProvider>
      <MetricsTabFilterSection
        defaultPeriod={defaultPeriod}
        maxPickableDays={maxPickableDays}
        relativeOptions={relativeOptions}
      />
      <MetricsQueryBuilderSection />
      <MetricsTabBodySection />
    </MultiMetricsQueryParamsProvider>
  );
}

function MetricsTabFilterSection({
  defaultPeriod,
  maxPickableDays,
  relativeOptions,
}: PickableDays) {
  return (
    <TopSectionBody noRowGap>
      <Layout.Main width="full">
        <FilterBarWithSaveAsContainer>
          <StyledPageFilterBar condensed>
            <ProjectPageFilter />
            <EnvironmentPageFilter />
            <DatePageFilter
              defaultPeriod={defaultPeriod}
              maxPickableDays={maxPickableDays}
              relativeOptions={relativeOptions}
              searchPlaceholder={t('Custom range: 2h, 4d, 3w')}
            />
          </StyledPageFilterBar>
          <MetricSaveAs />
        </FilterBarWithSaveAsContainer>
      </Layout.Main>
    </TopSectionBody>
  );
}

function MetricsQueryBuilderSection() {
  const metricQueries = useMultiMetricsQueryParams();
  const addMetricQuery = useAddMetricQuery();
  return (
    <MetricsQueryBuilderContainer borderTop="primary" padding="md" style={{flexGrow: 0}}>
      <Flex direction="column" gap="lg" align="start">
        {metricQueries.map((metricQuery, index) => {
          return (
            <MetricsQueryParamsProvider
              key={`queryBuilder-${index}`}
              queryParams={metricQuery.queryParams}
              setQueryParams={metricQuery.setQueryParams}
              traceMetric={metricQuery.metric}
              setTraceMetric={metricQuery.setTraceMetric}
              removeMetric={metricQuery.removeMetric}
            >
              <MetricToolbar traceMetric={metricQuery.metric} queryIndex={index} />
            </MetricsQueryParamsProvider>
          );
        })}
        <ToolbarVisualizeAddChart
          add={addMetricQuery}
          disabled={metricQueries.length >= MAX_METRICS_ALLOWED}
          label={t('Add Metric')}
        />
      </Flex>
    </MetricsQueryBuilderContainer>
  );
}

function MetricsTabBodySection() {
  const metricQueries = useMultiMetricsQueryParams();

  return (
    <BottomSectionBody>
      <Flex direction="column" gap="lg">
        {metricQueries.map((metricQuery, index) => {
          return (
            <MetricsQueryParamsProvider
              key={`queryPanel-${index}`}
              queryParams={metricQuery.queryParams}
              setQueryParams={metricQuery.setQueryParams}
              traceMetric={metricQuery.metric}
              setTraceMetric={metricQuery.setTraceMetric}
              removeMetric={metricQuery.removeMetric}
            >
              <MetricPanel traceMetric={metricQuery.metric} queryIndex={index} />
            </MetricsQueryParamsProvider>
          );
        })}
      </Flex>
    </BottomSectionBody>
  );
}

const MetricsQueryBuilderContainer = styled(Container)`
  padding: ${p => `${p.theme.space.xl} ${p.theme.space['3xl']}`};
  background-color: ${p => p.theme.background};
`;
