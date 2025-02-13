"""Public py.test fixtures: http://pytest.org/latest/fixture.html."""
from unittest.mock import Mock
from configparser import ConfigParser
from distutils import dir_util
from shutil import rmtree
from subprocess import CalledProcessError
import json
import os
import subprocess
import time

from pyramid.config import Configurator
from pyramid import testing
from pyramid.util import DottedNameResolver
from pytest import fixture
from ZODB import FileStorage
from testfixtures import LogCapture
from webtest import TestApp
from webtest import TestResponse
from zope.interface.interfaces import IInterface
import colander

from adhocracy_core.interfaces import SheetMetadata
from adhocracy_core.interfaces import ChangelogMetadata
from adhocracy_core.interfaces import ResourceMetadata
from adhocracy_core.interfaces import SearchResult
from adhocracy_core.interfaces import SearchQuery
from adhocracy_core.interfaces import IResourceCreatedAndAdded
from adhocracy_core.resources.root import IRootPool

#####################################
# Integration/Function test helper  #
#####################################

god_header = {'X-User-Path': '/principals/users/0000000',
              'X-User-Token': 'SECRET_GOD'}
"""The authentication headers for the `god` user, used by functional fixtures.
This assumes the initial user is created and has the `god` role.
"""
god_login = 'god'
"""The login name for the god user, default value."""
god_password = 'password'
"""The password for the god user, default value."""
god_email = 'sysadmin@test.de'
"""The email for the god user, default value."""

participant_header = {'X-User-Path': '/principals/users/0000001',
                      'X-User-Token': 'SECRET_PARTICIPANT'}
"""The authentication headers for the `participant`, used by funct. fixtures.
This assumes the user exists with path == 'X-User-Path'.
"""
participant_login = 'participant'
participant_password = 'password'

moderator_header = {'X-User-Path': '/principals/users/0000002',
                    'X-User-Token': 'SECRET_MODERATOR'}
moderator_login = 'moderator'
moderator_password = 'password'

initiator_header = {'X-User-Path': '/principals/users/0000003',
                    'X-User-Token': 'SECRET_INITIATOR'}
initiator_login = 'initiator'
initiator_password = 'password'

admin_header = {'X-User-Path': '/principals/users/0000004',
                'X-User-Token': 'SECRET_ADMIN'}
admin_login = 'admin'
admin_password = 'password'

participant2_header = {'X-User-Path': '/principals/users/0000005',
                       'X-User-Token': 'SECRET_PARTICIPANT2'}
participant2_login = 'participant2'
participant2_password = 'password'

broken_header = {'X-User-Path': '/principals/users/0000001',
                 'X-User-Token': ''}

batch_url = '/batch'


class DummyPool(testing.DummyResource):
    """Dummy Pool based on :class:`pyramid.testing.DummyResource`."""

    def add(self, name, resource, **kwargs):
        """Add resource to the pool."""
        self[name] = resource
        resource.__parent__ = self
        resource.__name__ = name

    def next_name(self, obj, prefix=''):
        """Get the next name for the resource when using autonaming."""
        return prefix + '_0000000'

    def add_service(self, name, resource, **kwargs):
        """Add a service to the pool."""
        from adhocracy_core.interfaces import IServicePool
        from zope.interface import alsoProvides
        alsoProvides(resource, IServicePool)
        resource.__is_service__ = True
        self.add(name, resource)

    def find_service(self, service_name, *sub_service_names):
        """Return a service from the pool."""
        from substanced.util import find_service
        return find_service(self, service_name, *sub_service_names)


def register_sheet(context, mock_sheet, registry, isheet=None) -> Mock:
    """Register `mock_sheet` for `context`. You can ony use this only once.

    If you need to register multiple mock_sheets in you test add side effects:
    `registry.content.get_sheet.side_effect = [sheet1, sheet2]`.
    You can also set single sheets directly:
    `registry.content.get_sheet.return_value = sheet1
    """
    from zope.interface import alsoProvides
    if isheet is not None:
        mock_sheet.meta = mock_sheet.meta._replace(isheet=isheet)
    if context is not None:
        alsoProvides(context, mock_sheet.meta.isheet)
    registry.content.get_sheet.return_value = mock_sheet
    return mock_sheet


