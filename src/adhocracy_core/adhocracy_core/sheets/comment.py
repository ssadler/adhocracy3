"""Comment sheet."""
import colander

from adhocracy_core.interfaces import ISheet
from adhocracy_core.interfaces import ISheetReferenceAutoUpdateMarker
from adhocracy_core.interfaces import SheetToSheet
from adhocracy_core.sheets import add_sheet_to_registry
from adhocracy_core.schema import UniqueReferences
from adhocracy_core.schema import Reference
from adhocracy_core.sheets import sheet_meta
from adhocracy_core.schema import Text
from adhocracy_core.schema import PostPool


class IComment(ISheet, ISheetReferenceAutoUpdateMarker):
    """Marker interface for the comment sheet."""


class ICommentable(ISheet, ISheetReferenceAutoUpdateMarker):
    """Marker interface for resources that can be commented upon."""


class CommentRefersToReference(SheetToSheet):
    """Reference from comment version to the commented-on item version."""

    source_isheet = IComment
    source_isheet_field = 'refers_to'
    target_isheet = ICommentable


class CommentSchema(colander.MappingSchema):
    """Comment sheet data structure.

    `content`:  Text
    """

    refers_to = Reference(reftype=CommentRefersToReference)
    content = Text()
    # TODO add post_pool validator


comment_meta = sheet_meta._replace(isheet=IComment,
                                   schema_class=CommentSchema)


class CommentableSchema(colander.MappingSchema):
    """Commentable sheet data structure.

    `comments`: list of comments (not stored)
    `post_pool`: Pool to post new :class:`adhocracy_sample.resource.IComment`.
    """

    comments = UniqueReferences(readonly=True,
                                backref=True,
                                reftype=CommentRefersToReference)
    post_pool = PostPool(iresource_or_service_name='comments')


commentable_meta = sheet_meta._replace(
    isheet=ICommentable,
    schema_class=CommentableSchema,
    editable=False,
    creatable=False,
)


def includeme(config):
    """Register sheets."""
    add_sheet_to_registry(comment_meta, config.registry)
    add_sheet_to_registry(commentable_meta, config.registry)
