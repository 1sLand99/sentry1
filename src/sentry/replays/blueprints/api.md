# Replays API

Host: https://sentry.io/api/0

**Authors.**

@cmanallen
@joshferge

**How to read this document.**

This document is structured by resource with each resource having actions that can be performed against it. Every action that either accepts a request or returns a response WILL document the full interchange format. Clients may opt to restrict response data or provide a subset of the request data. The API may or may not accept partial payloads.

## Replays [/organizations/<organization_id_or_slug>/replays/]

- Parameters
  - field (optional, string)
  - environment (optional, string)
  - project (optional, string)
  - sort, sortBy, orderBy (optional, string)
    Default: -startedAt
    Members: + projectId + -projectId + startedAt + -startedAt + finishedAt + -finishedAt + duration + -duration + countErrors + -countErrors
  - statsPeriod (optional, string) - A positive integer suffixed with a unit type.
    Default: 7d
    Members: + s + m + h + d + w
  - start (optional, string) - ISO 8601 format (`YYYY-MM-DDTHH:mm:ss.sssZ`)
  - end (optional, string) - ISO 8601 format. Required if `start` is set.
  - per_page (optional, number)
    Default: 10
  - offset (optional, number)
    Default: 0
  - query (optional, string) - Search query with space-separated field/value pairs. ie: `?query=count_errors:>2 AND duration:<1h`.
  - queryReferrer(optional, string) - Specify the page which this query is being made from.
    Some fields in the API response have their own dedicated parameters, or are otherwide not supported in the `query` param. They are:

    | Response Field      | Parameter       |
    | ------------------- | --------------- |
    | `environment`       | `?environment=` |
    | `project_id`        | `?project=`     |
    | `started_at`        | `?start=`       |
    | `finished_at`       | `?end=`         |
    | `user.display_name` | -               |

    You can use the following aliases to query for fields that are plural in the API response:

    | Response Field | Search Alias         |
    | -------------- | -------------------- |
    | `error_ids`    | `error_id`           |
    | `releases`     | `release`            |
    | `trace_ids`    | `trace` & `trace_id` |
    | `urls`         | `url`                |

    Additionally, you can filter by these hidden fields.

    | Field                | Type          | Description                                                    |
    | -------------------- | ------------- | -------------------------------------------------------------- |
    | click.alt            | string        | The alt attribute of the HTML element.                         |
    | click.class          | array[string] | An array of HTML element classes.                              |
    | click.id             | string        | The ID of an HTML element.                                     |
    | click.label          | string        | The aria-label attribute of an HTML element.                   |
    | click.component_name | string        | The value of the data-sentry-component attribute.              |
    | click.role           | string        | The role of an HTML element.                                   |
    | click.tag            | string        | Valid HTML5 tag name.                                          |
    | click.testid         | string        | The data-testid of an HTML element. (omitted from public docs) |
    | click.textContent    | string        | The text-content of an HTML element.                           |
    | click.title          | string        | The title attribute of an HTML element.                        |
    | click.selector       | string        | A valid CSS selector.                                          |
    | dead.selector        | string        | A valid CSS selector.                                          |
    | rage.selector        | string        | A valid CSS selector.                                          |

### Browse Replays [GET]

Retrieve a collection of replays.

**Attributes**

| Column            | Type                          | Description                                            |
| ----------------- | ----------------------------- | ------------------------------------------------------ |
| activity          | number                        | -                                                      |
| browser.name      | optional[string]              | -                                                      |
| browser.version   | optional[string]              | -                                                      |
| count_dead_clicks | number                        | The number of dead clicks present in the replay.       |
| count_rage_clicks | number                        | The number of rage clicks present in the replay.       |
| count_errors      | number                        | The number of errors associated with the replay.       |
| count_segments    | number                        | The number of segments that make up the replay.        |
| count_urls        | number                        | The number of urls visited in the replay.              |
| device.brand      | optional[string]              | -                                                      |
| device.family     | optional[string]              | -                                                      |
| device.model      | optional[string]              | Same search field as Events                            |
| device.name       | optional[string]              | -                                                      |
| dist              | optional[string]              | -                                                      |
| duration          | number                        | Difference of `finishedAt` and `startedAt` in seconds. |
| environment       | optional[string]              | -                                                      |
| error_ids         | array[string]                 | -                                                      |
| finished_at       | string                        | The **latest** timestamp received.                     |
| has_viewed        | bool                          | True if the authorized user has viewed the replay.     |
| id                | string                        | The ID of the Replay instance.                         |
| is_archived       | bool                          | Whether the replay was deleted or not.                 |
| os.name           | optional[string]              | -                                                      |
| os.version        | optional[string]              | -                                                      |
| platform          | string                        | -                                                      |
| project_id        | string                        | -                                                      |
| releases          | array[string]                 | Same search field as Events                            |
| sdk.name          | string                        | -                                                      |
| sdk.version       | string                        | -                                                      |
| started_at        | string                        | The **earliest** replay_start_timestamp received.      |
| tags              | object[string, array[string]] | -                                                      |
| trace_ids         | array[string]                 | Same search field as Events                            |
| urls              | array[string]                 | -                                                      |
| user.display_name | optional[string]              | -                                                      |
| user.email        | optional[string]              | -                                                      |
| user.id           | optional[string]              | -                                                      |
| user.ip           | optional[string]              | Same search field as Events                            |
| user.username     | optional[string]              | -                                                      |

