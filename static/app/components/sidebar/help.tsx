import styled from '@emotion/styled';

import {openHelpSearchModal} from 'app/actionCreators/modal';
import DropdownMenu from 'app/components/dropdownMenu';
import Hook from 'app/components/hook';
import SidebarItem from 'app/components/sidebar/sidebarItem';
import {IconQuestion} from 'app/icons';
import {t} from 'app/locale';
import space from 'app/styles/space';
import {Organization} from 'app/types';

import SidebarDropdownMenu from './sidebarDropdownMenu.styled';
import SidebarMenuItem from './sidebarMenuItem';
import {CommonSidebarProps} from './types';

type Props = Pick<CommonSidebarProps, 'collapsed' | 'hidePanel' | 'orientation'> & {
  organization: Organization;
};

const SidebarHelp = ({orientation, collapsed, hidePanel, organization}: Props) => (
  <DropdownMenu>
    {({isOpen, getActorProps, getMenuProps}) => (
      <HelpRoot>
        <HelpActor {...getActorProps({onClick: hidePanel})}>
          <SidebarItem
            data-test-id="help-sidebar"
            orientation={orientation}
            collapsed={collapsed}
            hasPanel={false}
            icon={<IconQuestion size="md" />}
            label={t('Help')}
            id="help"
          />
        </HelpActor>

        {isOpen && (
          <HelpMenu {...getMenuProps({})} orientation={orientation}>
            <SidebarMenuItem
              data-test-id="search-docs-and-faqs"
              onClick={() => openHelpSearchModal({organization})}
            >
              {t('Search Support, Docs and More')}
            </SidebarMenuItem>
            <SidebarMenuItem href="https://help.sentry.io/">
              {t('Visit Help Center')}
            </SidebarMenuItem>
            <Hook name="sidebar:help-menu" organization={organization} />
          </HelpMenu>
        )}
      </HelpRoot>
    )}
  </DropdownMenu>
);

export default SidebarHelp;

const HelpRoot = styled('div')`
  position: relative;
`;

// This exists to provide a styled actor for the dropdown. Making the actor a regular,
// non-styled react component causes some issues with toggling correctly because of
// how refs are handled.
const HelpActor = styled('div')``;

const HelpMenu = styled('div', {shouldForwardProp: p => p !== 'orientation'})<{
  orientation: Props['orientation'];
}>`
  ${SidebarDropdownMenu};
  ${p => (p.orientation === 'left' ? 'bottom: 100%' : `top: ${space(4)}; right: 0px;`)}
`;