def create_event_listener(config: Configurator, ievent: IInterface) -> list:
    """Register dummy event listener that adds events to the returned List."""
    events = []
    listener = lambda event: events.append(event)
    config.add_subscriber(listener, ievent)
    return events


##################
# Fixtures       #
##################


@fixture
def pool_graph(integration):
    """Return pool with graph for integration/functional tests."""
    from adhocracy_core.resources.pool import Pool
    from adhocracy_core.resources.root import _add_graph
    from adhocracy_core.resources.root import _add_objectmap_to_app_root
    from adhocracy_core.sheets.pool import IPool
    from zope.interface import directlyProvides
    pool = Pool()
    directlyProvides(pool, IPool)
    _add_objectmap_to_app_root(pool)
    _add_graph(pool, integration.registry)
    return pool


@fixture
def pool_with_catalogs(integration, pool_graph):
    """Return pool with graph and catalog for integration/functional tests."""
    from substanced.interfaces import MODE_IMMEDIATE
    from adhocracy_core.resources.root import _add_catalog_service
    context = pool_graph
    _add_catalog_service(context, integration.registry)
    context['catalogs']['system']['name'].action_mode = MODE_IMMEDIATE
    context['catalogs']['system']['interfaces'].action_mode = MODE_IMMEDIATE
    context['catalogs']['adhocracy']['tag'].action_mode = MODE_IMMEDIATE
    context['catalogs']['adhocracy']['rate'].action_mode = MODE_IMMEDIATE
    return context


@fixture
def integration(config) -> Configurator:
    """Include basic resource types and sheets."""
    config.include('adhocracy_core.events')
    config.include('adhocracy_core.content')
    config.include('adhocracy_core.graph')
    config.include('adhocracy_core.catalog')
    config.include('adhocracy_core.sheets')
    config.include('adhocracy_core.resources')
    config.include('adhocracy_core.workflows')
    return config


@fixture
def resource_meta() -> ResourceMetadata:
    """Return basic resource metadata."""
    from adhocracy_core.resources import resource_meta
    from adhocracy_core.interfaces import IResource
    return resource_meta._replace(iresource=IResource)


@fixture
def sheet_meta() -> SheetMetadata:
    """Return basic sheet metadata."""
    from adhocracy_core.sheets import sheet_meta
    from adhocracy_core.interfaces import ISheet
    return sheet_meta._replace(isheet=ISheet,
                               schema_class=colander.MappingSchema)


class DummyRequest(testing.DummyRequest):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.validated = {}
        self.errors = []
        self.content_type = 'application/json'
        self.text = ''

    def authenticated_userid(self):
        return None

    @property
    def json_body(self):
        return json.loads(self.body)


@fixture
def log(request) -> LogCapture:
    """Return object capturing all log messages."""
    log = LogCapture()

    def fin():
        log.uninstall()
    request.addfinalizer(fin)
    return log


@fixture
def request_():
    """Return dummy request with additional validation attributes.

    Additional Attributes:
        `errors`, `validated`
    """
    request = DummyRequest()
    request.registry.settings = {}
    return request


@fixture
def changelog_meta() -> ChangelogMetadata:
    """Return changelog metadata."""
    from adhocracy_core.changelog import changelog_meta
    return changelog_meta


@fixture
def context() -> testing.DummyResource:
    """Return dummy context with IResource interface."""
    from adhocracy_core.interfaces import IResource
    return testing.DummyResource(__provides__=IResource)


@fixture
def pool() -> DummyPool:
    """Return dummy pool with IPool interface."""
    from adhocracy_core.interfaces import IPool
    from substanced.interfaces import IFolder
    return DummyPool(__provides__=(IPool, IFolder))


@fixture
def service() -> DummyPool:
    """Return dummy pool with IServicePool interface."""
    from adhocracy_core.interfaces import IServicePool
    from substanced.interfaces import IFolder
    return DummyPool(__provides__=(IServicePool, IFolder),
                     __is_service__=True)