- Response 200

  ```json
  {
    "data": [
      {
        "activity": 5,
        "browser": {
          "name": "Chome",
          "version": "103.0.38"
        },
        "count_dead_clicks": 6,
        "count_rage_clicks": 1,
        "count_errors": 1,
        "count_segments": 0,
        "count_urls": 1,
        "device": {
          "brand": "Apple",
          "family": "iPhone",
          "model": "11",
          "name": "iPhone 11"
        },
        "dist": null,
        "duration": 576,
        "environment": "production",
        "error_ids": ["7e07485f-12f9-416b-8b14-26260799b51f"],
        "finished_at": "2022-07-07T14:15:33.201019",
        "has_viewed": true,
        "id": "7e07485f-12f9-416b-8b14-26260799b51f",
        "is_archived": false,
        "os": {
          "name": "iOS",
          "version": "16.2"
        },
        "platform": "Sentry",
        "project_id": "639195",
        "releases": ["version@1.4"],
        "sdk": {
          "name": "Thundercat",
          "version": "27.1"
        },
        "started_at": "2022-07-07T14:05:57.909921",
        "tags": {
          "hello": ["world", "Lionel Richie"]
        },
        "trace_ids": ["7e07485f-12f9-416b-8b14-26260799b51f"],
        "urls": ["/organizations/abc123/issues"],
        "user": {
          "display_name": "John Doe",
          "email": "john.doe@example.com",
          "id": "30246326",
          "ip": "213.164.1.114",
          "username": "John Doe"
        }
      }
    ]
  }
  ```

## Replay [/projects/<organization_id_or_slug>/<project_id_or_slug>/replays/<replay_id>/]

- Parameters
  - field (optional, string)

### Fetch Replay [GET]

Retrieve a single replay instance.

- Response 200

  ```json
  {
    "data": {
      "activity": 5,
      "browser": {
        "name": "Chome",
        "version": "103.0.38"
      },
      "count_dead_clicks": 6,
      "count_rage_clicks": 1,
      "count_errors": 1,
      "count_segments": 0,
      "count_urls": 1,
      "device": {
        "brand": "Apple",
        "family": "iPhone",
        "model": "11",
        "name": "iPhone 11"
      },
      "dist": null,
      "duration": 576,
      "environment": "production",
      "error_ids": ["7e07485f-12f9-416b-8b14-26260799b51f"],
      "finished_at": "2022-07-07T14:15:33.201019",
      "has_viewed": false,
      "id": "7e07485f-12f9-416b-8b14-26260799b51f",
      "os": {
        "name": "iOS",
        "version": "16.2"
      },
      "platform": "Sentry",
      "project_id": "639195",
      "releases": ["version@1.4"],
      "sdk": {
        "name": "Thundercat",
        "version": "27.1"
      },
      "started_at": "2022-07-07T14:05:57.909921",
      "tags": {
        "hello": ["world", "Lionel Richie"]
      },
      "trace_ids": ["7e07485f-12f9-416b-8b14-26260799b51f"],
      "urls": ["/organizations/abc123/issues"],
      "user": {
        "display_name": "John Doe",
        "email": "john.doe@example.com",
        "id": "30246326",
        "ip": "213.164.1.114",
        "username": "John Doe"
      }
    }
  }
  ```

### Delete Replay [DELETE]

Deletes a replay instance.

- Response 204

## Replay Selectors [/organizations/<organization_id_or_slug>/replay-selectors/]

