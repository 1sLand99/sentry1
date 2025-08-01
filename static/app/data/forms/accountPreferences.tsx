import type {JsonFormObject} from 'sentry/components/forms/types';
import languages from 'sentry/data/languages';
import {timezoneOptions} from 'sentry/data/timezones';
import {t} from 'sentry/locale';
import {StacktraceOrder} from 'sentry/types/user';
import {removeBodyTheme} from 'sentry/utils/removeBodyTheme';

// Export route to make these forms searchable by label/help
export const route = '/settings/account/details/';

// Called before sending API request, these fields need to be sent as an
// `options` object
const transformOptions = (data: Record<PropertyKey, unknown>) => ({options: data});

const formGroups: JsonFormObject[] = [
  {
    // Form "section"/"panel"
    title: 'Preferences',
    fields: [
      {
        name: 'theme',
        type: 'select',
        label: t('Theme'),
        help: t(
          "Select your theme preference. It can be synced to your system's theme, always light mode, or always dark mode."
        ),
        options: [
          {value: 'light', label: t('Light')},
          {value: 'dark', label: t('Dark')},
          {value: 'system', label: t('Default to system')},
        ],
        getData: transformOptions,
        onChange: () => {
          removeBodyTheme();
        },
      },
      {
        name: 'language',
        type: 'select',
        label: t('Language'),
        options: languages.map(([value, label]) => ({value, label})),
        getData: transformOptions,
      },
      {
        name: 'timezone',
        type: 'select',
        label: t('Timezone'),
        options: timezoneOptions,
        getData: transformOptions,
      },
      {
        name: 'clock24Hours',
        type: 'boolean',
        label: t('Use a 24-hour clock'),
        getData: transformOptions,
      },
      {
        name: 'stacktraceOrder',
        type: 'select',
        required: false,
        options: [
          // TODO: If we eliminate the special-casing as discussed in
          // https://github.com/getsentry/sentry/pull/96719, consider changing the label here to
          // `Default (newest first)` and removing the separate `Newest first` option.
          {value: StacktraceOrder.DEFAULT, label: t('Default')},
          {value: StacktraceOrder.MOST_RECENT_LAST, label: t('Oldest first')},
          {value: StacktraceOrder.MOST_RECENT_FIRST, label: t('Newest first')},
        ],
        label: t('Stack Trace Order'),
        help: t('Choose the default ordering of frames in stack traces'),
        getData: transformOptions,
      },
      {
        name: 'defaultIssueEvent',
        type: 'select',
        required: false,
        options: [
          {value: 'recommended', label: t('Recommended')},
          {value: 'latest', label: t('Latest')},
          {value: 'oldest', label: t('Oldest')},
        ],
        label: t('Default Issue Event'),
        help: t('Choose what event gets displayed by default'),
        getData: transformOptions,
      },
    ],
  },
];

export default formGroups;