@fixture
def item() -> DummyPool:
    """Return dummy pool with IItem and IMetadata interface."""
    from adhocracy_core.interfaces import IItem
    from adhocracy_core.sheets.metadata import IMetadata
    return DummyPool(__provides__=(IItem, IMetadata))


@fixture
def node() -> colander.MappingSchema:
    """Return dummy node."""
    return colander.MappingSchema()


@fixture
def changelog(changelog_meta) -> dict:
    """Return transaction_changelog dictionary."""
    from collections import defaultdict
    metadata = lambda: changelog_meta
    return defaultdict(metadata)


@fixture
def registry_with_changelog(registry, changelog):
    """Return registry with transaction_changelog."""
    registry.changelog = changelog
    return registry


@fixture
def mock_sheet() -> Mock:
    """Mock :class:`adhocracy_core.sheets.GenericResourceSheet`."""
    from adhocracy_core.sheets import sheet_meta
    from adhocracy_core.interfaces import ISheet
    # Better would be spec=GenericResourceSheet for the mock object;
    # however this fails if the object is deepcopied.
    sheet = Mock()
    sheet.meta = sheet_meta._replace(isheet=ISheet,
                                     schema_class=colander.MappingSchema)
    sheet.schema = colander.MappingSchema()
    sheet.get.return_value = {}
    return sheet


@fixture
def mock_graph() -> Mock:
    """Mock :class:`adhocracy_core.graph.Graph`."""
    from adhocracy_core.graph import Graph
    mock = Mock(spec=Graph)
    return mock


@fixture
def mock_catalogs(search_result) -> Mock:
    """Mock :class:`adhocracy_core.catalogs.ICatalalogsService`."""
    from zope.interface import alsoProvides
    from adhocracy_core.interfaces import IServicePool
    from adhocracy_core.catalog import CatalogsServiceAdhocracy
    catalogs = testing.DummyResource()
    alsoProvides(catalogs, IServicePool)
    search_mock = Mock(spec=CatalogsServiceAdhocracy.search)
    search_mock.return_value = search_result
    catalogs.search = search_mock
    reindex_index_mock = Mock(spec=CatalogsServiceAdhocracy.reindex_index)
    catalogs.reindex_index = reindex_index_mock
    get_index_mock = Mock(spec=CatalogsServiceAdhocracy.get_index)
    catalogs.get_index = get_index_mock
    return catalogs


@fixture
def search_result() -> SearchResult:
    """Return search result."""
    from adhocracy_core.interfaces import search_result
    return search_result


@fixture
def query() -> SearchQuery:
    """Return search query."""
    from adhocracy_core.interfaces import search_query
    return search_query


@fixture
def sheet_catalogs(monkeypatch, mock_catalogs) -> Mock:
    """Mock _catalogs property for sheets."""
    from adhocracy_core import sheets
    monkeypatch.setattr(sheets, 'find_service', lambda x, y: mock_catalogs)
    return mock_catalogs


@fixture
def mock_objectmap() -> Mock:
    """Mock :class:`substanced.objectmap.ObjectMap`."""
    from substanced.objectmap import ObjectMap
    mock = Mock(spec=ObjectMap)
    mock.get_reftypes.return_value = []
    return mock


@fixture
def mock_workflow() -> Mock:
    """Mock :class:`adhocracy_core.workflows.AdhocracyACLWorkflow`."""
    from adhocracy_core.workflows import AdhocracyACLWorkflow
    mock = Mock(spec=AdhocracyACLWorkflow)
    mock._states = {}
    return mock


@fixture
def mock_content_registry() -> Mock:
    """Mock :class:`adhocracy_core.content.ResourceContentRegistry`."""
    from adhocracy_core.content import ResourceContentRegistry
    mock = Mock(spec=ResourceContentRegistry)
    mock.sheets_meta = {}
    mock.resources_meta = {}
    mock.workflows_meta = {}
    mock.workflows = {}
    mock.get_resources_meta_addable.return_value = []
    mock.resources_meta_addable = {}
    mock.get_sheets_read.return_value = []
    mock.get_sheets_edit.return_value = []
    mock.get_sheets_create.return_value = []
    mock.get_sheet.return_value = None
    mock.sheets_read = {}
    mock.sheets_edit = {}
    mock.sheets_create = {}
    mock.sheets_create_mandatory = {}
    return mock


