import {OrganizationFixture} from 'sentry-fixture/organization';
import {OrganizationIntegrationsFixture} from 'sentry-fixture/organizationIntegrations';
import {PreventAIConfigFixture} from 'sentry-fixture/prevent';

import {render, screen, userEvent} from 'sentry-test/reactTestingLibrary';

import ManageReposPage from './manageRepos';

describe('PreventAIManageRepos', () => {
  const integratedOrgs = [
    OrganizationIntegrationsFixture({
      id: 'integration-1',
      organizationId: 'org-1',
      name: 'Org One',
      externalId: 'ext-1',
      domainName: 'github.com/org-one',
    }),
    OrganizationIntegrationsFixture({
      id: 'integration-2',
      organizationId: 'org-2',
      name: 'Org Two',
      externalId: 'ext-2',
      domainName: 'github.com/org-two',
    }),
  ];

  const organization = OrganizationFixture({
    preventAiConfigGithub: PreventAIConfigFixture(),
  });

  beforeEach(() => {
    MockApiClient.addMockResponse({
      url: `/organizations/${organization.slug}/repos/`,
      method: 'GET',
      body: [
        {
          id: 'repo-1',
          name: 'org-one/repo-one',
        },
        {
          id: 'repo-2',
          name: 'org-one/repo-two',
        },
        {
          id: 'repo-3',
          name: 'org-two/repo-three',
        },
      ],
    });
  });

  afterEach(() => {
    MockApiClient.clearMockResponses();
  });

  it('renders the Manage Repositories title and toolbar', async () => {
    render(<ManageReposPage integratedOrgs={integratedOrgs} />, {organization});
    expect(await screen.findByTestId('manage-repos-title')).toBeInTheDocument();
    expect(await screen.findByTestId('manage-repos-settings-button')).toBeInTheDocument();
  });

  it('opens the settings panel when the settings button is clicked', async () => {
    render(<ManageReposPage integratedOrgs={integratedOrgs} />, {organization});
    expect(screen.queryByTestId('manage-repos-panel')).not.toBeInTheDocument();
    const settingsButton = await screen.findByTestId('manage-repos-settings-button');
    await userEvent.click(settingsButton);
    expect(await screen.findByTestId('manage-repos-panel')).toBeInTheDocument();
  });

  it('renders the illustration image', async () => {
    render(<ManageReposPage integratedOrgs={integratedOrgs} />, {organization});
    const img = await screen.findByTestId('manage-repos-illustration-image');
    expect(img).toBeInTheDocument();
    expect(img.tagName).toBe('IMG');
  });

  it('starts with "All Repos" selected by default', async () => {
    render(<ManageReposPage integratedOrgs={integratedOrgs} />, {organization});
    const repoButton = await screen.findByRole('button', {
      name: /All Repos/i,
    });
    expect(repoButton).toBeInTheDocument();
  });
});
