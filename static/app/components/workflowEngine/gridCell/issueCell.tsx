import {css} from '@emotion/react';
import styled from '@emotion/styled';

import {ProjectAvatar} from 'sentry/components/core/avatar/projectAvatar';
import {Flex} from 'sentry/components/core/layout';
import {Link} from 'sentry/components/core/link';
import ShortId, {Wrapper} from 'sentry/components/group/inboxBadges/shortId';
import TimeSince from 'sentry/components/timeSince';
import {EmptyCell} from 'sentry/components/workflowEngine/gridCell/emptyCell';
import {t} from 'sentry/locale';
import {space} from 'sentry/styles/space';
import type {Group} from 'sentry/types/group';

type IssueCellProps = {
  className?: string;
  disabled?: boolean;
  group?: Group;
};

export function IssueCell({group, disabled = false, className}: IssueCellProps) {
  if (!group) {
    return <EmptyCell />;
  }
  return (
    <IssueWrapper to={'/issues/' + group.id} disabled={disabled} className={className}>
      <ShortId
        shortId={group.shortId}
        avatar={<ProjectAvatar project={group.project} />}
      />
      <LastSeenWrapper gap="xs">
        {t('Last seen')}
        <TimeSince
          date={group.lastSeen}
          liveUpdateInterval={'second'}
          unitStyle="short"
          disabledAbsoluteTooltip
        />
      </LastSeenWrapper>
    </IssueWrapper>
  );
}

const IssueWrapper = styled(Link)<{disabled: boolean}>`
  display: flex;
  flex-direction: column;
  gap: ${space(0.5)};
  flex: 1;

  ${Wrapper} {
    color: ${p => (p.disabled ? p.theme.disabled : p.theme.textColor)};
    font-size: ${p => p.theme.fontSize.md};
  }

  ${p =>
    !p.disabled &&
    css`
      &:hover ${Wrapper} {
        color: ${p.theme.textColor};
        text-decoration: underline;
      }
    `}
`;

const LastSeenWrapper = styled(Flex)`
  color: ${p => p.theme.subText};
`;
