import type {DOMAttributes} from 'react';
import {css} from '@emotion/react';
import styled from '@emotion/styled';
import type {FocusableElement} from '@react-types/shared';

import {Container, Flex, type FlexProps} from '@sentry/scraps/layout';
import type {ContainerProps} from '@sentry/scraps/layout/container';

type BaseGridCellProps = FlexProps & DOMAttributes<FocusableElement>;

export function BaseGridCell({children, ...props}: BaseGridCellProps) {
  return (
    <Flex align="stretch" position="relative" {...props}>
      {children}
    </Flex>
  );
}

type FilterWrapperProps = ContainerProps & {
  state: 'invalid' | 'warning' | 'valid';
};

export function FilterWrapper({children, ...props}: FilterWrapperProps) {
  return (
    <StyledFilterWrapper
      border="muted"
      position="relative"
      radius="sm"
      height="24px"
      /* Ensures that filters do not grow outside of the container */
      minWidth="0"
      {...props}
    >
      {typeof children === 'function'
        ? children({className: props.className ?? ''})
        : children}
    </StyledFilterWrapper>
  );
}

const StyledFilterWrapper = styled(Container)<{state: 'invalid' | 'warning' | 'valid'}>`
  :focus,
  &[aria-selected='true'] {
    background-color: ${p => p.theme.gray100};
    border-color: ${p => (p.theme.isChonk ? p.theme.tokens.border.accent : undefined)};
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
`;
