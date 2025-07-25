import {Fragment, useLayoutEffect, useRef, useState} from 'react';
import {css} from '@emotion/react';
import styled from '@emotion/styled';
import {useFocusWithin} from '@react-aria/interactions';
import {mergeProps} from '@react-aria/utils';
import type {ListState} from '@react-stately/list';
import type {Node} from '@react-types/shared';

import InteractionStateLayer from 'sentry/components/core/interactionStateLayer';
import {DateTime} from 'sentry/components/dateTime';
import {useSearchQueryBuilder} from 'sentry/components/searchQueryBuilder/context';
import {useQueryBuilderGridItem} from 'sentry/components/searchQueryBuilder/hooks/useQueryBuilderGridItem';
import {AggregateKey} from 'sentry/components/searchQueryBuilder/tokens/filter/aggregateKey';
import {FilterKey} from 'sentry/components/searchQueryBuilder/tokens/filter/filterKey';
import {FilterOperator} from 'sentry/components/searchQueryBuilder/tokens/filter/filterOperator';
import {UnstyledButton} from 'sentry/components/searchQueryBuilder/tokens/filter/unstyledButton';
import {useFilterButtonProps} from 'sentry/components/searchQueryBuilder/tokens/filter/useFilterButtonProps';
import {
  formatFilterValue,
  isAggregateFilterToken,
} from 'sentry/components/searchQueryBuilder/tokens/filter/utils';
import {SearchQueryBuilderValueCombobox} from 'sentry/components/searchQueryBuilder/tokens/filter/valueCombobox';
import {InvalidTokenTooltip} from 'sentry/components/searchQueryBuilder/tokens/invalidTokenTooltip';
import {
  FilterType,
  type ParseResultToken,
  Token,
  type TokenResult,
} from 'sentry/components/searchSyntax/parser';
import {getKeyName} from 'sentry/components/searchSyntax/utils';
import {IconClose} from 'sentry/icons';
import {t} from 'sentry/locale';
import {space} from 'sentry/styles/space';
import {defined} from 'sentry/utils';
import {prettifyTagKey} from 'sentry/utils/fields';
import useOrganization from 'sentry/utils/useOrganization';

interface SearchQueryTokenProps {
  item: Node<ParseResultToken>;
  state: ListState<ParseResultToken>;
  token: TokenResult<Token.FILTER>;
}

interface FilterValueProps extends SearchQueryTokenProps {
  filterRef: React.RefObject<HTMLDivElement | null>;
  onActiveChange: (active: boolean) => void;
}

export function FilterValueText({token}: {token: TokenResult<Token.FILTER>}) {
  const {size} = useSearchQueryBuilder();
  const hasWildcardOperators = useOrganization().features.includes(
    'search-query-builder-wildcard-operators'
  );

  if (token.filter === FilterType.HAS) {
    return (
      <FilterValueSingleTruncatedValue>
        {prettifyTagKey(token.value.text)}
      </FilterValueSingleTruncatedValue>
    );
  }

  switch (token.value.type) {
    case Token.VALUE_TEXT_LIST:
    case Token.VALUE_NUMBER_LIST: {
      const items = token.value.items;

      if (items.length === 1 && items[0]!.value) {
        const allContains =
          items[0]!.value.type === Token.VALUE_TEXT && !!items[0]!.value.wildcard;

        return (
          <FilterValueSingleTruncatedValue>
            {formatFilterValue({
              token: items[0]!.value,
              stripWildcards: allContains && hasWildcardOperators,
            })}
          </FilterValueSingleTruncatedValue>
        );
      }

      const maxItems = size === 'small' ? 1 : 3;
      const allContains = items.every(
        item => item?.value?.type === Token.VALUE_TEXT && item.value.wildcard
      );

      return (
        <FilterValueList>
          {items.slice(0, maxItems).map((item, index) => (
            <Fragment key={index}>
              <FilterMultiValueTruncated>
                {formatFilterValue({
                  token: item.value!,
                  stripWildcards: allContains && hasWildcardOperators,
                })}
              </FilterMultiValueTruncated>
              {index !== items.length - 1 && index < maxItems - 1 ? (
                <FilterValueOr> or </FilterValueOr>
              ) : null}
            </Fragment>
          ))}
          {items.length > maxItems && <span>+{items.length - maxItems}</span>}
        </FilterValueList>
      );
    }
    case Token.VALUE_ISO_8601_DATE: {
      const isUtc = token.value.tz?.toLowerCase() === 'z' || !token.value.tz;

      return (
        <DateTime date={token.value.value} dateOnly={!token.value.time} utc={isUtc} />
      );
    }
    default: {
      const allContains = token.value.type === Token.VALUE_TEXT && !!token.value.wildcard;

      return (
        <FilterValueSingleTruncatedValue>
          {formatFilterValue({
            token: token.value,
            stripWildcards: allContains && hasWildcardOperators,
          })}
        </FilterValueSingleTruncatedValue>
      );
    }
  }
}