- Parameters
  - project (optional, string)
  - sort, sortBy, orderBy (optional, string)
    Default: -count_dead_clicks
    Members:
    - count_dead_clicks
    - -count_dead_clicks
    - count_rage_clicks
    - -count_rage_clicks
  - statsPeriod (optional, string) - A positive integer suffixed with a unit type.
    Default: 7d
    Members:
    - s
    - m
    - h
    - d
    - w
  - start (optional, string) - ISO 8601 format (`YYYY-MM-DDTHH:mm:ss.sssZ`)
  - end (optional, string) - ISO 8601 format. Required if `start` is set.
  - environment (optional, string)
  - per_page (optional, number)
    Default: 10
  - offset (optional, number)
    Default: 0

### Browse Replay Selectors [GET]

Retrieve a collection of selectors.

**Attributes**

| Column                 | Type          | Description                                        |
| ---------------------- | ------------- | -------------------------------------------------- |
| count_dead_clicks      | number        | The number of dead clicks for a given DOM element. |
| count_rage_clicks      | number        | The number of rage clicks for a given DOM element. |
| dom_element            | string        | -                                                  |
| element.alt            | string        | -                                                  |
| element.aria_label     | string        | -                                                  |
| element.class          | array[string] | -                                                  |
| element.component_name | string        | -                                                  |
| element.id             | string        | -                                                  |
| element.role           | string        | -                                                  |
| element.tag            | string        | -                                                  |
| element.testid         | string        | -                                                  |
| element.title          | string        | -                                                  |
| project_id             | string        | -                                                  |

- Response 200

  ```json
  {
    "data": [
      {
        "count_dead_clicks": 2,
        "count_rage_clicks": 1,
        "dom_element": "div#myid.class1.class2",
        "element": {
          "alt": "",
          "aria_label": "",
          "class": ["class1", "class2"],
          "component_name": "",
          "id": "myid",
          "role": "",
          "tag": "div",
          "testid": "",
          "title": ""
        },
        "project_id": "1"
      }
    ]
  }
  ```

## Replay Recording Segments [/projects/<organization_id_or_slug>/<project_id_or_slug>/replays/<replay_id>/recording-segments/]

- Parameters
  - per_page
  - cursor
  - download - Instruct the API to return a streaming json response

### Browse Replay Recording Segments [GET]

Retrieve a collection of replay recording-segments.

| Column    | Type   | Description |
| --------- | ------ | ----------- |
| replayId  | string | -           |
| segmentId | number | -           |
| projectId | string | -           |
| dateAdded | string | -           |

Without download query argument

- Response 200

  ```json
  {
    "data": [
      {
        "replayId": "7e07485f-12f9-416b-8b14-26260799b51f",
        "segmentId": 0,
        "projectId": "409512",
        "dateAdded": "2022-07-07T14:15:33.201019"
      }
    ]
  }
  ```

With download query argument, rrweb events JSON

- Response 200
  Content-Type application/json

  ```json
  [
    [
      {"type":4, "data":{"href":"https://example.com", "width":1500, "height":1200}},
      {...}
    ],
    [
      {...}
    ]
  ]
  ```

## Replay Recording Segment [/projects/<organization_id_or_slug>/<project_id_or_slug>/replays/<replay_id>/recording-segments/<segment_id>/]

- Parameters
  - download - Instruct the API to return a streaming bytes response.

### Fetch Replay Recording Segment [GET]

Retrieve a single replay recording-segment.

Without download query argument.

- Response 200

  ```json
  {
    "data": {
      "replayId": "7e07485f-12f9-416b-8b14-26260799b51f",
      "segmentId": 0,
      "projectId": 409512,
      "dateAdded": "2022-07-07T14:15:33.201019"
    }
  }
  ```

With download query argument.

- Response 200

  Content-Type application/octet-stream

## Replay Video [/projects/<organization_id_or_slug>/<project_id_or_slug>/replays/<replay_id>/videos/<segment_id>/]

### Fetch Replay Video [GET]

Returns the bytes of a replay-segment video.

- Response 200

  ```
  \x00\x00\x00
  ```

## Replay Tag Keys [/projects/<organization_id_or_slug>/<project_id_or_slug>/replays/tags/]

### Fetch Tag Keys [GET]

Retrieve a collection of tag keys associated with the replays dataset.

| Column      | Type   | Description |
| ----------- | ------ | ----------- |
| key         | string | -           |
| name        | string | -           |
| totalValues | number | -           |

- Response 200

  ```json
  [
    {
      "key": "plan.total_members",
      "name": "Plan.Total Members",
      "totalValues": 630661
    }
  ]
  ```

## Replay Tag Values [/projects/<organization_id_or_slug>/<project_id_or_slug>/replays/tags/<key>/values/]

