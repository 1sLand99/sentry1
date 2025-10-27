import styled from '@emotion/styled';

import {FeatureBadge} from 'sentry/components/core/badge/featureBadge';
import {Button} from 'sentry/components/core/button';
import {Disclosure} from 'sentry/components/core/disclosure';
import {Flex} from 'sentry/components/core/layout';
import {useOrganizationSeerSetup} from 'sentry/components/events/autofix/useOrganizationSeerSetup';
import FeedbackCategories from 'sentry/components/feedback/summaryCategories/feedbackCategories';
import FeedbackSummary from 'sentry/components/feedback/summaryCategories/feedbackSummary';
import {IconThumb} from 'sentry/icons';
import {t} from 'sentry/locale';
import {useFeedbackForm} from 'sentry/utils/useFeedbackForm';
import useOrganization from 'sentry/utils/useOrganization';
import {useSyncedLocalStorageState} from 'sentry/utils/useSyncedLocalStorageState';

export default function FeedbackSummaryCategories() {
  const organization = useOrganization();

  const openForm = useFeedbackForm();

  const {areAiFeaturesAllowed} = useOrganizationSeerSetup();

  const [isExpanded, setIsExpanded] = useSyncedLocalStorageState(
    'user-feedback-ai-summary-categories-expanded',
    true
  );

  const showSummaryCategories =
    (organization.features.includes('user-feedback-ai-summaries') ||
      organization.features.includes('user-feedback-ai-categorization-features')) &&
    areAiFeaturesAllowed;

  if (!showSummaryCategories) {
    return null;
  }

  const feedbackButton = ({type}: {type: 'positive' | 'negative'}) => {
    return openForm ? (
      <Button
        aria-label={t('Give feedback on the AI-powered summary')}
        icon={<IconThumb direction={type === 'positive' ? 'up' : 'down'} />}
        title={type === 'positive' ? t('I like this') : t(`I don't like this`)}
        size="xs"
        onClick={() =>
          openForm({
            messagePlaceholder:
              type === 'positive'
                ? t('What did you like about the AI-powered summary?')
                : t('How can we make the summary work better for you?'),
            tags: {
              ['feedback.source']: 'feedback_ai_summary',
              ['feedback.owner']: 'replay',
              ['feedback.type']: type,
            },
          })
        }
      />
    ) : null;
  };

  return (
    <SummaryIconContainer>
      <Disclosure
        expanded={isExpanded}
        onExpandedChange={setIsExpanded}
        size="md"
        as="section"
      >
        <Disclosure.Title
          trailingItems={
            <Flex gap="xs">
              {feedbackButton({type: 'positive'})}
              {feedbackButton({type: 'negative'})}
            </Flex>
          }
        >
          <Flex gap="xs" align="center">
            {t('Summary')} <FeatureBadge type="beta" />
          </Flex>
        </Disclosure.Title>
        <Disclosure.Content>
          <SummaryContainer>
            {organization.features.includes('user-feedback-ai-summaries') && (
              <FeedbackSummary />
            )}
            {organization.features.includes(
              'user-feedback-ai-categorization-features'
            ) && <FeedbackCategories />}
          </SummaryContainer>
        </Disclosure.Content>
      </Disclosure>
    </SummaryIconContainer>
  );
}

const SummaryContainer = styled('div')`
  display: flex;
  flex-direction: column;
  gap: ${p => p.theme.space.md};
  width: 100%;
`;

const SummaryIconContainer = styled('div')`
  padding: ${p => p.theme.space.xl};
  border: 1px solid ${p => p.theme.border};
  border-radius: ${p => p.theme.borderRadius};
`;