function FilterValue({token, state, item, filterRef, onActiveChange}: FilterValueProps) {
  const ref = useRef<HTMLDivElement>(null);
  const {dispatch, focusOverride, disabled} = useSearchQueryBuilder();

  const [isEditing, setIsEditing] = useState(false);

  useLayoutEffect(() => {
    if (
      !isEditing &&
      focusOverride?.itemKey === item.key &&
      focusOverride.part === 'value'
    ) {
      setIsEditing(true);
      onActiveChange(true);
      dispatch({type: 'RESET_FOCUS_OVERRIDE'});
    }
  }, [dispatch, focusOverride, isEditing, item.key, onActiveChange]);

  const {focusWithinProps} = useFocusWithin({
    onBlurWithin: () => {
      setIsEditing(false);
    },
  });

  const filterButtonProps = useFilterButtonProps({state, item});

  if (isEditing) {
    return (
      <ValueEditing ref={ref} {...mergeProps(focusWithinProps, filterButtonProps)}>
        <SearchQueryBuilderValueCombobox
          token={token}
          wrapperRef={ref}
          onDelete={() => {
            filterRef.current?.focus();
            state.selectionManager.setFocusedKey(item.key);
            setIsEditing(false);
            onActiveChange(false);
          }}
          onCommit={() => {
            setIsEditing(false);
            onActiveChange(false);
            dispatch({type: 'COMMIT_QUERY'});
            if (state.collection.getKeyAfter(item.key)) {
              state.selectionManager.setFocusedKey(
                state.collection.getKeyAfter(item.key)
              );
            }
          }}
        />
      </ValueEditing>
    );
  }

  return (
    <ValueButton
      aria-label={t('Edit value for filter: %s', getKeyName(token.key))}
      onClick={() => {
        setIsEditing(true);
        onActiveChange(true);
      }}
      disabled={disabled}
      {...filterButtonProps}
    >
      <InteractionStateLayer />
      <FilterValueText token={token} />
    </ValueButton>
  );
}

function FilterDelete({token, state, item}: SearchQueryTokenProps) {
  const {dispatch, disabled} = useSearchQueryBuilder();
  const filterButtonProps = useFilterButtonProps({state, item});

  return (
    <DeleteButton
      aria-label={t('Remove filter: %s', getKeyName(token.key))}
      onClick={() => {
        dispatch({type: 'DELETE_TOKEN', token});
      }}
      disabled={disabled}
      {...filterButtonProps}
    >
      <InteractionStateLayer />
      <IconClose legacySize="8px" />
    </DeleteButton>
  );
}

export function SearchQueryBuilderFilter({item, state, token}: SearchQueryTokenProps) {
  const ref = useRef<HTMLDivElement>(null);
  const [filterMenuOpen, setFilterMenuOpen] = useState(false);

  const isFocused = item.key === state.selectionManager.focusedKey;

  const {dispatch} = useSearchQueryBuilder();
  const {rowProps, gridCellProps} = useQueryBuilderGridItem(item, state, ref);

  const onKeyDown = (e: React.KeyboardEvent<HTMLDivElement>) => {
    if (e.key === 'Backspace' || e.key === 'Delete') {
      e.preventDefault();
      e.stopPropagation();

      // Only delete if full filter token is focused, otherwise focus it
      if (ref.current === document.activeElement) {
        dispatch({type: 'DELETE_TOKEN', token});
      } else {
        ref.current?.focus();
      }
    }
  };

  const modifiedRowProps = mergeProps(rowProps, {
    tabIndex: isFocused ? 0 : -1,
    onKeyDown,
  });

  const tokenHasError = 'invalid' in token && defined(token.invalid);
  const tokenHasWarning = 'warning' in token && defined(token.warning);

  return (
    <FilterWrapper
      aria-label={token.text}
      aria-invalid={tokenHasError}
      state={tokenHasWarning ? 'warning' : tokenHasError ? 'invalid' : 'valid'}
      ref={ref}
      {...modifiedRowProps}
    >
      <GridInvalidTokenTooltip
        token={token}
        state={state}
        item={item}
        containerDisplayMode="grid"
        forceVisible={filterMenuOpen ? false : undefined}
      >
        {token.filter === FilterType.IS || token.filter === FilterType.HAS ? null : (
          <BaseGridCell {...gridCellProps}>
            {isAggregateFilterToken(token) ? (
              <AggregateKey
                filterRef={ref}
                item={item}
                token={token}
                state={state}
                onActiveChange={setFilterMenuOpen}
              />
            ) : (
              <FilterKey
                token={token}
                state={state}
                item={item}
                onActiveChange={setFilterMenuOpen}
              />
            )}
          </BaseGridCell>
        )}
        <BaseGridCell {...gridCellProps}>
          <FilterOperator
            token={token}
            state={state}
            item={item}
            onOpenChange={setFilterMenuOpen}
          />
        </BaseGridCell>
        <FilterValueGridCell {...gridCellProps}>
          <FilterValue
            token={token}
            state={state}
            item={item}
            filterRef={ref}
            onActiveChange={setFilterMenuOpen}
          />
        </FilterValueGridCell>
        <BaseGridCell {...gridCellProps}>
          <FilterDelete token={token} state={state} item={item} />
        </BaseGridCell>
      </GridInvalidTokenTooltip>
    </FilterWrapper>
  );
}

