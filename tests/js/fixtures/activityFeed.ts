import {EventFixture} from 'sentry-fixture/event';
import {ProjectFixture} from 'sentry-fixture/project';
import {UserFixture} from 'sentry-fixture/user';

import {EventOrGroupType} from 'sentry/types/event';
import type {Activity} from 'sentry/types/group';
import {GroupActivityType, IssueCategory, IssueType} from 'sentry/types/group';

export function ActivityFeedFixture(params: Partial<Activity> = {}): Activity {
  return {
    data: {text: 'Very interesting comment'},
    dateCreated: '2019-04-29T21:43:32.280Z',
    user: UserFixture({
      username: 'billy@sentry.io',
      lastLogin: '2019-04-23T00:10:19.787Z',
      isSuperuser: true,
      emails: [{is_verified: false, id: '1', email: 'billy@sentry.io'}],
      isManaged: false,
      lastActive: '2019-04-30T01:39:05.659Z',
      identities: [],
      id: '1',
      isActive: true,
      has2fa: false,
      name: 'billy@sentry.io',
      avatarUrl:
        'https://secure.gravatar.com/avatar/7b544e8eb9d08ed777be5aa82121155a?s=32&d=mm',
      dateJoined: '2019-03-09T06:52:42.836Z',
      options: {
        theme: 'system',
        avatarType: 'letter_avatar',
        clock24Hours: false,
        defaultIssueEvent: 'recommended',
        language: 'en',
        stacktraceOrder: -1,
        timezone: 'America/Los_Angeles',
        prefersIssueDetailsStreamlinedUI: false,
        prefersNextjsInsightsOverview: false,
        prefersAgentsInsightsModule: false,
        prefersStackedNavigation: false,
        prefersChonkUI: false,
      },
      flags: {newsletter_consent_prompt: false},
      avatar: {avatarUuid: null, avatarType: 'letter_avatar'},
      hasPasswordAuth: true,
      email: 'billy@sentry.io',
    }),
    type: GroupActivityType.NOTE,
    issue: {
      platform: 'javascript',
      lastSeen: '2019-04-26T16:34:12.288Z',
      numComments: 3,
      userCount: 1,
      culprit: '/organizations/:orgId/issues/:groupId/feedback/',
      title: 'Error: user efedback',
      id: '524',
      assignedTo: {
        id: '1',
        name: 'actor',
        type: 'user',
      },
      issueCategory: IssueCategory.ERROR,
      issueType: IssueType.ERROR,
      participants: [],
      latestEvent: EventFixture(),
      isUnhandled: true,
      pluginActions: [],
      pluginContexts: [],
      seenBy: [],
      filtered: null,
      pluginIssues: [],
      // there is a nasty type issue here where "reprocessing" cannot be assigned to
      // resolution status | "reprocessing" and "reprocessing" cannot be assigned to resolution
      // status (fails even if I as const it).
      // @ts-expect-error - cannot be assigned to resolution
      status: 'reprocessing' as const,
      activity: [],
      logger: 'critical',
      type: EventOrGroupType.ERROR,
      annotations: [],
      metadata: {type: 'Error', value: 'user feedback', filename: '<anonymous>'},
      subscriptionDetails: {reason: 'commented'},
      isPublic: false,
      hasSeen: true,
      shortId: 'INTERNAL-DW',
      shareId: '99',
      firstSeen: '2019-04-26T16:34:12.288Z',
      count: '1',
      permalink: 'http://localhost:8000/organizations/sentry/issues/524/?project=1',
      level: 'error',
      isSubscribed: true,
      isBookmarked: false,
      project: ProjectFixture({
        platform: undefined,
        slug: 'internal',
        id: '1',
        name: 'Internal',
      }),
    },
    id: '48',
    ...params,
  };
}
