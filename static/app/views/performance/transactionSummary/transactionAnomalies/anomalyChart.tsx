import ChartZoom from 'sentry/components/charts/chartZoom';
import type {LineChartProps} from 'sentry/components/charts/lineChart';
import {LineChart} from 'sentry/components/charts/lineChart';
import {normalizeDateTimeParams} from 'sentry/components/organizations/pageFilters/parse';
import {t} from 'sentry/locale';
import type {DateString} from 'sentry/types/core';
import type {Series} from 'sentry/types/echarts';
import {getUtcToLocalDateObject} from 'sentry/utils/dates';
import {axisLabelFormatter, tooltipFormatter} from 'sentry/utils/discover/charts';
import {aggregateOutputType} from 'sentry/utils/discover/fields';
import {useLocation} from 'sentry/utils/useLocation';

type Props = {
  data: Series[];
  end: DateString;
  start: DateString;
  statsPeriod: string | undefined;
  height?: number;
};

export function AnomalyChart(props: Props) {
  const location = useLocation();
  const {data, statsPeriod, height, start: propsStart, end: propsEnd} = props;

  const start = propsStart ? getUtcToLocalDateObject(propsStart) : null;
  const end = propsEnd ? getUtcToLocalDateObject(propsEnd) : null;
  const {utc} = normalizeDateTimeParams(location.query);

  const chartOptions: Omit<LineChartProps, 'series'> = {
    legend: {
      right: 10,
      top: 5,
      data: [t('High Confidence'), t('Low Confidence')],
    },
    seriesOptions: {
      showSymbol: false,
    },
    height,
    tooltip: {
      trigger: 'axis',
      valueFormatter: (value, label) =>
        tooltipFormatter(value, aggregateOutputType(label)),
    },
    xAxis: undefined,
    yAxis: {
      axisLabel: {
        // Coerces the axis to be count based
        formatter: (value: number) => axisLabelFormatter(value, 'number'),
      },
    },
  };

  return (
    <ChartZoom period={statsPeriod} start={start} end={end} utc={utc === 'true'}>
      {zoomRenderProps => (
        <LineChart {...zoomRenderProps} series={data} {...chartOptions} />
      )}
    </ChartZoom>
  );
}
