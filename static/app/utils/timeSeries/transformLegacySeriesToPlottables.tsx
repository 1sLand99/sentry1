import type {Series} from 'sentry/types/echarts';
import type {EventsStats} from 'sentry/types/organization';
import {
  aggregateOutputType,
  type AggregationOutputType,
} from 'sentry/utils/discover/fields';
import type {Widget} from 'sentry/views/dashboards/types';
import {DisplayType} from 'sentry/views/dashboards/types';
import type {TimeSeries} from 'sentry/views/dashboards/widgets/common/types';
import {Area} from 'sentry/views/dashboards/widgets/timeSeriesWidget/plottables/area';
import {Bars} from 'sentry/views/dashboards/widgets/timeSeriesWidget/plottables/bars';
import {Line} from 'sentry/views/dashboards/widgets/timeSeriesWidget/plottables/line';
import type {Plottable} from 'sentry/views/dashboards/widgets/timeSeriesWidget/plottables/plottable';
import {convertEventsStatsToTimeSeriesData} from 'sentry/views/insights/common/queries/useSortedTimeSeries';

/**
 * Transforms legacy Series[] data into Plottable[] objects for the TimeSeriesWidgetVisualization component.
 */
export function transformLegacySeriesToPlottables(
  timeseriesResults: Series[] | undefined,
  timeseriesResultsTypes: Record<string, AggregationOutputType> | undefined,
  widget: Widget
): Plottable[] {
  if (!timeseriesResults || timeseriesResults.length === 0) {
    return [];
  }

  const plottables = timeseriesResults
    .map(series => {
      const fieldType =
        timeseriesResultsTypes?.[series.seriesName] ??
        aggregateOutputType(series.seriesName);
      const {valueType, valueUnit} = mapAggregationTypeToValueTypeAndUnit(fieldType);
      const timeSeries = convertEventsStatsToTimeSeriesData(
        series.seriesName,
        createEventsStatsFromSeries(series, valueType as AggregationOutputType, valueUnit)
      );
      return createPlottableFromTimeSeries(timeSeries[1], widget.displayType);
    })
    .filter(plottable => plottable !== null);
  return plottables;
}

function createEventsStatsFromSeries(
  series: Series,
  valueType: AggregationOutputType,
  valueUnit: string | null
): EventsStats {
  return {
    data: series.data.map(dataUnit => [
      typeof dataUnit.name === 'number'
        ? dataUnit.name
        : new Date(dataUnit.name).getTime() / 1000,
      [{count: dataUnit.value, comparisonCount: undefined}],
    ]),
    meta: {
      fields: {
        [series.seriesName]: valueType,
      },
      units: {
        [series.seriesName]: valueUnit,
      },
      isMetricsData: false,
      tips: {columns: undefined, query: undefined},
    },
  };
}

function createPlottableFromTimeSeries(
  timeSeries: TimeSeries,
  displayType: DisplayType
): Plottable | null {
  switch (displayType) {
    case DisplayType.LINE:
      return new Line(timeSeries);
    case DisplayType.AREA:
      return new Area(timeSeries);
    case DisplayType.BAR:
      return new Bars(timeSeries);
    default:
      return null;
  }
}

function mapAggregationTypeToValueTypeAndUnit(aggregationType: AggregationOutputType): {
  valueType: TimeSeries['meta']['valueType'];
  valueUnit: TimeSeries['meta']['valueUnit'];
} {
  switch (aggregationType) {
    case 'percentage':
      return {valueType: 'percentage', valueUnit: null};
    case 'integer':
    case 'number':
    default:
      return {valueType: 'number', valueUnit: null};
  }
}
