import type {FocusEvent, RefObject} from 'react';
import {useCallback, useMemo} from 'react';
import {useGridListItem as useGridListItemAria} from '@react-aria/gridlist';
import type {ListState} from '@react-stately/list';
import type {Node} from '@react-types/shared';

import {shiftFocusToChild} from 'sentry/components/tokenizedInput/token/utils';

interface UseGridListItemOptions<T> {
  focusable: boolean;
  item: Node<T>;
  ref: RefObject<HTMLDivElement | null>;
  state: ListState<T>;
}

export function useGridListItem<T>({
  focusable,
  item,
  ref,
  state,
}: UseGridListItemOptions<T>) {
  const {rowProps, gridCellProps} = useGridListItemAria({node: item}, state, ref);

  const onFocus = useCallback(
    (evt: FocusEvent<HTMLDivElement>) => {
      if (focusable) {
        shiftFocusToChild(evt.currentTarget, item, state);
      }
    },
    [focusable, item, state]
  );

  return useMemo(() => {
    return {
      rowProps: {
        ...rowProps,
        onFocus,
        // The default behavior will capture some keys such as
        // Enter, Space, Arrows, which we want to handle ourselves.
        onKeyDown: noop,
        onKeyDownCapture: noop,
        // Default behavior is for click events to select the item
        onClick: noop,
        onMouseDown: noop,
        onPointerDown: noop,
      },
      gridCellProps,
    };
  }, [rowProps, gridCellProps, onFocus]);
}

function noop() {}
