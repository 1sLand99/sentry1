import {createContext, Fragment, useContext} from 'react';
import styled from '@emotion/styled';
import {uuid4} from '@sentry/core';

import {Button} from 'sentry/components/core/button';
import {AutomationBuilderInput} from 'sentry/components/workflowEngine/form/automationBuilderInput';
import {RowLine} from 'sentry/components/workflowEngine/form/automationBuilderRowLine';
import {AutomationBuilderSelect} from 'sentry/components/workflowEngine/form/automationBuilderSelect';
import {PurpleTextButton} from 'sentry/components/workflowEngine/ui/purpleTextButton';
import {IconAdd, IconDelete} from 'sentry/icons';
import {t, tct} from 'sentry/locale';
import {space} from 'sentry/styles/space';
import type {SelectValue} from 'sentry/types/core';
import {DataConditionType} from 'sentry/types/workflowEngine/dataConditions';
import {
  Attributes,
  MatchType,
} from 'sentry/views/automations/components/actionFilters/constants';
import {useAutomationBuilderErrorContext} from 'sentry/views/automations/components/automationBuilderErrorContext';
import {useDataConditionNodeContext} from 'sentry/views/automations/components/dataConditionNodes';

interface SubfilterProps {
  onUpdate: (comparison: Record<string, any>) => void;
  removeError: () => void;
  subfilter: Record<string, any>;
  subfilter_id: string;
}

const SubfilterContext = createContext<SubfilterProps | null>(null);

function useSubfilterContext(): SubfilterProps {
  const context = useContext(SubfilterContext);
  if (!context) {
    throw new Error('useSubfilterContext was called outside of Subfilter');
  }
  return context;
}

export function SubfiltersList() {
  const {condition, condition_id, onUpdate} = useDataConditionNodeContext();
  const {removeError} = useAutomationBuilderErrorContext();

  const subfilters = condition.comparison.filters || [];
  const subfilterCount = subfilters.length;

  function addSubfilter() {
    const newSubfilters = [
      ...subfilters,
      {
        id: uuid4(),
      },
    ];
    onUpdate({comparison: {...condition.comparison, filters: newSubfilters}});
  }

  function removeSubfilter(id: string) {
    const newSubfilters = subfilters.filter(
      (subfilter: Record<string, any>) => subfilter.id !== id
    );
    onUpdate({comparison: {...condition.comparison, filters: newSubfilters}});
  }

  function updateSubfilter(id: string, newSubfilter: Record<string, any>) {
    const newSubfilters = subfilters.map((subfilter: Record<string, any>) => {
      if (subfilter.id === id) {
        return newSubfilter;
      }
      return subfilter;
    });
    onUpdate({comparison: {...condition.comparison, filters: newSubfilters}});
  }

  return (
    <div>
      <div>
        {subfilters.map((subfilter: Record<string, any>, i: number) => {
          return (
            <SubfilterContext.Provider
              value={{
                subfilter,
                subfilter_id: `${condition_id}.comparison.filters.${subfilter.id}`,
                onUpdate: newSubfilter => updateSubfilter(subfilter.id, newSubfilter),
                removeError: () => removeError(subfilter.id),
              }}
              key={subfilter.id}
            >
              <SubfilterRow
                onRemove={() => removeSubfilter(subfilter.id)}
                isFirstRow={i === 0}
                isLastRow={i === subfilterCount - 1}
              />
            </SubfilterContext.Provider>
          );
        })}
      </div>
      <PurpleTextButton borderless icon={<IconAdd />} size="xs" onClick={addSubfilter}>
        {t('Sub-filter')}
      </PurpleTextButton>
    </div>
  );
}

interface SubfilterRowProps {
  isFirstRow: boolean;
  isLastRow: boolean;
  onRemove: () => void;
}

function SubfilterRow({onRemove, isFirstRow, isLastRow}: SubfilterRowProps) {
  return (
    <RowWrapper>
      <Branch lastChild={isLastRow} />
      <StyledRowLine>
        {!isFirstRow && t('and')}
        <ComparisonTypeField />
        <Button
          aria-label={t('Delete Subfilter')}
          size="sm"
          icon={<IconDelete />}
          borderless
          onClick={onRemove}
        />
      </StyledRowLine>
    </RowWrapper>
  );
}

interface BranchProps {
  lastChild?: boolean;
}

function Branch({lastChild}: BranchProps) {
  return (
    <svg
      width="26"
      height="38"
      viewBox="0 0 26 38"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
    >
      <line x1="0.5" x2="0.5" y2={lastChild ? '19' : '38'} stroke="#80708F" />
      <circle cx="23.5" cy="18.5" r="2.5" fill="#80708F" />
      <line x1="22" y1="18.5" x2="1" y2="18.5" stroke="#80708F" />
    </svg>
  );
}

