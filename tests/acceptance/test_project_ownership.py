from sentry.testutils.cases import AcceptanceTestCase
from sentry.testutils.silo import no_silo_test


@no_silo_test
class ProjectOwnershipTest(AcceptanceTestCase):
    def setUp(self):
        super().setUp()
        self.login_as(self.user)
        self.path = f"/settings/{self.organization.slug}/projects/{self.project.slug}/ownership/"

    def test_simple(self) -> None:
        self.browser.get(self.path)
        self.browser.wait_until_not(".loading")
        self.browser.wait_until_test_id("ownership-rules-table")

    def test_open_modal(self) -> None:
        self.browser.get(self.path)
        self.browser.wait_until_not(".loading")
        self.browser.wait_until_test_id("ownership-rules-table")
        self.browser.click('[aria-label="Edit Rules"]')
        self.browser.wait_until("[role='dialog']")
        self.browser.wait_until_not("div[class$='loadingIndicator']")