@fixture
def registry_with_content(registry, mock_content_registry):
    """Return registry with content registry attribute."""
    registry.content = mock_content_registry
    return registry


@fixture
def config(request) -> Configurator:
    """Return dummy testing configuration."""
    config = testing.setUp()
    request.addfinalizer(testing.tearDown)
    return config


@fixture
def registry(config) -> object:
    """Return dummy registry."""
    return config.registry


@fixture
def mock_user_locator(registry) -> Mock:
    """Mock :class:`adhocracy_core.resource.principal.UserLocatorAdapter`."""
    from zope.interface import Interface
    from adhocracy_core.interfaces import IRolesUserLocator
    from adhocracy_core.resources.principal import UserLocatorAdapter
    locator = Mock(spec=UserLocatorAdapter)
    locator.get_groupids.return_value = None
    locator.get_roleids.return_value = None
    locator.get_user_by_userid.return_value = None
    locator.get_user_by_login.return_value = None
    locator.get_user_by_email.return_value = None
    locator.get_group_roleids.return_value = None
    locator.get_role_and_group_roleids.return_value = None
    registry.registerAdapter(lambda y, x: locator, (Interface, Interface),
                             IRolesUserLocator)
    return locator


@fixture
def mock_messenger():
    """Return mock messenger."""
    from adhocracy_core.messaging import Messenger
    messenger = Mock(spec=Messenger)
    return messenger


def _get_settings(request, part, config_path_key='pyramid_config'):
    """Return settings of a config part."""
    config_parser = ConfigParser()
    config_file = request.config.getoption(config_path_key) \
        or 'etc/test_with_ws.ini'
    config_parser.read(config_file)
    settings = {}
    for option, value in config_parser.items(part):
        settings[option] = value
    return settings


@fixture(scope='session')
def settings(request) -> dict:
    """Return app:main and server:main settings."""
    settings = {}
    app = _get_settings(request, 'app:main')
    settings.update(app)
    server = _get_settings(request, 'server:main')
    settings.update(server)
    return settings


@fixture(scope='session')
def app_settings(request) -> dict:
    """Return settings to start the test wsgi app."""
    settings = {}
    # disable creating a default group, this causes
    # ZODB.POSException.InvalidObjectReference
    settings['adhocracy.add_default_group'] = False
    # enable create test user for every :term:`role`
    settings['adhocracy.add_test_users'] = True
    # don't look for the websocket server
    settings['adhocracy.ws_url'] = ''
    # use in memory database without zeo
    settings['zodbconn.uri'] = 'memory://'
    # satisfy substanced
    settings['substanced.secret'] = 'secret'
    # extra dependenies
    settings['pyramid.includes'] = [
        # commit after request
        'pyramid_tm',
        # mock mail server
        'pyramid_mailer.testing',
    ]
    settings['mail.default_sender'] = 'substanced_demo@example.com'
    settings['adhocracy.abuse_handler_mail'] = \
        'abuse_handler@unconfigured.domain'
    return settings


@fixture(scope='session')
def ws_settings(request) -> Configurator:
    """Return websocket server settings."""
    return _get_settings(request, 'websockets')


@fixture(scope='session')
def supervisor(request) -> str:
    """Start supervisord daemon."""
    pid_file = 'var/supervisord.pid'
    if _is_running(pid_file):
        return True
    try:
        subprocess.check_output('bin/supervisord',
                                shell=True,
                                stderr=subprocess.STDOUT)
    # workaround if pid file is missing but supervisord is still running
    except CalledProcessError as err:
        print(err)


