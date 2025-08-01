import {css} from '@emotion/react';
import styled from '@emotion/styled';

import {Select} from 'sentry/components/core/select';
import type {FormFieldProps} from 'sentry/components/forms/formField';
import FormField from 'sentry/components/forms/formField';
import {t} from 'sentry/locale';
import {space} from 'sentry/styles/space';
import type {Organization} from 'sentry/types/organization';
import type {Project} from 'sentry/types/project';
import type {QueryFieldValue} from 'sentry/utils/discover/fields';
import {explodeFieldString, generateFieldAsString} from 'sentry/utils/discover/fields';
import EAPField from 'sentry/views/alerts/rules/metric/eapField';
import type {Dataset, EventTypes} from 'sentry/views/alerts/rules/metric/types';
import {isEapAlertType} from 'sentry/views/alerts/rules/utils';
import type {AlertType} from 'sentry/views/alerts/wizard/options';
import {
  AlertWizardAlertNames,
  AlertWizardRuleTemplates,
  DEPRECATED_TRANSACTION_ALERTS,
} from 'sentry/views/alerts/wizard/options';
import {hasLogAlerts} from 'sentry/views/alerts/wizard/utils';
import {QueryField} from 'sentry/views/discover/table/queryField';
import {FieldValueKind} from 'sentry/views/discover/table/types';
import {generateFieldOptions} from 'sentry/views/discover/utils';
import {
  deprecateTransactionAlerts,
  hasEAPAlerts,
} from 'sentry/views/insights/common/utils/hasEAPAlerts';

import {getFieldOptionConfig} from './metricField';

type MenuOption = {label: React.ReactNode; value: AlertType};
type GroupedMenuOption = {label: string; options: MenuOption[]};

type Props = Omit<FormFieldProps, 'children'> & {
  organization: Organization;
  project: Project;
  alertType?: AlertType;
  /**
   * Optionally set a width for each column of selector
   */
  columnWidth?: number;
  eventTypes?: EventTypes[];
  inFieldLabels?: boolean;
  isEditing?: boolean;
};

