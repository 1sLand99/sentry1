import {useRef} from 'react';

import {Flex} from '@sentry/scraps/layout';

import SplitPanel from 'sentry/components/splitPanel';
import {useDimensions} from 'sentry/utils/useDimensions';
import type {useMetricTimeseries} from 'sentry/views/explore/metrics/hooks/useMetricTimeseries';
import type {TableOrientation} from 'sentry/views/explore/metrics/hooks/useOrientationControl';
import {MetricsGraph} from 'sentry/views/explore/metrics/metricGraph';
import MetricInfoTabs from 'sentry/views/explore/metrics/metricInfoTabs';
import {SAMPLES_PANEL_MIN_WIDTH} from 'sentry/views/explore/metrics/metricInfoTabs/samplesTab';
import {HideContentButton} from 'sentry/views/explore/metrics/metricPanel/hideContentButton';
import {PanelPositionSelector} from 'sentry/views/explore/metrics/metricPanel/panelPositionSelector';
import type {TraceMetric} from 'sentry/views/explore/metrics/metricQuery';

const MIN_LEFT_WIDTH = 400;

// Defined by the size of the expected samples tab component
const PADDING_SIZE = 16;
const MIN_RIGHT_WIDTH = SAMPLES_PANEL_MIN_WIDTH + PADDING_SIZE;

export function SideBySideOrientation({
  timeseriesResult,
  queryIndex,
  traceMetric,
  orientation,
  setOrientation,
  infoContentHidden,
  setInfoContentHidden,
}: {
  infoContentHidden: boolean;
  orientation: TableOrientation;
  queryIndex: number;
  setInfoContentHidden: (hidden: boolean) => void;
  setOrientation: (orientation: TableOrientation) => void;
  timeseriesResult: ReturnType<typeof useMetricTimeseries>['result'];
  traceMetric: TraceMetric;
}) {
  const measureRef = useRef<HTMLDivElement>(null);
  const {width} = useDimensions({elementRef: measureRef});

  const hasSize = width > 0;
  // Default split is 65% of the available width, but not less than MIN_LEFT_WIDTH
  // and at most the maximum size allowed for the left panel (i.e. width - MIN_RIGHT_WIDTH)
  const defaultSplit = Math.min(
    Math.max(width * 0.65, MIN_LEFT_WIDTH),
    width - MIN_RIGHT_WIDTH
  );

  const additionalActions = (
    <Flex direction="row" marginTop={infoContentHidden ? undefined : 'md'}>
      <PanelPositionSelector
        orientation={orientation}
        setOrientation={setOrientation}
        disabled={infoContentHidden}
      />
      <HideContentButton
        orientation={orientation}
        infoContentHidden={infoContentHidden}
        onToggle={() => setInfoContentHidden(!infoContentHidden)}
      />
    </Flex>
  );

  if (infoContentHidden) {
    return (
      <div ref={measureRef}>
        <MetricsGraph
          timeseriesResult={timeseriesResult}
          queryIndex={queryIndex}
          orientation={orientation}
          additionalActions={additionalActions}
          infoContentHidden={infoContentHidden}
        />
      </div>
    );
  }

  return (
    <div ref={measureRef}>
      {hasSize ? (
        <SplitPanel
          availableSize={width}
          left={{
            content: (
              <MetricsGraph
                timeseriesResult={timeseriesResult}
                queryIndex={queryIndex}
                orientation={orientation}
              />
            ),
            default: defaultSplit,
            min: MIN_LEFT_WIDTH,
            max: width - MIN_RIGHT_WIDTH,
          }}
          right={
            <MetricInfoTabs
              traceMetric={traceMetric}
              additionalActions={additionalActions}
              orientation={orientation}
            />
          }
        />
      ) : null}
    </div>
  );
}
