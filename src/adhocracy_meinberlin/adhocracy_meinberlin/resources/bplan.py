"""BPlan process resources."""
from adhocracy_core.resources import add_resource_type_to_registry
from adhocracy_core.resources import process
from adhocracy_core.resources import proposal
import adhocracy_meinberlin.sheets.bplan


class IProposalVersion(proposal.IProposalVersion):
    """BPlan proposal version."""


proposal_version_meta = proposal.proposal_version_meta._replace(
    content_name='ProposalVersion',
    iresource=IProposalVersion,
    extended_sheets=(adhocracy_meinberlin.sheets.bplan.IProposal,
                     ),
)


class IProposal(proposal.IProposal):
    """BPlan proposal versions pool."""


proposal_meta = proposal.proposal_meta._replace(
    iresource=IProposal,
    element_types=(IProposalVersion,),
    item_type=IProposalVersion,
    workflow_name = 'bplan_private',
)


class IProcess(process.IProcess):
    """BPlan participation process."""


process_meta = process.process_meta._replace(
    iresource=IProcess,
    element_types=(IProposal,
                   ),
    is_implicit_addable=True,
    workflow_name = 'bplan',
    extended_sheets=(adhocracy_meinberlin.sheets.bplan.IProcessSettings,
                     ),
)


def includeme(config):
    """Add resource type to content."""
    add_resource_type_to_registry(proposal_meta, config)
    add_resource_type_to_registry(proposal_version_meta, config)
    add_resource_type_to_registry(process_meta, config)
