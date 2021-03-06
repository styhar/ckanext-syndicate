import os

import ckan.plugins as plugins
import ckan.plugins.toolkit as toolkit

from pylons import config
import ckan.model as model
from ckan.model.domain_object import DomainObjectOperation

import ckanext.syndicate


def get_syndicate_flag():
    return config.get('ckan.syndicate.flag', 'syndicate')


def get_syndicated_id():
    return config.get('ckan.syndicate.id', 'syndicated_id')


def get_syndicated_author():
    return config.get('ckan.syndicate.author')


def get_syndicated_name_prefix():
    return config.get('ckan.syndicate.name_prefix', '')


def get_syndicated_organization():
    return config.get('ckan.syndicate.organization', None)


def is_organization_preserved():
    return toolkit.asbool(config.get('ckan.syndicate.replicate_organization', False))


def syndicate_dataset(package_id, topic):
    import ckanext.syndicate.tasks as tasks
    ckan_ini_filepath = os.path.abspath(config['__file__'])
    compat_enqueue(
        'syndicate.sync_package',
        tasks.sync_package_task,
        [package_id, topic, ckan_ini_filepath])


def compat_enqueue(name, fn, args=None):
    u'''
    Enqueue a background job using Celery or RQ.
    '''
    try:
        # Try to use RQ
        from ckan.plugins.toolkit import enqueue_job
        enqueue_job(fn, args=args)
    except ImportError:
        # Fallback to Celery
        import uuid
        from ckan.lib.celery_app import celery
        celery.send_task(name, args=args, task_id=str(uuid.uuid4()))


class SyndicatePlugin(plugins.SingletonPlugin):
    plugins.implements(plugins.IConfigurer)
    plugins.implements(plugins.IDomainObjectModification, inherit=True)

    # IConfigurer

    def update_config(self, config_):
        toolkit.add_template_directory(config_, 'templates')
        toolkit.add_public_directory(config_, 'public')
        toolkit.add_resource('fanstatic', 'syndicate')

    ## Based on ckanext-webhooks plugin
    # IDomainObjectNotification & IResourceURLChange
    def notify(self, entity, operation=None):
        if not operation:
            # This happens on IResourceURLChange
            return

        if isinstance(entity, model.Package):
            self._syndicate_dataset(entity, operation)

    def _syndicate_dataset(self, dataset, operation):
        topic = self._get_topic('dataset', operation)

        if topic is not None and self._syndicate(dataset):
            syndicate_dataset(dataset.id, topic)

    def _syndicate(self, dataset):
        return True
        return (not dataset.private and
                toolkit.asbool(dataset.extras.get(get_syndicate_flag(), 'false')))

    def _get_topic(self, prefix, operation):
        topics = {
            DomainObjectOperation.new: 'create',
            DomainObjectOperation.changed: 'update',
        }

        topic = topics.get(operation, None)

        if topic is not None:
            return '{0}/{1}'.format(prefix, topic)

        return None