@fixture(scope='class')
def zeo(request, supervisor) -> str:
    """Start zeo server with supervisor."""
    output = subprocess.check_output(
        'bin/supervisorctl restart adhocracy_test:test_zeo',
        shell=True,
        stderr=subprocess.STDOUT)

    def fin():
        subprocess.check_output(
            'bin/supervisorctl stop adhocracy_test:test_zeo',
            shell=True,
            stderr=subprocess.STDOUT)
    request.addfinalizer(fin)

    return output


@fixture(scope='class')
def websocket(request, supervisor) -> bool:
    """Start websocket server with supervisor."""
    output = subprocess.check_output(
        'bin/supervisorctl restart adhocracy_test:test_autobahn',
        shell=True,
        stderr=subprocess.STDOUT)

    def fin():
        subprocess.check_output(
            'bin/supervisorctl stop adhocracy_test:test_autobahn',
            shell=True,
            stderr=subprocess.STDOUT)
    request.addfinalizer(fin)

    return output


def _kill_pid_in_file(path_to_pid_file):
    if os.path.isfile(path_to_pid_file):
        pid = open(path_to_pid_file).read().strip()
        pid_int = int(pid)
        os.kill(pid_int, 15)
        time.sleep(1)
        subprocess.call(['rm', path_to_pid_file])


def _is_running(path_to_pid_file) -> bool:
    if os.path.isfile(path_to_pid_file):
        pid = open(path_to_pid_file).read().strip()
        pid_int = int(pid)
        try:
            os.kill(pid_int, 0)
        except OSError:
            subprocess.call(['rm', path_to_pid_file])
        else:
            return True


def add_user_token(root, userid: str, token: str, registry):
    """Add user authentication token to :app:`Pyramid`."""
    from datetime import datetime
    from adhocracy_core.interfaces import ITokenManger
    timestamp = datetime.now()
    token_manager = registry.getAdapter(root, ITokenManger)
    token_manager.token_to_user_id_timestamp[token] = (userid, timestamp)


def add_user(root, login: str=None, password: str=None, email: str=None,
             roles=None, registry=None) -> str:
    """Add user to :app:`Pyramid`."""
    from substanced.util import find_service
    from adhocracy_core.resources.principal import IUser
    import adhocracy_core.sheets
    users = find_service(root, 'principals', 'users')
    roles = roles or []
    passwd_sheet = adhocracy_core.sheets.principal.IPasswordAuthentication
    appstructs =\
        {adhocracy_core.sheets.principal.IUserBasic.__identifier__:
         {'name': login},
         adhocracy_core.sheets.principal.IUserExtended.__identifier__:
         {'email': email},
         adhocracy_core.sheets.principal.IPermissions.__identifier__:
         {'roles': roles},
         passwd_sheet.__identifier__:
         {'password': password},
         }
    user = registry.content.create(IUser.__identifier__,
                                   parent=users,
                                   appstructs=appstructs,
                                   registry=registry,
                                   run_after_creation=False,
                                   )
    user.activate()
    return user


def add_test_users(root, registry):
    """Add test user and dummy authentication token for every role."""
    add_user_token(root,
                   god_header['X-User-Path'],
                   god_header['X-User-Token'],
                   registry)
    add_user(root, login=participant_login, password=participant_password,
             email='participant@example.org', roles=['participant'],
             registry=registry)
    add_user_token(root,
                   participant_header['X-User-Path'],
                   participant_header['X-User-Token'],
                   registry)
    add_user(root, login=moderator_login, password=moderator_password,
             email='moderator@example.org', roles=['moderator'],
             registry=registry)
    add_user_token(root,
                   moderator_header['X-User-Path'],
                   moderator_header['X-User-Token'],
                   registry)
    add_user(root, login=initiator_login, password=initiator_password,
             email='initiator@example.org', roles=['initiator'],
             registry=registry)
    add_user_token(root,
                   initiator_header['X-User-Path'],
                   initiator_header['X-User-Token'],
                   registry)
    add_user(root, login=admin_login, password=admin_password,
             email='admin@example.org', roles=['admin'], registry=registry)
    add_user_token(root,
                   admin_header['X-User-Path'],
                   admin_header['X-User-Token'],
                   registry)
    add_user_token(root,
                   participant2_header['X-User-Path'],
                   participant2_header['X-User-Token'],
                   registry)
    add_user(root, login=participant2_login, password=participant2_password,
             email='participant2@example.org', roles=['participant'],
             registry=registry)


