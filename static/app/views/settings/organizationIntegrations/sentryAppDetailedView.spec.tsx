import {OrganizationFixture} from 'sentry-fixture/organization';
import {RouterFixture} from 'sentry-fixture/routerFixture';

import {
  render,
  renderGlobalModal,
  screen,
  userEvent,
  waitFor,
} from 'sentry-test/reactTestingLibrary';

import {testableWindowLocation} from 'sentry/utils/testableWindowLocation';
import SentryAppDetailedView from 'sentry/views/settings/organizationIntegrations/sentryAppDetailedView';

const mockNavigate = jest.fn();
jest.mock('sentry/utils/useNavigate', () => ({
  useNavigate: () => mockNavigate,
}));

describe('SentryAppDetailedView', function () {
  const organization = OrganizationFixture({features: ['events']});

  afterEach(() => {
    MockApiClient.clearMockResponses();
    jest.clearAllMocks();
  });

  async function renderSentryAppDetailedView({
    integrationSlug,
  }: {
    integrationSlug: string;
  }) {
    render(<SentryAppDetailedView />, {
      router: {...RouterFixture(), params: {integrationSlug}},
      organization,
      deprecatedRouterMocks: true,
    });
    renderGlobalModal();
    expect(await screen.findByTestId('loading-indicator')).not.toBeInTheDocument();
  }

  describe('Published Sentry App', function () {
    let createRequest: jest.Mock;
    let deleteRequest: jest.Mock;
    let sentryAppInteractionRequest: jest.Mock;

    beforeEach(() => {
      sentryAppInteractionRequest = MockApiClient.addMockResponse({
        url: `/sentry-apps/clickup/interaction/`,
        method: 'POST',
        statusCode: 200,
        body: {},
      });

      MockApiClient.addMockResponse({
        url: '/sentry-apps/clickup/',
        body: {
          status: 'published',
          scopes: [],
          isAlertable: false,
          clientSecret:
            '193583e573d14d61832de96a9efc32ceb64e59a494284f58b50328a656420a55',
          overview: null,
          verifyInstall: false,
          owner: {id: 1, slug: 'sentry'},
          slug: 'clickup',
          name: 'ClickUp',
          uuid: '5d547ecb-7eb8-4ed2-853b-40256177d526',
          author: 'Nisanthan',
          webhookUrl: 'http://localhost:7000',
          clientId: 'c215db1accc040919e0b0dce058e0ecf4ea062bb82174d70aee8eba62351be24',
          redirectUrl: null,
          allowedOrigins: [],
          events: [],
          schema: {},
        },
      });
      MockApiClient.addMockResponse({
        url: '/sentry-apps/clickup/features/',
        body: [
          {
            featureGate: 'integrations-api',
            description:
              'ClickUp can **utilize the Sentry API** to pull data or update resources in Sentry (with permissions granted, of course).',
          },
        ],
      });
      MockApiClient.addMockResponse({
        url: `/organizations/${organization.slug}/sentry-app-installations/`,
        body: [],
      });

      createRequest = MockApiClient.addMockResponse({
        url: `/organizations/${organization.slug}/sentry-app-installations/`,
        body: {
          status: 'installed',
          organization: {slug: `${organization.slug}`},
          app: {uuid: '5d547ecb-7eb8-4ed2-853b-40256177d526', slug: 'clickup'},
          code: '1dc8b0a28b7f45959d01bbc99d9bd568',
          uuid: '687323fd-9fa4-4f8f-9bee-ca0089224b3e',
        },
        method: 'POST',
      });

      deleteRequest = MockApiClient.addMockResponse({
        url: '/sentry-app-installations/687323fd-9fa4-4f8f-9bee-ca0089224b3e/',
        body: {},
        method: 'DELETE',
      });
    });

    it('renders a published sentry app', async () => {
      await renderSentryAppDetailedView({integrationSlug: 'clickup'});

      expect(sentryAppInteractionRequest).toHaveBeenCalledWith(
        `/sentry-apps/clickup/interaction/`,
        expect.objectContaining({
          method: 'POST',
          data: {
            tsdbField: 'sentry_app_viewed',
          },
        })
      );

      // Shows the Integration name and install status
      expect(screen.getByText('ClickUp')).toBeInTheDocument();
      expect(screen.getByText('Not Installed')).toBeInTheDocument();

      // Shows the Accept & Install button
      expect(screen.getByRole('button', {name: 'Accept & Install'})).toBeEnabled();
    });

    it('installs and uninstalls', async function () {
      await renderSentryAppDetailedView({integrationSlug: 'clickup'});

      await userEvent.click(screen.getByRole('button', {name: 'Accept & Install'}));
      expect(createRequest).toHaveBeenCalledTimes(1);

      expect(await screen.findByRole('button', {name: 'Uninstall'})).toBeInTheDocument();
      await userEvent.click(screen.getByRole('button', {name: 'Uninstall'}));
      await userEvent.click(screen.getByRole('button', {name: 'Confirm'}));
      expect(deleteRequest).toHaveBeenCalledTimes(1);
    });
  });

  describe('Internal Sentry App', function () {
    beforeEach(() => {
      MockApiClient.addMockResponse({
        url: `/sentry-apps/my-headband-washer-289499/interaction/`,
        method: 'POST',
        statusCode: 200,
        body: {},
      });
      MockApiClient.addMockResponse({
        url: '/sentry-apps/my-headband-washer-289499/',
        body: {
          status: 'internal',
          scopes: [
            'project:read',
            'team:read',
            'team:write',
            'project:releases',
            'event:read',
            'org:read',
            'member:read',
            'member:write',
          ],
          isAlertable: false,
          clientSecret:
            '8f47dcef40f7486f9bacfeca257022e092a483add7cf4d619993b9ace9775a79',
          overview: null,
          verifyInstall: false,
          owner: {id: 1, slug: 'sentry'},
          slug: 'my-headband-washer-289499',
          name: 'My Headband Washer',
          uuid: 'a806ab10-9608-4a4f-8dd9-ca6d6c09f9f5',
          author: 'Sentry',
          webhookUrl: 'https://myheadbandwasher.com',
          clientId: 'a6d35972d4164ef18845b1e2ca954fe70ac196e0b20d4d1e8760a38772cf6f1c',
          redirectUrl: null,
          allowedOrigins: [],
          events: [],
          schema: {},
        },
      });
      MockApiClient.addMockResponse({
        url: '/sentry-apps/my-headband-washer-289499/features/',
        body: [
          {
            featureGate: 'integrations-api',
            description:
              'My Headband Washer can **utilize the Sentry API** to pull data or update resources in Sentry (with permissions granted, of course).',
          },
        ],
      });
      MockApiClient.addMockResponse({
        url: `/organizations/${organization.slug}/sentry-app-installations/`,
        body: [],
      });
    });

    it('should get redirected to Developer Settings', async () => {
      await renderSentryAppDetailedView({integrationSlug: 'my-headband-washer-289499'});

      expect(mockNavigate).toHaveBeenLastCalledWith(
        `/settings/${organization.slug}/developer-settings/my-headband-washer-289499/`
      );
    });
  });

  describe('Unpublished Sentry App without Redirect Url', function () {
    let createRequest: jest.Mock;

    beforeEach(() => {
      MockApiClient.addMockResponse({
        url: `/sentry-apps/la-croix-monitor/interaction/`,
        method: 'POST',
        statusCode: 200,
        body: {},
      });
      MockApiClient.addMockResponse({
        url: '/sentry-apps/la-croix-monitor/',
        body: {
          status: 'unpublished',
          scopes: [
            'project:read',
            'project:write',
            'team:read',
            'project:releases',
            'event:read',
            'org:read',
          ],
          isAlertable: false,
          clientSecret:
            '2b2aeb743c3745ab832e03bf02a7d91851908d379646499f900cd115780e8b2b',
          overview: null,
          verifyInstall: false,
          owner: {id: 1, slug: 'sentry'},
          slug: 'la-croix-monitor',
          name: 'La Croix Monitor',
          uuid: 'a59c8fcc-2f27-49f8-af9e-02661fc3e8d7',
          author: 'La Croix',
          webhookUrl: 'https://lacroix.com',
          clientId: '8cc36458a0f94c93816e06dce7d808f882cbef59af6040d2b9ec4d67092c80f1',
          redirectUrl: null,
          allowedOrigins: [],
          events: [],
          schema: {},
        },
      });
      MockApiClient.addMockResponse({
        url: '/sentry-apps/la-croix-monitor/features/',
        body: [
          {
            featureGate: 'integrations-api',
            description:
              'La Croix Monitor can **utilize the Sentry API** to pull data or update resources in Sentry (with permissions granted, of course).',
          },
        ],
      });
      MockApiClient.addMockResponse({
        url: `/organizations/${organization.slug}/sentry-app-installations/`,
        body: [],
      });

      createRequest = MockApiClient.addMockResponse({
        url: `/organizations/${organization.slug}/sentry-app-installations/`,
        method: 'POST',
        body: {
          status: 'installed',
          organization: {slug: 'sentry'},
          app: {uuid: 'a59c8fcc-2f27-49f8-af9e-02661fc3e8d7', slug: 'la-croix-monitor'},
          code: '21c87231918a4e5c85d9b9e799c07382',
          uuid: '258ad77c-7e6c-4cfe-8a40-6171cff30d61',
        },
      });
    });
    it('shows the Integration name and install status', async function () {
      await renderSentryAppDetailedView({integrationSlug: 'la-croix-monitor'});
      expect(screen.getByText('La Croix Monitor')).toBeInTheDocument();
      expect(screen.getByText('Not Installed')).toBeInTheDocument();
    });

    it('installs and uninstalls', async function () {
      await renderSentryAppDetailedView({integrationSlug: 'la-croix-monitor'});
      await userEvent.click(screen.getByRole('button', {name: 'Accept & Install'}));
      expect(createRequest).toHaveBeenCalledTimes(1);
    });
  });

  describe('Unpublished Sentry App with Redirect Url', function () {
    let createRequest: jest.Mock;
    beforeEach(() => {
      MockApiClient.addMockResponse({
        url: `/sentry-apps/go-to-google/interaction/`,
        method: 'POST',
        statusCode: 200,
        body: {},
      });
      MockApiClient.addMockResponse({
        url: '/sentry-apps/go-to-google/',
        body: {
          status: 'unpublished',
          scopes: ['project:read', 'team:read'],
          isAlertable: false,
          clientSecret:
            '6405a4a7b8084cdf8dbea53b53e2163983deb428b78e4c6997bc408d44d93878',
          overview: null,
          verifyInstall: false,
          owner: {id: 1, slug: 'sentry'},
          slug: 'go-to-google',
          name: 'Go to Google',
          uuid: 'a4b8f364-4300-41ac-b8af-d8791ad50e77',
          author: 'Nisanthan Nanthakumar',
          webhookUrl: 'https://www.google.com',
          clientId: '0974b5df6b57480b99c2e1f238eef769ef2c27ec156d4791a26903a896d5807e',
          redirectUrl: 'https://www.google.com',
          allowedOrigins: [],
          events: [],
          schema: {},
        },
      });
      MockApiClient.addMockResponse({
        url: '/sentry-apps/go-to-google/features/',
        body: [
          {
            featureGate: 'integrations-api',
            description:
              'Go to Google can **utilize the Sentry API** to pull data or update resources in Sentry (with permissions granted, of course).',
          },
        ],
      });
      MockApiClient.addMockResponse({
        url: `/organizations/${organization.slug}/sentry-app-installations/`,
        body: [],
      });

      createRequest = MockApiClient.addMockResponse({
        url: `/organizations/${organization.slug}/sentry-app-installations/`,
        body: {
          status: 'installed',
          organization: {slug: 'sentry'},
          app: {uuid: 'a4b8f364-4300-41ac-b8af-d8791ad50e77', slug: 'go-to-google'},
          code: '1f0e7c1b99b940abac7a19b86e69bbe1',
          uuid: '4d803538-fd42-4278-b410-492f5ab677b5',
        },
        method: 'POST',
      });
    });
    it('shows the Integration name and install status', async function () {
      await renderSentryAppDetailedView({integrationSlug: 'go-to-google'});
      expect(screen.getByText('Go to Google')).toBeInTheDocument();
      expect(screen.getByText('Not Installed')).toBeInTheDocument();

      // Shows the Accept & Install button
      expect(screen.getByRole('button', {name: 'Accept & Install'})).toBeEnabled();
    });
    it('onClick: redirects url', async function () {
      await renderSentryAppDetailedView({integrationSlug: 'go-to-google'});

      await userEvent.click(screen.getByRole('button', {name: 'Accept & Install'}));

      expect(createRequest).toHaveBeenCalled();
      await waitFor(() => {
        expect(testableWindowLocation.assign).toHaveBeenLastCalledWith(
          'https://www.google.com/?code=1f0e7c1b99b940abac7a19b86e69bbe1&installationId=4d803538-fd42-4278-b410-492f5ab677b5&orgSlug=org-slug'
        );
      });
    });
  });
});
