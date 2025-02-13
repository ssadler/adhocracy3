"""Initialize meinberlin ACM."""
from pyramid.events import ApplicationCreated
from pyramid.traversal import find_interface
from pyramid.renderers import render

from adhocracy_core.interfaces import IResourceCreatedAndAdded
from adhocracy_core.interfaces import IResourceSheetModified
from adhocracy_core.authorization import set_acms_for_app_root
from adhocracy_core.resources.root import root_acm
from adhocracy_core.utils import get_sheet
from adhocracy_core.utils import has_annotation_sheet_data
from adhocracy_meinberlin.resources.root import meinberlin_acm
from adhocracy_meinberlin.resources.bplan import IProposalVersion
from adhocracy_meinberlin.resources.bplan import IProposal
from adhocracy_meinberlin import sheets
from adhocracy_meinberlin import resources


def send_bplan_submission_confirmation_email(event):
    """Notify office worker and creator about created bplan version."""
    if not hasattr(event.registry, 'messenger'):  # ease testing
        return
    messenger = event.registry.messenger
    proposal_version = event.object
    if not _is_proposal_creation_finished(proposal_version):
        return
    appstruct = _get_appstruct(proposal_version)
    process_settings = _get_process_settings(proposal_version)
    if process_settings['plan_number'] == 0 or \
            process_settings['office_worker'] is None:
        return
    templates_values = _get_templates_values(process_settings, appstruct)
    subject = 'Ihre Stellungnahme zum Bebauungsplan {plan_number}, ' \
              '{participation_kind} von {participation_start_date:%d/%m/%Y} ' \
              '- {participation_end_date:%d/%m/%Y}.' \
              .format(**process_settings)
    messenger.send_mail(subject,
                        [appstruct['email']],
                        'noreply@mein.berlin.de',
                        render('adhocracy_meinberlin:templates/'
                               'bplan_submission_confirmation.txt.mako',
                               templates_values))
    messenger.send_mail(subject,
                        [process_settings['office_worker'].email],
                        'noreply@mein.berlin.de',
                        render('adhocracy_meinberlin:templates/'
                               'bplan_submission_confirmation.txt.mako',
                               templates_values))


def _get_templates_values(process_settings, appstruct):
    templates_values = appstruct.copy()
    templates_values.update(process_settings)
    return templates_values


def _get_process_settings(proposal_version):
    process = find_interface(proposal_version, resources.bplan.IProcess)
    process_settings = get_sheet(process, sheets.bplan.IProcessSettings).get()
    return process_settings


def _get_appstruct(proposal_version):
    proposal_sheet = get_sheet(proposal_version, sheets.bplan.IProposal)
    appstruct = proposal_sheet.get()
    return appstruct


def _is_proposal_creation_finished(proposal_version):
    proposal_item = find_interface(proposal_version, IProposal)
    versions_with_data = [x for x in proposal_item.values()
                          if IProposalVersion.providedBy(x)
                          and has_annotation_sheet_data(x)]
    return len(versions_with_data) == 1


def set_root_acms(event):
    """Set :term:`acm`s for root if the Pyramid application starts."""
    set_acms_for_app_root(event.app, (meinberlin_acm, root_acm))


def includeme(config):
    """Register subscribers."""
    config.add_subscriber(set_root_acms, ApplicationCreated)
    config.add_subscriber(send_bplan_submission_confirmation_email,
                          IResourceCreatedAndAdded,
                          object_iface=IProposalVersion)
    config.add_subscriber(send_bplan_submission_confirmation_email,
                          IResourceSheetModified,
                          object_iface=IProposalVersion)
