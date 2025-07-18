import styled from '@emotion/styled';

import {Button} from 'sentry/components/core/button';
import {IconChevron} from 'sentry/icons';
import {t} from 'sentry/locale';
import {space} from 'sentry/styles/space';

interface AccordionItemContent {
  content: React.ReactNode;
  header: React.ReactNode;
}

interface Props {
  expandedIndex: number;
  items: AccordionItemContent[];
  setExpandedIndex: (index: number) => void;
  collapsible?: boolean;
}

export default function Accordion({
  expandedIndex,
  setExpandedIndex,
  items,
  collapsible = true,
}: Props) {
  return (
    <AccordionContainer>
      {items.map((item, index) => {
        const isExpanded = index === expandedIndex;

        return (
          <AccordionItem key={index}>
            <AccordionHeader>
              <Button
                icon={<IconChevron size="xs" direction={isExpanded ? 'up' : 'down'} />}
                aria-label={collapsible && isExpanded ? t('Collapse') : t('Expand')}
                aria-expanded={isExpanded}
                size="zero"
                borderless
                onClick={() => setExpandedIndex(collapsible && isExpanded ? -1 : index)}
              />
              <LineItemWrapper
                onClick={() => setExpandedIndex(isExpanded && collapsible ? -1 : index)}
              >
                {item.header}
              </LineItemWrapper>
            </AccordionHeader>
            <AccordionContent>{isExpanded && item.content}</AccordionContent>
          </AccordionItem>
        );
      })}
    </AccordionContainer>
  );
}

const AccordionItem = styled('li')`
  line-height: ${p => p.theme.text.lineHeightBody};
`;

const AccordionContainer = styled('ul')`
  padding: ${space(1)} 0 0 0;
  margin: 0;
  list-style-type: none;
`;

const AccordionHeader = styled('div')`
  display: flex;
  align-items: center;
  border-top: 1px solid ${p => p.theme.border};
  padding: ${space(1)} ${space(2)};
  font-size: ${p => p.theme.fontSize.md};
  column-gap: ${space(1.5)};
`;

const AccordionContent = styled('div')`
  padding: 0 ${space(0.25)};
`;

const LineItemWrapper = styled('div')`
  display: grid;
  grid-template-columns: 1fr max-content;
  flex: 1;
`;