const FilterWrapper = styled('div')<{state: 'invalid' | 'warning' | 'valid'}>`
  position: relative;
  border: 1px solid ${p => p.theme.innerBorder};
  border-radius: ${p => p.theme.borderRadius};
  height: 24px;
  /* Ensures that filters do not grow outside of the container */
  min-width: 0;

  :focus {
    background-color: ${p => p.theme.gray100};
    outline: none;
  }

  ${p =>
    p.state === 'invalid'
      ? css`
          border-color: ${p.theme.red200};
          background-color: ${p.theme.red100};
        `
      : p.state === 'warning'
        ? css`
            border-color: ${p.theme.gray300};
            background-color: ${p.theme.gray100};
          `
        : ''}

  &[aria-selected='true'] {
    background-color: ${p => p.theme.gray100};
  }
`;

const GridInvalidTokenTooltip = styled(InvalidTokenTooltip)`
  display: grid;
  grid-template-columns: auto auto auto auto;
  align-items: stretch;
  height: 22px;
`;

const BaseGridCell = styled('div')`
  display: flex;
  align-items: stretch;
  position: relative;
`;

const FilterValueGridCell = styled(BaseGridCell)`
  /* When we run out of space, shrink the value */
  min-width: 0;
`;

const ValueButton = styled(UnstyledButton)`
  padding: 0 ${space(0.25)};
  color: ${p => p.theme.purple400};
  border-left: 1px solid transparent;
  border-right: 1px solid transparent;
  width: 100%;
  max-width: 400px;

  :focus {
    background-color: ${p => p.theme.purple100};
    border-left: 1px solid ${p => p.theme.innerBorder};
    border-right: 1px solid ${p => p.theme.innerBorder};
  }
`;

const ValueEditing = styled('div')`
  padding: 0 ${space(0.25)};
  color: ${p => p.theme.purple400};
  border-left: 1px solid transparent;
  border-right: 1px solid transparent;
  max-width: 100%;

  :focus-within {
    background-color: ${p => p.theme.purple100};
    border-left: 1px solid ${p => p.theme.innerBorder};
    border-right: 1px solid ${p => p.theme.innerBorder};
  }
`;

const DeleteButton = styled(UnstyledButton)`
  padding: 0 ${space(0.75)} 0 ${space(0.5)};
  border-radius: 0 3px 3px 0;
  color: ${p => p.theme.subText};
  border-left: 1px solid transparent;

  :focus {
    background-color: ${p => p.theme.translucentGray100};
    border-left: 1px solid ${p => p.theme.innerBorder};
  }
`;

const FilterValueList = styled('div')`
  display: flex;
  align-items: center;
  flex-wrap: nowrap;
  gap: ${space(0.5)};
  max-width: 400px;
`;

const FilterValueOr = styled('span')`
  color: ${p => p.theme.subText};
`;

const FilterMultiValueTruncated = styled('div')`
  ${p => p.theme.overflowEllipsis};
  max-width: 110px;
  width: min-content;
`;

const FilterValueSingleTruncatedValue = styled('div')`
  ${p => p.theme.overflowEllipsis};
  max-width: 100%;
  width: min-content;
`;