### Fetch Tag Values [GET]

Retrieve a collection of tag values associated with a tag key on the replays dataset.

| Column    | Type   | Description |
| --------- | ------ | ----------- |
| key       | string | -           |
| name      | string | -           |
| value     | string | -           |
| count     | number | -           |
| lastSeen  | string | -           |
| firstSeen | string | -           |

- Response 200

  ```json
  [
    {
      "key": "plan",
      "name": "am1_team",
      "value": "am1_team",
      "count": 66880,
      "lastSeen": "2022-12-09T19:39:53Z",
      "firstSeen": "2022-11-25T19:40:39Z"
    }
  ]
  ```

## Replay Click [/projects/<organization_id_or_slug>/<project_id_or_slug>/replays/<replay_id>/clicks/]

Parameters:

| Parameter | Type   | Default | Description                                  |
| --------- | ------ | ------- | -------------------------------------------- |
| per_page  | number | 100     |                                              |
| offset    | number | 0       |                                              |
| query     | string | 0       | Space-separated string of field, value pairs |

Queryable fields:

| Field                | Type          | Description                                                    |
| -------------------- | ------------- | -------------------------------------------------------------- |
| click.alt            | string        | The alt attribute of the HTML element.                         |
| click.class          | array[string] | An array of HTML element classes.                              |
| click.id             | string        | The ID of an HTML element.                                     |
| click.label          | string        | The aria-label attribute of an HTML element.                   |
| click.component_name | string        | The value of the data-sentry-component attribute.              |
| click.role           | string        | The role of an HTML element.                                   |
| click.selector       | string        | A valid CSS selector.                                          |
| click.tag            | string        | Valid HTML5 tag name.                                          |
| click.testid         | string        | The data-testid of an HTML element. (omitted from public docs) |
| click.textContent    | string        | The text-content of an HTML element.                           |
| click.title          | string        | The title attribute of an HTML element.                        |

Queryable fields for rage and dead clicks:

| Field         | Type   | Description           |
| ------------- | ------ | --------------------- |
| dead.selector | string | A valid CSS selector. |
| rage.selector | string | A valid CSS selector. |

### Fetch Replay Clicks [GET]

Retrieve a collection of click events associated with a replay.

| Column    | Type   | Description                    |
| --------- | ------ | ------------------------------ |
| node_id   | number | RRWeb node id.                 |
| timestamp | number | Unix timestamp of click event. |

- Response 200

  ```json
  {
    "data": [
      {
        "node_id": 339,
        "timestamp": 1681226444
      }
    ]
  }
  ```

## Replay Viewed By [/projects/<organization_id_or_slug>/<project_id_or_slug>/replays/<replay_id>/viewed-by/]

### Fetch Replay Viewed By [GET]

| Column    | Type        | Description                                        |
| --------- | ----------- | -------------------------------------------------- |
| viewed_by | array[User] | An array of user types who have viewed the replay. |

- Response 200

  ```json
  {
    "data": {
      "viewed_by": [
        {
          "id": "884411",
          "name": "some.body@sentry.io",
          "username": "d93522a35cb64c13991104bd73d44519",
          "email": "some.body@sentry.io",
          "avatarUrl": "https://gravatar.com/avatar/d93522a35cb64c13991104bd73d44519d93522a35cb64c13991104bd73d44519?s=32&d=mm",
          "isActive": true,
          "hasPasswordAuth": false,
          "isManaged": false,
          "dateJoined": "2022-07-25T23:36:29.593212Z",
          "lastLogin": "2024-03-14T18:11:28.740309Z",
          "has2fa": true,
          "lastActive": "2024-03-15T22:22:06.925934Z",
          "isSuperuser": true,
          "isStaff": false,
          "experiments": {},
          "emails": [
            {
              "id": "2231333",
              "email": "some.body@sentry.io",
              "is_verified": true
            }
          ],
          "avatar": {
            "avatarType": "upload",
            "avatarUuid": "499dcd0764da42a589654a2224086e67",
            "avatarUrl": "https://sentry.io/avatar/499dcd0764da42a589654a2224086e67/"
          },
          "type": "user"
        }
      ]
    }
  }
  ```

### Create Replay Viewed [POST]

A POST request is issued with no body. The URL and authorization context is used to construct a new viewed replay entry.

- Request
  - Headers

    Cookie: \_ga=GA1.2.17576183...

- Response 204

## Replay Summarize Breadcrumb [/projects/<organization_id_or_slug>/<project_id_or_slug>/replays/<replay_id>/summarize/breadcrumbs/]

