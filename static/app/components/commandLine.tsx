import styled from '@emotion/styled';

import {space} from 'sentry/styles/space';

type Props = {
  /**
   * The text interface
   */
  children: string;
};

function CommandLine({children}: Props) {
  return <Wrapper>{children}</Wrapper>;
}

export default CommandLine;

const Wrapper = styled('code')`
  padding: ${space(0.5)} ${space(1)};
  color: ${p => p.theme.pink400};
  background: ${p => p.theme.pink100};
  border: 1px solid ${p => p.theme.pink200};
  font-family: ${p => p.theme.text.familyMono};
  font-size: ${p => p.theme.fontSize.md};
  white-space: nowrap;
`;