def add_create_test_users_subscriber(configurator):
    """Register a subscriber to create test users."""
    configurator.add_subscriber(lambda event:
                                add_test_users(event.object, event.registry),
                                IResourceCreatedAndAdded,
                                object_iface=IRootPool)


@fixture(scope='class')
def app(app_settings):
    """Return the adhocracy test wsgi application."""
    return _make_app(app_settings)


def _make_app(app_config):
    import adhocracy_core
    import adhocracy_core.resources.paragraph
    import adhocracy_core.resources.document
    configurator = Configurator(settings=app_config,
                                root_factory=adhocracy_core.root_factory)
    configurator.include(adhocracy_core)
    add_create_test_users_subscriber(configurator)

    app = configurator.make_wsgi_app()
    return app


@fixture(scope='class')
def app_with_filestorage(app_settings: dict):
    """
    Return the adhocracy test wsgi application using a DB with file storage.

    Any DB contents are cleared by this fixture.
    """
    db_file = 'var/test_zeodata/Data.fs'
    blob_dir = 'var/test_zeodata/blobs'
    # Delete old content
    storage = FileStorage.FileStorage(db_file, blob_dir=blob_dir)
    storage.cleanup()
    # This doesn't seem to clear the blob_dir, hence we do so manually
    rmtree(blob_dir, ignore_errors=True)
    our_settings = app_settings.copy()
    our_settings['zodbconn.uri'] = 'file://{}?blobstorage_dir={}'.format(
        db_file, blob_dir)
    return _make_app(our_settings)


@fixture(scope='class')
def newest_activation_path(app):
    """Return the newest activation path generated by app."""
    import re
    mailer = app.registry.messenger.mailer
    last_message_body = mailer.outbox[-1].body
    path_match = re.search(r'/activate/\S+', last_message_body)
    return path_match.group()


@fixture(scope='class')
def newest_reset_path(app) -> callable:
    """Return callable to get newest reset password path generated by app."""
    from urllib.request import unquote
    mailer = app.registry.messenger.mailer

    def get_newest_reset_path():
        last_message_body = mailer.outbox[-1].body
        path_quoted = last_message_body.split('path=')[1].split()[0]
        path = unquote(path_quoted)
        return path
    return get_newest_reset_path


@fixture(scope='class')
def backend(request, zeo, supervisor):
    """Start the backend server with supervisor."""
    output = subprocess.check_output(
        'bin/supervisorctl restart adhocracy_test:test_backend',
        shell=True,
        stderr=subprocess.STDOUT
    )

    def fin():
        subprocess.check_output(
            'bin/supervisorctl stop adhocracy_test:test_backend',
            shell=True,
            stderr=subprocess.STDOUT
        )
    request.addfinalizer(fin)

    return output


@fixture(scope='class')
def backend_with_ws(request, zeo, websocket, supervisor):
    """Start the backend and websocket server with supervisor."""
    output = subprocess.check_output(
        'bin/supervisorctl restart test_backend_with_ws',
        shell=True,
        stderr=subprocess.STDOUT
    )

    def fin():
        subprocess.check_output(
            'bin/supervisorctl stop test_backend_with_ws',
            shell=True,
            stderr=subprocess.STDOUT
        )
    request.addfinalizer(fin)

    return output


