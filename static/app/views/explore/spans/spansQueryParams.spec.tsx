import type {Location} from 'history';
import {LocationFixture} from 'sentry-fixture/locationFixture';

import {initializeOrg} from 'sentry-test/initializeOrg';

import {Mode} from 'sentry/views/explore/queryParams/mode';
import type {ReadableQueryParamsOptions} from 'sentry/views/explore/queryParams/readableQueryParams';
import {ReadableQueryParams} from 'sentry/views/explore/queryParams/readableQueryParams';
import {Visualize} from 'sentry/views/explore/queryParams/visualize';
import {getReadableQueryParamsFromLocation} from 'sentry/views/explore/spans/spansQueryParams';
import {ChartType} from 'sentry/views/insights/common/components/chart';

function locationFixture(query: Location['query']): Location {
  return LocationFixture({query});
}

function readableQueryParamOptions(
  options: Partial<ReadableQueryParamsOptions> = {}
): ReadableQueryParamsOptions {
  return {
    mode: Mode.SAMPLES,
    query: '',
    cursor: '',
    fields: [
      'id',
      'span.op',
      'span.description',
      'span.duration',
      'transaction',
      'timestamp',
    ],
    sortBys: [{field: 'timestamp', kind: 'desc'}],
    aggregateCursor: '',
    aggregateFields: [{groupBy: ''}, new Visualize('count(span.duration)')],
    aggregateSortBys: [
      {
        field: 'count(span.duration)',
        kind: 'desc',
      },
    ],
    ...options,
  };
}

