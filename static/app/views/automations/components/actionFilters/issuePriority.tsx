import {AutomationBuilderSelect} from 'sentry/components/workflowEngine/form/automationBuilderSelect';
import {t, tct} from 'sentry/locale';
import type {SelectValue} from 'sentry/types/core';
import type {DataCondition} from 'sentry/types/workflowEngine/dataConditions';
import {
  type Priority,
  PRIORITY_CHOICES,
} from 'sentry/views/automations/components/actionFilters/constants';
import {useAutomationBuilderErrorContext} from 'sentry/views/automations/components/automationBuilderErrorContext';
import type {ValidateDataConditionProps} from 'sentry/views/automations/components/automationFormData';
import {useDataConditionNodeContext} from 'sentry/views/automations/components/dataConditionNodes';

export function IssuePriorityDetails({condition}: {condition: DataCondition}) {
  return tct('Current issue priority is greater than or equal to [priority]', {
    priority:
      PRIORITY_CHOICES.find(choice => choice.value === condition.comparison)?.label ||
      condition.comparison,
  });
}

export function IssuePriorityNode() {
  const {condition, condition_id, onUpdate} = useDataConditionNodeContext();
  const {removeError} = useAutomationBuilderErrorContext();

  return tct('Current issue priority is greater than or equal to [priority]', {
    priority: (
      <AutomationBuilderSelect
        name={`${condition_id}.comparison`}
        aria-label={t('Priority')}
        value={condition.comparison}
        options={PRIORITY_CHOICES}
        onChange={(option: SelectValue<Priority>) => {
          onUpdate({comparison: option.value});
          removeError(condition.id);
        }}
      />
    ),
  });
}

export function validateIssuePriorityCondition({
  condition,
}: ValidateDataConditionProps): string | undefined {
  if (!condition.comparison) {
    return t('You must select a priority level.');
  }
  return undefined;
}
