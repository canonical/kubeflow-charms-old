import os

from charmhelpers.core import hookenv
from charms import layer
from charms.reactive import set_flag, clear_flag, endpoint_from_flag, when, when_not


@when('charm.kubeflow-seldon-cluster-manager.started')
def charm_ready():
    layer.status.active('')


@when('config.changed')
def update_model():
    clear_flag('charm.kubeflow-seldon-cluster-manager.started')


@when('layer.docker-resource.cluster-manager-image.changed')
def update_image():
    clear_flag('charm.kubeflow-seldon-cluster-manager.started')


@when_not('endpoint.redis.available')
def blocked():
    goal_state = hookenv.goal_state()
    if 'redis' in goal_state['relations']:
        layer.status.waiting('waiting for redis')
    else:
        layer.status.blocked('missing relation to redis')
    clear_flag('charm.kubeflow-seldon-cluster-manager.started')


@when('layer.docker-resource.cluster-manager-image.available')
@when('endpoint.redis.available')
@when_not('charm.kubeflow-seldon-cluster-manager.started')
def start_charm():
    layer.status.maintenance('configuring container')

    config = hookenv.config()
    image_info = layer.docker_resource.get_info('cluster-manager-image')
    redis = endpoint_from_flag('endpoint.redis.available')
    redis_application_name = redis.all_joined_units[0].application_name
    model = os.environ['JUJU_MODEL_NAME']

    layer.caas_base.pod_spec_set({
        'containers': [
            {
                'name': 'seldon-cluster-manager',
                'imageDetails': {
                    'imagePath': image_info.registry_path,
                    'username': image_info.username,
                    'password': image_info.password,
                },
                'ports': [
                    {
                        'name': 'cluster-manager',
                        'containerPort': 8080,
                    },
                ],
                'config': {
                    'ENGINE_CONTAINER_IMAGE_AND_VERSION': config['engine-image'],
                    'ENGINE_CONTAINER_IMAGE_PULL_POLICY': 'IfNotPresent',
                    'ENGINE_CONTAINER_SERVICE_ACCOUNT_NAME': 'default',
                    'JAVA_OPTS': config['java-opts'],
                    'SELDON_CLUSTER_MANAGER_POD_NAMESPACE': model,
                    'SELDON_CLUSTER_MANAGER_REDIS_HOST': f'juju-{redis_application_name}',
                    'SELDON_CLUSTER_MANAGER_SINGLE_NAMESPACE': True,
                    'SPRING_OPTS': config['spring-opts'],
                },
            },
        ],
    })

    layer.status.maintenance('creating container')
    set_flag('charm.kubeflow-seldon-cluster-manager.started')
