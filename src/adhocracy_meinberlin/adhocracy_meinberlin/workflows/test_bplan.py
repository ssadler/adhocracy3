from pyramid import testing
from pytest import fixture
from pytest import mark
from webtest import TestResponse

from adhocracy_core.utils.testing import add_resources
from adhocracy_core.utils.testing import do_transition_to


@fixture(scope='class')
def app_anonymous(app_anonymous):
    app_anonymous.base_path = '/organisation'
    return app_anonymous

@fixture(scope='class')
def app_anonymous(app_anonymous):
    app_anonymous.base_path = '/organisation'
    return app_anonymous


@fixture(scope='class')
def app_initiator(app_initiator):
    app_initiator.base_path = '/organisation'
    return app_initiator


@fixture(scope='class')
def app_admin(app_admin):
    app_admin.base_path = '/organisation'
    return app_admin


@fixture
def integration(config):
    config.include('adhocracy_core.events')
    config.include('adhocracy_core.content')
    config.include('adhocracy_meinberlin.workflows')

@mark.usefixtures('integration')
def test_includeme_add_bplan_private_workflow(registry):
    from adhocracy_core.workflows import AdhocracyACLWorkflow
    workflow = registry.content.workflows['bplan_private']
    assert isinstance(workflow, AdhocracyACLWorkflow)


@mark.usefixtures('integration')
def test_initiate_bplan_private_workflow(registry, context):
    from substanced.util import get_acl
    workflow = registry.content.workflows['bplan_private']
    assert workflow.state_of(context) is None
    workflow.initialize(context)
    assert workflow.state_of(context) is 'private'
    local_acl = get_acl(context)
    assert ('Deny', 'system.Anonymous', 'view') in local_acl


@mark.usefixtures('integration')
def test_includeme_add_bplan_workflow(registry):
    from adhocracy_core.workflows import AdhocracyACLWorkflow
    workflow = registry.content.workflows['bplan']
    assert isinstance(workflow, AdhocracyACLWorkflow)


def _post_proposal_item(app_user, path='') -> TestResponse:
    from adhocracy_meinberlin.resources.bplan import IProposal
    resp = app_user.post_resource(path, IProposal, {})
    return resp


def _post_proposal_itemversion(app_user, path='') -> TestResponse:
    from adhocracy_meinberlin.sheets.bplan import IProposal
    from adhocracy_meinberlin.resources.bplan import IProposalVersion
    appstructs = {IProposal.__identifier__: {'name': 'test',
                                             'street_number': '1',
                                             'postal_code_city': '1',
                                             'email': 'test@test.de',
                                             'statement': 'buh',
                                             }}
    resp = app_user.post_resource(path, IProposalVersion, appstructs)
    return resp


@mark.functional
class TestBPlanWorkflow:

    def test_create_resources(self,
                              registry,
                              datadir,
                              app,
                              app_admin):
        json_file = str(datadir.join('resources.json'))
        add_resources(app, json_file)
        resp = app_admin.get('/bplan')
        assert resp.status_code == 200

    def test_draft_admin_can_view_process(self, registry, app_admin):
        resp = app_admin.get('/bplan')
        assert resp.status_code == 200

    def test_draft_initiator_can_view_process(self, registry, app_initiator):
        resp = app_initiator.get(path='/bplan')
        assert resp.status_code == 200

    def test_draft_anonymous_cannot_view_process(self,
                                                 registry,
                                                 app_anonymous):
        resp = app_anonymous.get('/bplan')
        assert resp.status_code == 403

    def test_draft_anonymous_cannot_create_proposal(self,
                                                    registry,
                                                    app_anonymous):
        from adhocracy_meinberlin.resources.bplan import IProposal
        assert IProposal not in app_anonymous.get_postable_types('/bplan')

    def test_change_state_to_announce(self, registry, app_initiator):
        resp = do_transition_to(app_initiator, '/bplan', 'announce')
        assert resp.status_code == 200

    def test_announce_anonymous_can_view_process(self,
                                                 registry,
                                                 app_anonymous):
        resp = app_anonymous.get('/bplan')
        assert resp.status_code == 200

    def test_anonymous_cannot_create_proposal(self, registry, app_anonymous):
        from adhocracy_meinberlin.resources.bplan import IProposal
        assert IProposal not in app_anonymous.get_postable_types('/bplan')

    def test_change_state_to_participate(self, registry, app_initiator):
        resp = do_transition_to(app_initiator, '/bplan', 'participate')
        assert resp.status_code == 200

    def test_participate_anonymous_creates_proposal(self,
                                                    registry,
                                                    app_anonymous):
        resp = _post_proposal_item(app_anonymous, path='/bplan')
        assert resp.status_code == 200

    def test_participate_anonymous_edits_proposal_version0(self,
                                                           registry,
                                                           app_anonymous):
        resp = _post_proposal_itemversion(app_anonymous,
                                          path='/bplan/proposal_0000000')
        assert resp.status_code == 200

    def test_participate_anonymous_gets_notification(self, registry, mailer):
        msg = mailer.outbox[-2]
        assert msg.subject.startswith('Ihre Stellungnahme')
        assert msg.recipients == ['test@test.de']

    def test_participate_office_worker_gets_notification(self,
                                                         registry,
                                                         mailer):
        msg = mailer.outbox[-1]
        assert msg.subject.startswith('Ihre Stellungnahme')
        assert msg.recipients == ['sysadmin@test.de']

    def test_participate_anonymous_cannot_edit_proposal_version1(self,
                                                                 registry,
                                                                 app_anonymous):
        from adhocracy_meinberlin.resources.bplan import IProposalVersion
        assert IProposalVersion not in app_anonymous.get_postable_types(
            '/bplan/proposal_0000000')

    def test_participate_anonymous_cannot_view_proposal(self,
                                                        registry,
                                                        app_anonymous):
        resp = app_anonymous.get(path='/bplan/proposal_0000000')
        assert resp.status_code == 403

    def test_participate_initiator_can_view_proposal(self,
                                                     registry,
                                                     app_initiator):
        resp = app_initiator.get(path='/bplan/proposal_0000000')
        assert resp.status_code == 200

    def test_change_state_to_frozen(self, registry, app_initiator):
        resp = do_transition_to(app_initiator, '/bplan', 'evaluate')
        assert resp.status_code == 200

    def test_evaluate_anonymous_cannot_create_proposal(self,
                                                       registry,
                                                       app_anonymous):
        from adhocracy_meinberlin.resources.bplan import IProposal
        assert IProposal not in app_anonymous.get_postable_types('/bplan')

    def test_evaluate_initiator_can_view_proposal(self,
                                                  registry,
                                                  app_initiator):
        resp = app_initiator.get(path='/bplan/proposal_0000000')
        assert resp.status_code == 200

    def test_evaluate_anonymous_cannot_view_proposal(self,
                                                     registry,
                                                     app_anonymous):
        resp = app_anonymous.get('/bplan/proposal_0000000')
        assert resp.status_code == 403
