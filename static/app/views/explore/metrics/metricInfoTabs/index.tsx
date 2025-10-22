import styled from '@emotion/styled';

import {TabList, TabPanels, TabStateProvider} from 'sentry/components/core/tabs';
import {t} from 'sentry/locale';
import {AggregatesTab} from 'sentry/views/explore/metrics/metricInfoTabs/aggregatesTab';
import {SamplesTab} from 'sentry/views/explore/metrics/metricInfoTabs/samplesTab';
import type {TraceMetric} from 'sentry/views/explore/metrics/metricQuery';
import {useMetricVisualize} from 'sentry/views/explore/metrics/metricsQueryParams';
import {
  useQueryParamsMode,
  useSetQueryParamsMode,
} from 'sentry/views/explore/queryParams/context';
import {Mode} from 'sentry/views/explore/queryParams/mode';

interface MetricInfoTabsProps {
  traceMetric: TraceMetric;
}

export default function MetricInfoTabs({traceMetric}: MetricInfoTabsProps) {
  const visualize = useMetricVisualize();
  const queryParamsMode = useQueryParamsMode();
  const setAggregatesMode = useSetQueryParamsMode();
  return (
    <TabStateProvider<Mode>
      defaultValue={queryParamsMode}
      onChange={mode => {
        setAggregatesMode(mode);
      }}
    >
      <HeaderWrapper>
        <TabList>
          <TabList.Item key={Mode.AGGREGATE}>{t('Aggregates')}</TabList.Item>
          <TabList.Item key={Mode.SAMPLES}>{t('Samples')}</TabList.Item>
        </TabList>
      </HeaderWrapper>

      {visualize.visible && (
        <BodyContainer>
          <TabPanels>
            <TabPanels.Item key={Mode.AGGREGATE}>
              <AggregatesTab metricName={traceMetric.name} />
            </TabPanels.Item>
            <TabPanels.Item key={Mode.SAMPLES}>
              <SamplesTab metricName={traceMetric.name} />
            </TabPanels.Item>
          </TabPanels>
        </BodyContainer>
      )}
    </TabStateProvider>
  );
}

const HeaderWrapper = styled('div')`
  padding-bottom: ${p => p.theme.space.sm};
`;

const BodyContainer = styled('div')`
  padding: ${p => p.theme.space.md};
  padding-top: 0;
  height: 250px;
`;