function ComparisonTypeField() {
  const {subfilter, subfilter_id, onUpdate} = useSubfilterContext();

  if (!subfilter.type) {
    return (
      <AutomationBuilderSelect
        name={`${subfilter_id}.type`}
        aria-label={t('Comparison type')}
        value={subfilter.type}
        placeholder={t('Select value type')}
        options={[
          {
            label: t('Attribute'),
            value: DataConditionType.EVENT_ATTRIBUTE,
          },
          {
            label: t('Tag'),
            value: DataConditionType.TAGGED_EVENT,
          },
        ]}
        onChange={(option: SelectValue<DataConditionType>) => {
          onUpdate({
            id: subfilter.id,
            type: option.value,
            match: MatchType.EQUAL,
            value: '',
            ...(option.value === DataConditionType.EVENT_ATTRIBUTE
              ? {attribute: Attributes.MESSAGE}
              : {}),
          });
        }}
      />
    );
  }

  return (
    <Fragment>
      {subfilter.type === DataConditionType.EVENT_ATTRIBUTE ? (
        <AttributeField />
      ) : (
        <KeyField />
      )}
      <MatchField />
      <ValueField />
    </Fragment>
  );
}

function AttributeField() {
  const {subfilter, subfilter_id, onUpdate} = useSubfilterContext();
  return (
    <AutomationBuilderSelect
      name={`${subfilter_id}.attribute`}
      aria-label={t('Attribute')}
      placeholder={t('Select attribute')}
      value={subfilter.attribute}
      options={Object.values(Attributes).map(attribute => ({
        value: attribute,
        label: attribute,
      }))}
      onChange={(option: SelectValue<string>) => {
        onUpdate({...subfilter, attribute: option.value});
      }}
    />
  );
}

function KeyField() {
  const {subfilter, subfilter_id, onUpdate, removeError} = useSubfilterContext();
  return (
    <AutomationBuilderInput
      name={`${subfilter_id}.key`}
      aria-label={t('Tag')}
      placeholder={t('tag')}
      value={subfilter.key}
      onChange={(e: React.ChangeEvent<HTMLInputElement>) => {
        onUpdate({...subfilter, key: e.target.value});
        removeError();
      }}
    />
  );
}

function MatchField() {
  const {subfilter, subfilter_id, onUpdate} = useSubfilterContext();
  return (
    <AutomationBuilderSelect
      name={`${subfilter_id}.match`}
      aria-label={t('Match type')}
      value={subfilter.match}
      options={[
        {
          label: 'is',
          value: MatchType.EQUAL,
        },
        {
          label: 'is not',
          value: MatchType.NOT_EQUAL,
        },
      ]}
      onChange={(option: SelectValue<MatchType>) => {
        onUpdate({...subfilter, match: option.value});
      }}
    />
  );
}

function ValueField() {
  const {subfilter, subfilter_id, onUpdate, removeError} = useSubfilterContext();
  return (
    <AutomationBuilderInput
      name={`${subfilter_id}.value`}
      aria-label={t('Value')}
      placeholder={t('value')}
      value={`${subfilter.value}`}
      onChange={(e: React.ChangeEvent<HTMLInputElement>) => {
        onUpdate({...subfilter, value: e.target.value});
        removeError();
      }}
    />
  );
}

export function SubfilterDetailsList({
  subfilters,
}: {
  subfilters: Array<Record<string, any>>;
}) {
  return (
    <DetailsListWrapper>
      {subfilters.map((subfilter, index) => (
        <div key={index}>
          <SubfilterDetails subfilter={subfilter} />
        </div>
      ))}
    </DetailsListWrapper>
  );
}

function SubfilterDetails({subfilter}: {subfilter: Record<string, any>}) {
  return tct('[item] [match] [value]', {
    item: subfilter.attribute ?? subfilter.key,
    match: subfilter.match === MatchType.EQUAL ? t('is') : t('is not'),
    value: subfilter.value,
  });
}

export function validateSubfilters(
  subfilters: Array<Record<string, any>>
): string | undefined {
  for (const subfilter of subfilters) {
    const isMissingAttributeOrTag = !subfilter.attribute && !subfilter.key;
    if (isMissingAttributeOrTag || !subfilter.match || !subfilter.value) {
      return t('Ensure all subfilters are filled in.');
    }
  }
  return undefined;
}

const RowWrapper = styled('div')`
  display: flex;
  align-items: center;
  gap: ${space(1)};

  :first-child {
    margin-top: 3px;
  }
`;

const StyledRowLine = styled(RowLine)`
  padding: 3px 0;

  Button {
    opacity: 0;
  }

  :hover {
    Button {
      opacity: 1;
    }
  }
`;

const DetailsListWrapper = styled('div')`
  display: flex;
  flex-direction: column;
  gap: ${space(1)};
  padding: ${space(1)} 0 0 ${space(2)};
`;