describe('getReadableQueryParamsFromLocation', function () {
  const {organization} = initializeOrg();

  it('decodes defaults correctly', function () {
    const location = locationFixture({});
    const queryParams = getReadableQueryParamsFromLocation(location, organization);
    expect(queryParams).toEqual(new ReadableQueryParams(readableQueryParamOptions()));
  });

  it('decodes samples mode correctly', function () {
    const location = locationFixture({mode: 'samples'});
    const queryParams = getReadableQueryParamsFromLocation(location, organization);
    expect(queryParams).toEqual(
      new ReadableQueryParams(readableQueryParamOptions({mode: Mode.SAMPLES}))
    );
  });

  it('decodes aggregate mode correctly', function () {
    const location = locationFixture({mode: 'aggregate'});
    const queryParams = getReadableQueryParamsFromLocation(location, organization);
    expect(queryParams).toEqual(
      new ReadableQueryParams(readableQueryParamOptions({mode: Mode.AGGREGATE}))
    );
  });

  it('defaults to samples mode for invalid mode values', function () {
    const location = locationFixture({mode: 'invalid'});
    const queryParams = getReadableQueryParamsFromLocation(location, organization);
    expect(queryParams).toEqual(
      new ReadableQueryParams(readableQueryParamOptions({mode: Mode.SAMPLES}))
    );
  });

  it('decodes empty query correctly', function () {
    const location = locationFixture({query: ''});
    const queryParams = getReadableQueryParamsFromLocation(location, organization);
    expect(queryParams).toEqual(
      new ReadableQueryParams(readableQueryParamOptions({query: ''}))
    );
  });

  it('decodes custom query parameter correctly', function () {
    const location = locationFixture({query: 'span.op:db'});
    const queryParams = getReadableQueryParamsFromLocation(location, organization);
    expect(queryParams).toEqual(
      new ReadableQueryParams(readableQueryParamOptions({query: 'span.op:db'}))
    );
  });

  it('decodes empty cursor correctly', function () {
    const location = locationFixture({cursor: ''});
    const queryParams = getReadableQueryParamsFromLocation(location, organization);
    expect(queryParams).toEqual(
      new ReadableQueryParams(
        readableQueryParamOptions({cursor: '', aggregateCursor: ''})
      )
    );
  });

  it('decodes custom cursor parameter correctly', function () {
    const location = locationFixture({cursor: '0:0:1'});
    const queryParams = getReadableQueryParamsFromLocation(location, organization);
    expect(queryParams).toEqual(
      new ReadableQueryParams(
        readableQueryParamOptions({cursor: '0:0:1', aggregateCursor: '0:0:1'})
      )
    );
  });

  it('decodes empty fields correctly', function () {
    const location = locationFixture({field: []});
    const queryParams = getReadableQueryParamsFromLocation(location, organization);
    expect(queryParams).toEqual(
      new ReadableQueryParams(
        readableQueryParamOptions({
          fields: [
            'id',
            'span.op',
            'span.description',
            'span.duration',
            'transaction',
            'timestamp',
          ],
        })
      )
    );
  });

  it('decodes empty fields correctly for otel', function () {
    const {organization: org} = initializeOrg({
      organization: {
        features: ['performance-otel-friendly-ui'],
      },
    });

    const location = locationFixture({field: []});
    const queryParams = getReadableQueryParamsFromLocation(location, org);
    expect(queryParams).toEqual(
      new ReadableQueryParams(
        readableQueryParamOptions({
          fields: ['id', 'span.name', 'span.duration', 'timestamp'],
        })
      )
    );
  });

  it('decodes custom fields correctly', function () {
    const location = locationFixture({
      field: ['id', 'span.op', 'span.duration', 'timestamp'],
    });
    const queryParams = getReadableQueryParamsFromLocation(location, organization);
    expect(queryParams).toEqual(
      new ReadableQueryParams(
        readableQueryParamOptions({
          fields: ['id', 'span.op', 'span.duration', 'timestamp'],
        })
      )
    );
  });

  it('decodes custom sortBys correctly', function () {
    const location = locationFixture({sort: ['-span.duration', 'timestamp']});
    const queryParams = getReadableQueryParamsFromLocation(location, organization);
    expect(queryParams).toEqual(
      new ReadableQueryParams(
        readableQueryParamOptions({
          sortBys: [
            {field: 'span.duration', kind: 'desc'},
            {field: 'timestamp', kind: 'asc'},
          ],
        })
      )
    );
  });

  it('uses timestamp sort when fields include timestamp', function () {
    const location = locationFixture({field: ['id', 'span.op', 'timestamp'], sort: []});
    const queryParams = getReadableQueryParamsFromLocation(location, organization);
    expect(queryParams).toEqual(
      new ReadableQueryParams(
        readableQueryParamOptions({
          fields: ['id', 'span.op', 'timestamp'],
          sortBys: [{field: 'timestamp', kind: 'desc'}],
        })
      )
    );
  });

  it('falls back to first field when fields do not include timestamp', function () {
    const location = locationFixture({field: ['id', 'span.op'], sort: []});
    const queryParams = getReadableQueryParamsFromLocation(location, organization);
    expect(queryParams).toEqual(
      new ReadableQueryParams(
        readableQueryParamOptions({
          fields: ['id', 'span.op'],
          sortBys: [{field: 'id', kind: 'desc'}],
        })
      )
    );
  });

  it('decodes empty sort correctly', function () {
    const location = locationFixture({sort: []});
    const queryParams = getReadableQueryParamsFromLocation(location, organization);
    expect(queryParams).toEqual(
      new ReadableQueryParams(
        readableQueryParamOptions({
          sortBys: [{field: 'timestamp', kind: 'desc'}],
        })
      )
    );
  });

  it('decodes custom group bys correctly', function () {
    const location = locationFixture({groupBy: ['span.op', 'transaction']});
    const queryParams = getReadableQueryParamsFromLocation(location, organization);
    expect(queryParams).toEqual(
      new ReadableQueryParams(
        readableQueryParamOptions({
          aggregateFields: [
            {groupBy: 'span.op'},
            {groupBy: 'transaction'},
            new Visualize('count(span.duration)'),
          ],
        })
      )
    );
  });

  it('decodes custom visualizes correctly', function () {
    const location = locationFixture({
      visualize: JSON.stringify({yAxes: ['count(span.duration)', 'avg(span.self_time)']}),
    });
    const queryParams = getReadableQueryParamsFromLocation(location, organization);
    expect(queryParams.aggregateFields).toHaveLength(3);
    expect(queryParams.aggregateFields[0]).toEqual({groupBy: ''});
    expect(queryParams.aggregateFields[1]).toEqual(new Visualize('count(span.duration)'));
    expect(queryParams.aggregateFields[2]).toEqual(new Visualize('avg(span.self_time)'));
    expect(queryParams).toEqual(
      new ReadableQueryParams(
        readableQueryParamOptions({
          aggregateFields: [
            {groupBy: ''},
            new Visualize('count(span.duration)'),
            new Visualize('avg(span.self_time)'),
          ],
        })
      )
    );
  });

  it('decodes custom visualizes with chart type correctly', function () {
    const location = locationFixture({
      visualize: JSON.stringify({
        yAxes: ['count(span.duration)', 'avg(span.self_time)'],
        chartType: ChartType.LINE,
      }),
    });
    const queryParams = getReadableQueryParamsFromLocation(location, organization);
    expect(queryParams).toEqual(
      new ReadableQueryParams(
        readableQueryParamOptions({
          aggregateFields: [
            {groupBy: ''},
            new Visualize('count(span.duration)', {chartType: ChartType.LINE}),
            new Visualize('avg(span.self_time)', {chartType: ChartType.LINE}),
          ],
        })
      )
    );
  });

  it('decodes custom aggregate fields correctly', function () {
    const location = locationFixture({
      aggregateField: [
        {yAxes: ['count(span.duration)'], chartType: ChartType.AREA},
        {groupBy: 'span.op'},
        {yAxes: ['p50(span.duration)', 'p75(span.duration)']},
      ].map(aggregateField => JSON.stringify(aggregateField)),
    });
    const queryParams = getReadableQueryParamsFromLocation(location, organization);
    expect(queryParams).toEqual(
      new ReadableQueryParams(
        readableQueryParamOptions({
          aggregateFields: [
            new Visualize('count(span.duration)', {chartType: ChartType.AREA}),
            {groupBy: 'span.op'},
            new Visualize('p50(span.duration)'),
            new Visualize('p75(span.duration)'),
          ],
        })
      )
    );
  });

  it('decodes custom aggregatefields and inserts default group bys', function () {
    const location = locationFixture({
      aggregateField: [
        JSON.stringify({yAxes: ['count(span.duration)'], chartType: ChartType.LINE}),
      ],
    });
    const queryParams = getReadableQueryParamsFromLocation(location, organization);
    expect(queryParams).toEqual(
      new ReadableQueryParams(
        readableQueryParamOptions({
          aggregateFields: [
            new Visualize('count(span.duration)', {chartType: ChartType.LINE}),
            {groupBy: ''},
          ],
        })
      )
    );
  });

  it('decodes custom aggregatefields and inserts default visualizes', function () {
    const location = locationFixture({
      aggregateField: [JSON.stringify({groupBy: 'span.op'})],
    });
    const queryParams = getReadableQueryParamsFromLocation(location, organization);
    expect(queryParams.aggregateFields).toHaveLength(2);
    expect(queryParams.aggregateFields[0]).toEqual({groupBy: 'span.op'});
    expect(queryParams.aggregateFields[1]).toEqual(new Visualize('count(span.duration)'));
    expect(queryParams).toEqual(
      new ReadableQueryParams(
        readableQueryParamOptions({
          aggregateFields: [{groupBy: 'span.op'}, new Visualize('count(span.duration)')],
        })
      )
    );
  });

  it('decodes custom aggregate sort bys correctly', function () {
    const location = locationFixture({
      aggregateField: [
        {groupBy: 'span.op'},
        {yAxes: ['p50(span.duration)']},
        {yAxes: ['avg(span.duration)'], chartType: ChartType.AREA},
      ].map(aggregateField => JSON.stringify(aggregateField)),
      aggregateSort: ['-span.op', 'avg(span.duration)'],
    });
    const queryParams = getReadableQueryParamsFromLocation(location, organization);
    expect(queryParams).toEqual(
      new ReadableQueryParams(
        readableQueryParamOptions({
          aggregateFields: [
            {groupBy: 'span.op'},
            new Visualize('p50(span.duration)'),
            new Visualize('avg(span.duration)', {chartType: ChartType.AREA}),
          ],
          aggregateSortBys: [
            {field: 'span.op', kind: 'desc'},
            {field: 'avg(span.duration)', kind: 'asc'},
          ],
        })
      )
    );
  });

  it('decodes invalid aggregate sorts and falls back to first visualize', function () {
    const location = locationFixture({
      aggregateField: [{groupBy: ''}, {yAxes: ['p50(span.duration)']}].map(
        aggregateField => JSON.stringify(aggregateField)
      ),
      aggregateSort: ['-avg(span.duration)'],
    });
    const queryParams = getReadableQueryParamsFromLocation(location, organization);
    expect(queryParams).toEqual(
      new ReadableQueryParams(
        readableQueryParamOptions({
          aggregateFields: [{groupBy: ''}, new Visualize('p50(span.duration)')],
          aggregateSortBys: [{field: 'p50(span.duration)', kind: 'desc'}],
        })
      )
    );
  });
});