### Fetch Replay Breadcrumb Summary [GET]

| Column                   | Type            | Description                                                                                   |
| ------------------------ | --------------- | --------------------------------------------------------------------------------------------- |
| title                    | str             | The main title of the user journey summary.                                                   |
| summary                  | str             | A concise summary featuring the highlights of the user's journey while using the application. |
| time_ranges              | list[TimeRange] | A list of TimeRange objects.                                                                  |
| time_ranges.period_start | number          | The start time (UNIX timestamp) of the analysis window.                                       |
| time_ranges.period_end   | number          | The end time (UNIX timestamp) of the analysis window.                                         |
| time_ranges.period_title | str             | A concise summary utilizing 6 words or fewer describing what happened during the time range.  |

- Response 200

  ```json
  {
    "data": {
      "title": "Something Happened",
      "summary": "The application broke",
      "time_ranges": [
        {
          "period_start": 1749584581.5356228,
          "period_end": 1749584992.912,
          "period_title": "Second Replay Load Failure"
        }
      ]
    }
  }
  ```

## Replay Deletion Jobs [/projects/<organization_id_or_slug>/<project_id_or_slug>/replays/jobs/delete/]

- Parameters
  - per_page (optional, number)
    Default: 10
  - offset (optional, number)
    Default: 0

### List Replay Deletion Jobs [GET]

Retrieve a collection of replay delete jobs.

**Attributes**

| Column       | Type         | Description                                                                                                                |
| ------------ | ------------ | -------------------------------------------------------------------------------------------------------------------------- |
| id           | string       | -                                                                                                                          |
| dateCreated  | string       | -                                                                                                                          |
| dateUpdated  | string       | -                                                                                                                          |
| rangeStart   | string       | The minimum UTC timestamp in the deletion range.                                                                           |
| rangeEnd     | string       | The maximum UTC timestamp in the deletion range.                                                                           |
| environments | list[string] | The environment to delete replays from. If not specified, applies to all environments                                      |
| status       | string       | The status of the deletion job. One of `pending`, `in-progress`, `completed` or `failed`.                                  |
| query        | string       | The query string which matches the to-be-deleted replays. Conforms to https://docs.sentry.io/concepts/search/#query-syntax |
| countDeleted | number       | The count of replays deleted by the job.                                                                                   |

- Response 200

  ```json
  {
    "data": [
      {
        "id": 23,
        "dateCreated": "2025-06-06T14:05:57.909921",
        "dateUpdated": "2025-06-06T14:05:57.909921",
        "rangeStart": "2025-06-01T00:00:00.000000",
        "rangeEnd": "2025-06-04T00:00:00.000000",
        "environments": ["production"],
        "status": "in-progress",
        "query": "release:2.3.0 AND url:*/billing*",
        "countDeleted": 104
      }
    ]
  }
  ```

### Create a Replay Batch Deletion Job [POST]

Delete a collection of replays. Deletes are throttled and will take some time to complete. The number of events expected to be deleted is returned on the meta object. This number is ephemeral and can change. It is only returned for informational reasons.

- Request

  ```json
  {
    "data": {
      "rangeStart": "2025-06-01T00:00:00.000000",
      "rangeEnd": "2025-06-04T00:00:00.000000",
      "environments": ["production"],
      "query": "release:2.3.0 AND url:*/billing*"
    }
  }
  ```

- Response 201

  ```json
  {
    "data": {
      "id": 23,
      "dateCreated": "2025-06-06T14:05:57.909921",
      "dateUpdated": "2025-06-06T14:05:57.909921",
      "rangeStart": "2025-06-01T00:00:00.000000",
      "rangeEnd": "2025-06-04T00:00:00.000000",
      "environments": ["production"],
      "status": "pending",
      "query": "release:2.3.0 AND url:*/billing*",
      "countDeleted": 0
    }
  }
  ```

## Replay Delete Job [/projects/<organization_id_or_slug>/<project_id_or_slug>/replays/jobs/delete/<id>/]

### Get Replay Delete Job [GET]

Fetch a replay delete job instance.

- Response 200

  ```json
  {
    "data": {
      "id": 23,
      "dateCreated": "2025-06-06T14:05:57.909921",
      "dateUpdated": "2025-06-06T14:05:57.909921",
      "rangeStart": "2025-06-01T00:00:00.000000",
      "rangeEnd": "2025-06-04T00:00:00.000000",
      "environments": ["production"],
      "status": "pending",
      "query": "release:2.3.0 AND url:*/billing*",
      "countDeleted": 1452667
    }
  }
  ```