class AppUser:
    """:class:`webtest.TestApp` wrapper for backend functional testing."""

    def __init__(self, app,
                 rest_url: str='http://localhost',
                 base_path: str='/',
                 header: dict=None):
        """Initialize self."""
        self.app = TestApp(app)
        """:class:`webtest.TestApp`to send requests to the backend server."""
        self.rest_url = rest_url
        """backend server url to generate request urls."""
        self.base_path = base_path
        """path prefix to generate request urls."""
        self.header = header or {}
        """default header for requests, mostly for authentication."""
        self._resolver = DottedNameResolver()

    def post_resource(self, path: str,
                      iresource: IInterface,
                      cstruct: dict) -> TestResponse:
        """Build and post request to create a new resource."""
        url = self._build_url(path)
        props = self._build_post_body(iresource, cstruct)
        resp = self.app.post_json(url, props, headers=self.header,
                                  expect_errors=True)
        return resp

    def put(self, path: str, cstruct: dict={}) -> TestResponse:
        """Put request to modify a resource."""
        url = self._build_url(path)
        resp = self.app.put_json(url, cstruct, headers=self.header,
                                 expect_errors=True)
        return resp

    def post(self, path: str, cstruct: dict={}) -> TestResponse:
        """Post request to create a new resource."""
        url = self._build_url(path)
        resp = self.app.post_json(url, cstruct, headers=self.header,
                                  expect_errors=True)
        return resp

    def _build_post_body(self, iresource: IInterface, cstruct: dict) -> dict:
        return {'content_type': iresource.__identifier__,
                'data': cstruct}

    def _build_url(self, path: str) -> str:
        if path.startswith('http'):
            return path
        return self.rest_url + self.base_path + path

    def batch(self, subrequests: list):
        """Build and post batch request to the backend rest server."""
        resp = self.app.post_json(batch_url, subrequests, headers=self.header,
                                  expect_errors=True)
        return resp

    def get(self, path: str, params={}) -> TestResponse:
        """Send get request to the backend rest server."""
        url = self._build_url(path)
        resp = self.app.get(url,
                            headers=self.header,
                            params=params,
                            expect_errors=True)
        return resp

    def options(self, path: str) -> TestResponse:
        """Send options request to the backend rest server."""
        url = self._build_url(path)
        resp = self.app.options(url, headers=self.header, expect_errors=True)
        return resp

    def get_postable_types(self, path: str) -> []:
        """Send options request and return the postable content types."""
        resp = self.options(path)
        if 'POST' not in resp.json:
            return []
        post_request_body = resp.json['POST']['request_body']
        type_names = sorted([r['content_type'] for r in post_request_body])
        iresources = [self._resolver.resolve(t) for t in type_names]
        return iresources


@fixture(scope='class')
def app_anonymous(app) -> TestApp:
    """Return backend test app wrapper with participant authentication."""
    return AppUser(app)


@fixture(scope='class')
def app_broken_token(app) -> TestApp:
    """Return backend test app wrapper with participant authentication."""
    return AppUser(app, header=broken_header)


@fixture(scope='class')
def app_participant(app) -> TestApp:
    """Return backend test app wrapper with participant authentication."""
    return AppUser(app, header=participant_header)


@fixture(scope='class')
def app_participant2(app) -> TestApp:
    """Return backend test app wrapper with participant authentication."""
    return AppUser(app, header=participant2_header)


@fixture(scope='class')
def app_moderator(app):
    """Return backend test app wrapper with moderator authentication."""
    return AppUser(app, header=moderator_header)


@fixture(scope='class')
def app_initiator(app):
    """Return backend test app wrapper with initiator authentication."""
    return AppUser(app, header=initiator_header)


@fixture(scope='class')
def app_admin(app):
    """Return backend test app wrapper with admin authentication."""
    return AppUser(app, header=admin_header)


@fixture(scope='class')
def app_god(app):
    """Return backend test app wrapper with god authentication."""
    return AppUser(app, header=god_header)


@fixture(scope='class')
def mailer(app) -> TestApp:
    """Return :class:`pyramid_mailer.mailer.DummyMailer` of `app` fixture."""
    mailer = app.registry.messenger.mailer
    return mailer


@fixture
def datadir(tmpdir, request):
    """Fixture to access tests data.

    Responsible for searching a folder with the same name of test
    module and, if available, moving all contents to a temporary directory so
    tests can use them freely.

    """
    filename = request.module.__file__
    test_dir, _ = os.path.splitext(filename)

    if os.path.isdir(test_dir):
        dir_util.copy_tree(test_dir, str(tmpdir))

    return tmpdir
