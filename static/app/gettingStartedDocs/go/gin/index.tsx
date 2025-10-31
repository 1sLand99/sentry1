import type {Docs} from 'sentry/components/onboarding/gettingStartedDoc/types';
import {onboarding} from 'sentry/gettingStartedDocs/go/gin/onboarding';
import {crashReport} from 'sentry/gettingStartedDocs/go/go/crashReport';
import {logs} from 'sentry/gettingStartedDocs/go/go/logs';
import {
  feedbackOnboardingJsLoader,
  replayOnboardingJsLoader,
} from 'sentry/gettingStartedDocs/javascript/jsLoader/jsLoader';

const docs: Docs = {
  onboarding,
  replayOnboardingJsLoader,
  crashReportOnboarding: crashReport({
    docsLink:
      'https://docs.sentry.io/platforms/go/guides/gin/user-feedback/configuration/#crash-report-modal',
  }),
  feedbackOnboardingJsLoader,
  logsOnboarding: logs({
    docsPlatform: 'gin',
  }),
};

export default docs;
