import os
import uuid

from pylons import config
import ckan.model as model
import ckan.plugins.toolkit as toolkit
from ckan.lib.celery_app import celery

from ckanext.syndicate.syndicate_model.syndicate_config import SyndicateConfig


def syndicate_individual_dataset(context, data_dict):
    id, api_key = toolkit.get_or_bust(data_dict, ['id', 'api_key'])
    toolkit.check_access('package_update', context, {'id': id})
    profile = model.Session.query(SyndicateConfig).filter_by(
        syndicate_api_key=api_key
    ).first()
    if profile is None:
        raise toolkit.ValidationError(
            'Incorrect API Key for syndication endpoint')

    pkg_dict = toolkit.get_action('package_show')(context, {'id': id})
    endpoints = pkg_dict.get('syndication_endpoints', [])
    if profile.syndicate_url not in endpoints:
        raise toolkit.ValidationError(
            'Syndication endpoint not configured for current dataset')

    _syndicate_dataset(
        id, 'dataset/update',
        _prepare_profile_dict(profile)
    )

    return {}


def syndicate_datasets_by_endpoint(context, data_dict):
    api_key = toolkit.get_or_bust(data_dict, ['api_key'])

    # only sysadmin can perform this action
    toolkit.check_access('config_option_update', context)
    profile = model.Session.query(SyndicateConfig).filter_by(
        syndicate_api_key=api_key
    ).first()
    if profile is None:
        raise toolkit.ValidationError(
            'Incorrect API Key for syndication endpoint')
    packages = model.Session.query(
        model.PackageExtra.package_id.distinct()
    ).filter_by(key='syndication_endpoints').filter(
        model.PackageExtra.value.contains(profile.syndicate_url))
    prepared_profile = _prepare_profile_dict(profile)
    for pkg in packages:
        id = pkg[0]
        _syndicate_dataset(id, 'dataset/update', prepared_profile)

    return {}



def _syndicate_dataset(package_id, topic, profile=None):
    ckan_ini_filepath = os.path.abspath(config['__file__'])
    celery.send_task(
        'syndicate.sync_package',
        args=[package_id, topic, ckan_ini_filepath, profile],
        task_id='{}-{}'.format(str(uuid.uuid4()), package_id)
    )


def _prepare_profile_dict(profile):
    profile_dict = {
            'id': profile.id,
            'syndicate_url': profile.syndicate_url,
            'syndicate_api_key': profile.syndicate_api_key,
            'syndicate_organization': profile.syndicate_organization,
            'syndicate_flag': profile.syndicate_flag,
            'syndicate_field_id': profile.syndicate_field_id,
            'syndicate_prefix': profile.syndicate_prefix,
            'syndicate_replicate_organization': profile.syndicate_replicate_organization,
            'syndicate_author': profile.syndicate_author
        }

    return profile_dict