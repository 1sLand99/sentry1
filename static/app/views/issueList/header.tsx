import type {ReactNode} from 'react';
import styled from '@emotion/styled';

import DisableInDemoMode from 'sentry/components/acl/demoModeDisabled';
import GuideAnchor from 'sentry/components/assistant/guideAnchor';
import {Badge} from 'sentry/components/core/badge';
import {Button} from 'sentry/components/core/button';
import {ButtonBar} from 'sentry/components/core/button/buttonBar';
import {TabList, Tabs} from 'sentry/components/core/tabs';
import {Tooltip} from 'sentry/components/core/tooltip';
import * as Layout from 'sentry/components/layouts/thirds';
import {PageHeadingQuestionTooltip} from 'sentry/components/pageHeadingQuestionTooltip';
import QueryCount from 'sentry/components/queryCount';
import {SLOW_TOOLTIP_DELAY} from 'sentry/constants';
import {IconPause, IconPlay} from 'sentry/icons';
import {t} from 'sentry/locale';
import type {InjectedRouter} from 'sentry/types/legacyReactRouter';
import type {Organization} from 'sentry/types/organization';
import normalizeUrl from 'sentry/utils/url/normalizeUrl';
import IssueListSetAsDefault from 'sentry/views/issueList/issueListSetAsDefault';

import type {QueryCounts} from './utils';
import {
  CUSTOM_TAB_VALUE,
  FOR_REVIEW_QUERIES,
  getTabs,
  IssueSortOptions,
  Query,
  TAB_MAX_COUNT,
} from './utils';

type IssueListHeaderProps = {
  displayReprocessingTab: boolean;
  onRealtimeChange: (realtime: boolean) => void;
  organization: Organization;
  query: string;
  queryCounts: QueryCounts;
  realtimeActive: boolean;
  router: InjectedRouter;
  selectedProjectIds: number[];
  sort: string;
  queryCount?: number;
};

type IssueListHeaderTabProps = {
  name: string;
  count?: number;
  hasMore?: boolean;
  tooltipHoverable?: boolean;
  tooltipTitle?: ReactNode;
};

function IssueListHeaderTabContent({
  count = 0,
  hasMore = false,
  name,
  tooltipHoverable,
  tooltipTitle,
}: IssueListHeaderTabProps) {
  return (
    <Tooltip
      title={tooltipTitle}
      position="bottom"
      isHoverable={tooltipHoverable}
      delay={SLOW_TOOLTIP_DELAY}
    >
      {name}{' '}
      {count > 0 && (
        <Badge type="default">
          <QueryCount hideParens count={count} max={hasMore ? TAB_MAX_COUNT : 1000} />
        </Badge>
      )}
    </Tooltip>
  );
}

function IssueListHeader({
  organization,
  query,
  sort,
  queryCounts,
  realtimeActive,
  onRealtimeChange,
  router,
  displayReprocessingTab,
}: IssueListHeaderProps) {
  const tabs = getTabs();
  const visibleTabs = displayReprocessingTab
    ? tabs
    : tabs.filter(([tab]) => tab !== Query.REPROCESSING);
  const tabValues = new Set(visibleTabs.map(([val]) => val));
  // Remove cursor and page when switching tabs
  const {cursor: _cursor, page: _page, ...queryParms} = router?.location?.query ?? {};
  const sortParam =
    queryParms.sort === IssueSortOptions.INBOX ? undefined : queryParms.sort;

  const realtimeTitle = realtimeActive
    ? t('Pause real-time updates')
    : t('Enable real-time updates');

  return (
    <Layout.Header noActionWrap>
      <Layout.HeaderContent>
        <Layout.Title>
          {t('Issues')}
          <PageHeadingQuestionTooltip
            docsUrl="https://docs.sentry.io/product/issues/"
            title={t(
              'Detailed views of errors and performance problems in your application grouped by events with a similar set of characteristics.'
            )}
          />
        </Layout.Title>
      </Layout.HeaderContent>
      <Layout.HeaderActions>
        <ButtonBar>
          <IssueListSetAsDefault {...{sort, query, organization}} />
          <DisableInDemoMode>
            <Button
              size="sm"
              data-test-id="real-time"
              title={realtimeTitle}
              aria-label={realtimeTitle}
              icon={realtimeActive ? <IconPause /> : <IconPlay />}
              onClick={() => onRealtimeChange(!realtimeActive)}
            />
          </DisableInDemoMode>
        </ButtonBar>
      </Layout.HeaderActions>
      <StyledTabs value={tabValues.has(query) ? query : CUSTOM_TAB_VALUE}>
        <TabList hideBorder>
          {visibleTabs.map(
            ([tabQuery, {name: queryName, tooltipTitle, tooltipHoverable, hidden}]) => {
              const to = normalizeUrl({
                query: {
                  ...queryParms,
                  query: tabQuery,
                  sort: FOR_REVIEW_QUERIES.includes(tabQuery || '')
                    ? IssueSortOptions.INBOX
                    : sortParam,
                },
                pathname: `/organizations/${organization.slug}/issues/`,
              });

              return (
                <TabList.Item
                  key={tabQuery}
                  to={to}
                  textValue={queryName}
                  hidden={hidden}
                >
                  <GuideAnchor
                    disabled={tabQuery !== Query.ARCHIVED}
                    target="issue_stream_archive_tab"
                    position="bottom"
                  >
                    <IssueListHeaderTabContent
                      tooltipTitle={tooltipTitle}
                      tooltipHoverable={tooltipHoverable}
                      name={queryName}
                      // @ts-expect-error TS(7053): Element implicitly has an 'any' type because expre... Remove this comment to see the full error message
                      count={queryCounts[tabQuery]?.count}
                      // @ts-expect-error TS(7053): Element implicitly has an 'any' type because expre... Remove this comment to see the full error message
                      hasMore={queryCounts[tabQuery]?.hasMore}
                    />
                  </GuideAnchor>
                </TabList.Item>
              );
            }
          )}
        </TabList>
      </StyledTabs>
    </Layout.Header>
  );
}

export default IssueListHeader;

const StyledTabs = styled(Tabs)`
  grid-column: 1/-1;
`;