export default function WizardField({
  organization,
  columnWidth,
  inFieldLabels,
  alertType,
  eventTypes,
  ...fieldProps
}: Props) {
  const isDeprecatedTransactionAlertType =
    alertType &&
    deprecateTransactionAlerts(organization) &&
    DEPRECATED_TRANSACTION_ALERTS.includes(alertType) &&
    hasEAPAlerts(organization);

  const deprecatedTransactionAggregationOptions: MenuOption[] = [
    {
      label: AlertWizardAlertNames.throughput,
      value: 'throughput',
    },
    {
      label: AlertWizardAlertNames.trans_duration,
      value: 'trans_duration',
    },
    {
      label: AlertWizardAlertNames.apdex,
      value: 'apdex',
    },
    {
      label: AlertWizardAlertNames.failure_rate,
      value: 'failure_rate',
    },
    {
      label: AlertWizardAlertNames.lcp,
      value: 'lcp',
    },
    {
      label: AlertWizardAlertNames.fid,
      value: 'fid',
    },
    {
      label: AlertWizardAlertNames.cls,
      value: 'cls',
    },
  ];

  const traceItemAggregationOptions: MenuOption[] = [
    {
      label: AlertWizardAlertNames.trace_item_throughput,
      value: 'trace_item_throughput',
    },
    {
      label: AlertWizardAlertNames.trace_item_duration,
      value: 'trace_item_duration',
    },
    {
      label: AlertWizardAlertNames.trace_item_failure_rate,
      value: 'trace_item_failure_rate',
    },
    {
      label: AlertWizardAlertNames.trace_item_lcp,
      value: 'trace_item_lcp',
    },
  ];

  const menuOptions: GroupedMenuOption[] = [
    {
      label: t('ERRORS'),
      options: [
        {
          label: AlertWizardAlertNames.num_errors,
          value: 'num_errors',
        },
        {
          label: AlertWizardAlertNames.users_experiencing_errors,
          value: 'users_experiencing_errors',
        },
      ],
    },
    ...((organization.features.includes('crash-rate-alerts')
      ? [
          {
            label: t('SESSIONS'),
            options: [
              {
                label: AlertWizardAlertNames.crash_free_sessions,
                value: 'crash_free_sessions',
              },
              {
                label: AlertWizardAlertNames.crash_free_users,
                value: 'crash_free_users',
              },
            ],
          },
        ]
      : []) as GroupedMenuOption[]),
    {
      label: t('PERFORMANCE'),
      options: [
        ...(deprecateTransactionAlerts(organization)
          ? traceItemAggregationOptions
          : deprecatedTransactionAggregationOptions),

        ...(hasEAPAlerts(organization)
          ? [
              {
                label: AlertWizardAlertNames.eap_metrics,
                value: 'eap_metrics' as const,
              },
            ]
          : []),

        ...(fieldProps.isEditing && isDeprecatedTransactionAlertType
          ? [
              {
                label: AlertWizardAlertNames[alertType],
                value: alertType,
              },
            ]
          : []),
      ],
    },
    ...(hasLogAlerts(organization)
      ? [
          {
            label: t('LOGS'),
            options: [
              {
                label: AlertWizardAlertNames.trace_item_logs,
                value: 'trace_item_logs' as const,
              },
            ],
          },
        ]
      : []),
    {
      label: t('CUSTOM'),
      options: [
        {
          label: AlertWizardAlertNames.custom_transactions,
          value: 'custom_transactions',
        },
      ],
    },
  ];

  return (
    <FormField {...fieldProps}>
      {({onChange, model, disabled, isEditing, disabledReason}: any) => {
        const aggregate = model.getValue('aggregate');
        const dataset: Dataset = model.getValue('dataset');
        const selectedTemplate: AlertType = alertType || 'eap_metrics';

        const {fieldOptionsConfig, hidePrimarySelector, hideParameterSelector} =
          getFieldOptionConfig({
            dataset,
            alertType,
          });
        const fieldOptions = generateFieldOptions({
          organization,
          ...fieldOptionsConfig,
        });
        const fieldValue = getFieldValue(aggregate ?? '', model);

        const fieldKey =
          fieldValue?.kind === FieldValueKind.FUNCTION
            ? `function:${fieldValue.function[0]}`
            : '';

        const selectedField = fieldOptions[fieldKey]?.value;
        const numParameters: number =
          selectedField?.kind === FieldValueKind.FUNCTION
            ? selectedField.meta.parameters.length
            : 0;

        const gridColumns =
          1 +
          numParameters -
          (hideParameterSelector ? 1 : 0) -
          (hidePrimarySelector ? 1 : 0);

        return (
          <Container alertType={alertType} hideGap={gridColumns < 1}>
            <Select
              value={selectedTemplate}
              options={menuOptions}
              disabled={disabled || (isEditing && isDeprecatedTransactionAlertType)}
              disabledReason={disabledReason}
              onChange={(option: MenuOption) => {
                // @ts-expect-error TS(7053): Element implicitly has an 'any' type because expre... Remove this comment to see the full error message
                const template = AlertWizardRuleTemplates[option.value];

                model.setValue('aggregate', template.aggregate);
                model.setValue('dataset', template.dataset);
                model.setValue('eventTypes', [template.eventTypes]);
                // Keep alertType last
                model.setValue('alertType', option.value);
              }}
            />
            {isEapAlertType(alertType) ? (
              <EAPField
                aggregate={aggregate}
                eventTypes={eventTypes ?? []}
                onChange={newAggregate => {
                  return onChange(newAggregate, {});
                }}
              />
            ) : (
              <StyledQueryField
                filterPrimaryOptions={option =>
                  option.value.kind === FieldValueKind.FUNCTION
                }
                fieldOptions={fieldOptions}
                fieldValue={fieldValue}
                onChange={v => onChange(generateFieldAsString(v), {})}
                columnWidth={columnWidth}
                gridColumns={gridColumns}
                inFieldLabels={inFieldLabels}
                shouldRenderTag={false}
                disabled={disabled || (isEditing && isDeprecatedTransactionAlertType)}
                hideParameterSelector={hideParameterSelector}
                hidePrimarySelector={hidePrimarySelector}
              />
            )}
          </Container>
        );
      }}
    </FormField>
  );
}

// swaps out custom percentile values for known percentiles, used while we fade out custom percentiles in metric alerts
// TODO(telemetry-experience): remove once we migrate all custom percentile alerts
const getFieldValue = (aggregate: string | undefined, model: any) => {
  const fieldValue = explodeFieldString(aggregate ?? '');

  if (fieldValue?.kind !== FieldValueKind.FUNCTION) {
    return fieldValue;
  }

  if (fieldValue.function[0] !== 'percentile') {
    return fieldValue;
  }

  const newFieldValue: QueryFieldValue = {
    kind: FieldValueKind.FUNCTION,
    function: [
      getApproximateKnownPercentile(fieldValue.function[2] as string),
      fieldValue.function[1],
      undefined,
      undefined,
    ],
    alias: fieldValue.alias,
  };

  model.setValue('aggregate', generateFieldAsString(newFieldValue));

  return newFieldValue;
};

const getApproximateKnownPercentile = (customPercentile: string) => {
  const percentile = parseFloat(customPercentile);

  if (percentile <= 0.5) {
    return 'p50';
  }
  if (percentile <= 0.75) {
    return 'p75';
  }
  if (percentile <= 0.9) {
    return 'p90';
  }
  if (percentile <= 0.95) {
    return 'p95';
  }
  if (percentile <= 0.99) {
    return 'p99';
  }
  return 'p100';
};

const Container = styled('div')<{hideGap: boolean; alertType?: AlertType}>`
  display: grid;
  gap: ${p => (p.hideGap ? 0 : space(1))};
  grid-template-columns: 1fr auto;
`;

const StyledQueryField = styled(QueryField)<{gridColumns: number; columnWidth?: number}>`
  ${p =>
    p.columnWidth &&
    css`
      width: ${p.gridColumns * p.columnWidth}px;
    `}
`;
