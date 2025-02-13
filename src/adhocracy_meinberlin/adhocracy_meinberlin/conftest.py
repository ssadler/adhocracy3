"""Common fixtures for adhocracy_mercator."""
from pytest import fixture


@fixture(scope='class')
def app(app_settings):
    """Return the adhocracy_mercator test wsgi application."""
    from pyramid.config import Configurator
    from adhocracy_core.testing import add_create_test_users_subscriber
    import adhocracy_meinberlin
    configurator = Configurator(settings=app_settings,
                                root_factory=adhocracy_meinberlin.root_factory)
    configurator.include(adhocracy_meinberlin)
    configurator.commit()
    add_create_test_users_subscriber(configurator)
    app = configurator.make_wsgi_app()
    return app


@fixture
def integration(integration):
    """Include resource types and sheets."""
    integration.include('adhocracy_meinberlin.sheets')
    integration.include('adhocracy_meinberlin.resources')
    integration.include('adhocracy_meinberlin.workflows')
    integration.include('adhocracy_meinberlin.content')
    return integration
