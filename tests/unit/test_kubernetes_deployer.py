# -*- coding: utf-8 -*-
import pytest
import asyncio
import os
import tempfile
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from kubernetes import client
from kubernetes.client.rest import ApiException

from agentscope_runtime.engine.deployers.kubernetes_deployer import (
    KubernetesDeployer,
    RegistryConfig,
    BuildConfig,
    ImageBuilder,
)


@pytest.fixture
def k8s_config():
    """Mock Kubernetes配置"""
    config = Mock()
    config.k8s_namespace = "test-namespace"
    config.kubeconfig_path = None
    return config


@pytest.fixture
def registry_config():
    """Registry配置"""
    return RegistryConfig(
        registry_url="test-registry.com",
        username="test-user",
        password="test-pass",
        namespace="test",
    )


@pytest.fixture
def build_config():
    """Build配置"""
    return BuildConfig(
        build_context_dir="/tmp/test_build",
        build_timeout=60,
        push_timeout=30,
        cleanup_after_build=True,
    )


@pytest.fixture
def sample_user_code():
    """创建示例用户代码"""
    with tempfile.TemporaryDirectory() as temp_dir:
        # 创建示例Python文件
        code_file = os.path.join(temp_dir, "agent.py")
        with open(code_file, "w") as f:
            f.write(
                """
def my_agent(request):
    return {"message": "Hello from agent", "input": request}
""",
            )

        # 创建requirements文件
        req_file = os.path.join(temp_dir, "requirements.txt")
        with open(req_file, "w") as f:
            f.write("fastapi==0.68.0\nuvicorn==0.15.0\n")

        yield temp_dir, code_file, req_file


def sample_agent_func(request):
    """示例agent函数"""
    return {"response": "test", "request": request}


class TestImageBuilder:
    """ImageBuilder测试类"""

    def test_init(self, registry_config, build_config):
        """测试ImageBuilder初始化"""
        builder = ImageBuilder(registry_config, build_config)

        assert builder.registry_config == registry_config
        assert builder.build_config == build_config
        assert os.path.exists(builder.build_config.build_context_dir)

    @patch("os.makedirs")
    def test_setup_build_dir(self, mock_makedirs, registry_config):
        """测试构建目录创建"""
        builder = ImageBuilder(registry_config)
        builder._setup_build_dir()

        mock_makedirs.assert_called_once_with(
            builder.build_config.build_context_dir,
            exist_ok=True,
        )

    @pytest.mark.asyncio
    @patch(
        "agentscope_runtime.engine.deployers.kubernetes_deployer.ImageBuilder._build_image",
    )
    @patch(
        "agentscope_runtime.engine.deployers.kubernetes_deployer.ImageBuilder._push_image",
    )
    @patch(
        "agentscope_runtime.engine.deployers.kubernetes_deployer.ImageBuilder._generate_dockerfile",
    )
    @patch(
        "agentscope_runtime.engine.deployers.kubernetes_deployer.ImageBuilder._prepare_build_context",
    )
    @patch(
        "agentscope_runtime.engine.deployers.kubernetes_deployer.ImageBuilder._cleanup_build_dir",
    )
    async def test_build_user_image(
        self,
        mock_cleanup,
        mock_prepare,
        mock_generate_dockerfile,
        mock_push,
        mock_build,
        registry_config,
        sample_user_code,
    ):
        """测试镜像构建流程"""
        temp_dir, code_file, req_file = sample_user_code

        # 设置mock返回值
        mock_prepare.return_value = None
        mock_generate_dockerfile.return_value = None
        mock_build.return_value = None
        mock_push.return_value = None
        mock_cleanup.return_value = None

        builder = ImageBuilder(registry_config)

        result = await builder.build_user_image(
            user_code_path=temp_dir,
            requirements=req_file,
            base_image="python:3.9-slim",
            func=sample_agent_func,
            image_tag="test-tag",
        )

        # 验证返回值
        assert result == "test-tag"

        # 验证调用顺序
        mock_prepare.assert_called_once()
        mock_generate_dockerfile.assert_called_once()
        mock_build.assert_called_once()
        mock_push.assert_called_once()
        mock_cleanup.assert_called_once()

    @pytest.mark.asyncio
    async def test_prepare_build_context(
        self,
        registry_config,
        sample_user_code,
    ):
        """测试构建上下文准备"""
        temp_dir, code_file, req_file = sample_user_code

        builder = ImageBuilder(registry_config)

        build_dir = "/tmp/test_build_context"
        os.makedirs(build_dir, exist_ok=True)

        try:
            await builder._prepare_build_context(
                build_dir=build_dir,
                user_code_path=temp_dir,
                requirements=req_file,
                func=sample_agent_func,
            )

            # 验证文件是否创建
            assert os.path.exists(os.path.join(build_dir, "user_code"))
            assert os.path.exists(os.path.join(build_dir, "requirements.txt"))
            assert os.path.exists(os.path.join(build_dir, "agent_func.pkl"))
            assert os.path.exists(
                os.path.join(build_dir, "runner_entrypoint.py"),
            )

        finally:
            # 清理测试文件
            import shutil

            if os.path.exists(build_dir):
                shutil.rmtree(build_dir)


class TestKubernetesDeployer:
    """KubernetesDeployer测试类"""

    @patch("kubernetes.config.load_kube_config")
    @patch("kubernetes.client.CoreV1Api")
    @patch("kubernetes.client.AppsV1Api")
    def test_init(
        self,
        mock_apps_v1,
        mock_core_v1,
        mock_load_config,
        k8s_config,
        registry_config,
    ):
        """测试KubernetesDeployer初始化"""
        # 设置mock
        mock_core_v1_instance = Mock()
        mock_core_v1_instance.list_namespace.return_value = Mock()
        mock_core_v1.return_value = mock_core_v1_instance

        mock_apps_v1_instance = Mock()
        mock_apps_v1.return_value = mock_apps_v1_instance

        deployer = KubernetesDeployer(
            k8s_config=k8s_config,
            registry_config=registry_config,
            use_deployment=True,
        )

        # 验证初始化
        assert deployer.k8s_config == k8s_config
        assert deployer.registry_config == registry_config
        assert deployer.use_deployment is True
        assert deployer.namespace == "test-namespace"
        assert isinstance(deployer.image_builder, ImageBuilder)

        # 验证K8s客户端创建
        mock_core_v1.assert_called_once()
        mock_apps_v1.assert_called_once()
        mock_core_v1_instance.list_namespace.assert_called_once()

    @patch("kubernetes.config.load_kube_config")
    @patch("kubernetes.client.CoreV1Api")
    @patch("kubernetes.client.AppsV1Api")
    def test_init_failure(
        self,
        mock_apps_v1,
        mock_core_v1,
        mock_load_config,
        k8s_config,
        registry_config,
    ):
        """测试初始化失败"""
        mock_load_config.side_effect = Exception("Connection failed")

        with pytest.raises(
            RuntimeError,
            match="Kubernetes client initialization failed",
        ):
            KubernetesDeployer(k8s_config, registry_config)

    def test_create_deployment_spec(self, k8s_config, registry_config):
        """测试Deployment规范创建"""
        with patch.multiple(
            "agentscope_runtime.engine.deployers.kubernetes_deployer",
            k8s_config=Mock(),
            client=Mock(),
        ):
            # Mock K8s clients
            with patch("kubernetes.client.CoreV1Api"), patch(
                "kubernetes.client.AppsV1Api",
            ), patch("kubernetes.config.load_kube_config"):
                deployer = KubernetesDeployer(k8s_config, registry_config)
                deployer.v1 = Mock()
                deployer.v1.list_namespace.return_value = Mock()

                spec = deployer._create_deployment_spec(
                    image="test-image",
                    name="test-deploy",
                    port=8090,
                    replicas=3,
                    environment={"ENV": "test"},
                    runtime_config={
                        "resources": {
                            "limits": {"memory": "512Mi", "cpu": "500m"},
                        },
                        "image_pull_secrets": ["test-secret"],
                    },
                )

                # 验证规范
                assert spec.replicas == 3
                assert spec.selector.match_labels == {"app": "test-deploy"}
                assert (
                    spec.template.spec.containers[0].image
                    == "test-registry.com/test-image"
                )
                assert (
                    spec.template.spec.containers[0].ports[0].container_port
                    == 8090
                )
                assert len(spec.template.spec.containers[0].env) == 1
                assert spec.template.spec.containers[0].env[0].name == "ENV"
                assert spec.template.spec.containers[0].env[0].value == "test"

    @pytest.mark.asyncio
    async def test_deploy_success(self, k8s_config, registry_config):
        """测试成功部署"""
        with patch.multiple(
            "agentscope_runtime.engine.deployers.kubernetes_deployer",
            k8s_config=Mock(),
            client=Mock(),
        ):
            with patch("kubernetes.client.CoreV1Api"), patch(
                "kubernetes.client.AppsV1Api",
            ), patch("kubernetes.config.load_kube_config"):
                deployer = KubernetesDeployer(k8s_config, registry_config)
                deployer.v1 = Mock()
                deployer.apps_v1 = Mock()
                deployer.v1.list_namespace.return_value = Mock()

                # Mock ImageBuilder
                mock_image_builder = AsyncMock()
                mock_image_builder.build_user_image.return_value = (
                    "test-image-tag"
                )
                deployer.image_builder = mock_image_builder

                # Mock部署方法
                deployer._create_deployment = Mock(return_value=True)
                deployer._create_service_for_deployment = Mock(
                    return_value=30000,
                )
                deployer._wait_for_deployment_ready = AsyncMock(
                    return_value=True,
                )
                deployer._get_node_ip = Mock(return_value="192.168.1.100")
                deployer.health_check = AsyncMock(return_value=True)

                result = await deployer.deploy(
                    func=sample_agent_func,
                    user_code_path="/tmp/test",
                    requirements_list=["fastapi"],
                    replicas=2,
                )

                # 验证结果
                assert "deploy_id" in result
                assert result["url"] == "http://192.168.1.100:30000"
                assert result["replicas"] == 2

                # 验证调用
                mock_image_builder.build_user_image.assert_called_once()
                deployer._create_deployment.assert_called_once()
                deployer._create_service_for_deployment.assert_called_once()
                deployer._wait_for_deployment_ready.assert_called_once()

    @pytest.mark.asyncio
    async def test_deploy_failure_rollback(self, k8s_config, registry_config):
        """测试部署失败回滚"""
        with patch.multiple(
            "agentscope_runtime.engine.deployers.kubernetes_deployer",
            k8s_config=Mock(),
            client=Mock(),
        ):
            with patch("kubernetes.client.CoreV1Api"), patch(
                "kubernetes.client.AppsV1Api",
            ), patch("kubernetes.config.load_kube_config"):
                deployer = KubernetesDeployer(k8s_config, registry_config)
                deployer.v1 = Mock()
                deployer.apps_v1 = Mock()
                deployer.v1.list_namespace.return_value = Mock()

                # Mock ImageBuilder
                mock_image_builder = AsyncMock()
                mock_image_builder.build_user_image.return_value = (
                    "test-image-tag"
                )
                deployer.image_builder = mock_image_builder

                # Mock部署失败
                deployer._create_deployment = Mock(return_value=False)
                deployer._rollback_deployment = AsyncMock()

                with pytest.raises(
                    RuntimeError,
                    match="Failed to create deployment",
                ):
                    await deployer.deploy(
                        func=sample_agent_func,
                        user_code_path="/tmp/test",
                    )

                # 验证回滚被调用
                deployer._rollback_deployment.assert_called_once()

    @pytest.mark.asyncio
    async def test_scale(self, k8s_config, registry_config):
        """测试扩缩容"""
        with patch.multiple(
            "agentscope_runtime.engine.deployers.kubernetes_deployer",
            k8s_config=Mock(),
            client=Mock(),
        ):
            with patch("kubernetes.client.CoreV1Api"), patch(
                "kubernetes.client.AppsV1Api",
            ), patch("kubernetes.config.load_kube_config"):
                deployer = KubernetesDeployer(
                    k8s_config,
                    registry_config,
                    use_deployment=True,
                )
                deployer.v1 = Mock()
                deployer.apps_v1 = Mock()
                deployer.v1.list_namespace.return_value = Mock()

                # 模拟已有部署
                deploy_id = deployer.deploy_id
                deployer._deployed_resources[deploy_id] = {
                    "deployment_name": "test-deployment",
                    "replicas": 2,
                }

                # Mock Deployment对象
                mock_deployment = Mock()
                mock_deployment.spec.replicas = 2
                deployer.apps_v1.read_namespaced_deployment.return_value = (
                    mock_deployment
                )
                deployer.apps_v1.patch_namespaced_deployment.return_value = (
                    Mock()
                )
                deployer._wait_for_deployment_ready = AsyncMock(
                    return_value=True,
                )

                result = await deployer.scale(5)

                # 验证结果
                assert result is True
                assert deployer._deployed_resources[deploy_id]["replicas"] == 5

                # 验证调用
                deployer.apps_v1.read_namespaced_deployment.assert_called_once()
                deployer.apps_v1.patch_namespaced_deployment.assert_called_once()
                deployer._wait_for_deployment_ready.assert_called_once_with(
                    "test-deployment",
                    5,
                )

    def test_scale_without_deployment_mode(self, k8s_config, registry_config):
        """测试非Deployment模式下的扩缩容"""
        with patch.multiple(
            "agentscope_runtime.engine.deployers.kubernetes_deployer",
            k8s_config=Mock(),
            client=Mock(),
        ):
            with patch("kubernetes.client.CoreV1Api"), patch(
                "kubernetes.client.AppsV1Api",
            ), patch("kubernetes.config.load_kube_config"):
                deployer = KubernetesDeployer(
                    k8s_config,
                    registry_config,
                    use_deployment=False,
                )
                deployer.v1 = Mock()
                deployer.v1.list_namespace.return_value = Mock()

                result = asyncio.run(deployer.scale(3))

                assert result is False

    def test_get_status_deployment_mode(self, k8s_config, registry_config):
        """测试Deployment模式状态查询"""
        with patch.multiple(
            "agentscope_runtime.engine.deployers.kubernetes_deployer",
            k8s_config=Mock(),
            client=Mock(),
        ):
            with patch("kubernetes.client.CoreV1Api"), patch(
                "kubernetes.client.AppsV1Api",
            ), patch("kubernetes.config.load_kube_config"):
                deployer = KubernetesDeployer(
                    k8s_config,
                    registry_config,
                    use_deployment=True,
                )
                deployer.v1 = Mock()
                deployer.apps_v1 = Mock()
                deployer.v1.list_namespace.return_value = Mock()

                # 模拟已有部署
                deploy_id = deployer.deploy_id
                deployer._deployed_resources[deploy_id] = {
                    "deployment_name": "test-deployment",
                }

                # Mock Deployment状态
                mock_deployment = Mock()
                mock_deployment.status.ready_replicas = 3
                mock_deployment.status.replicas = 3
                deployer.apps_v1.read_namespaced_deployment.return_value = (
                    mock_deployment
                )

                status = deployer.get_status()
                assert status == "running"

    def test_get_status_not_found(self, k8s_config, registry_config):
        """测试部署不存在状态"""
        with patch.multiple(
            "agentscope_runtime.engine.deployers.kubernetes_deployer",
            k8s_config=Mock(),
            client=Mock(),
        ):
            with patch("kubernetes.client.CoreV1Api"), patch(
                "kubernetes.client.AppsV1Api",
            ), patch("kubernetes.config.load_kube_config"):
                deployer = KubernetesDeployer(k8s_config, registry_config)
                deployer.v1 = Mock()
                deployer.v1.list_namespace.return_value = Mock()

                status = deployer.get_status()
                assert status == "not_found"

    def test_get_current_replicas(self, k8s_config, registry_config):
        """测试副本状态查询"""
        with patch.multiple(
            "agentscope_runtime.engine.deployers.kubernetes_deployer",
            k8s_config=Mock(),
            client=Mock(),
        ):
            with patch("kubernetes.client.CoreV1Api"), patch(
                "kubernetes.client.AppsV1Api",
            ), patch("kubernetes.config.load_kube_config"):
                deployer = KubernetesDeployer(
                    k8s_config,
                    registry_config,
                    use_deployment=True,
                )
                deployer.v1 = Mock()
                deployer.apps_v1 = Mock()
                deployer.v1.list_namespace.return_value = Mock()

                # 模拟已有部署
                deploy_id = deployer.deploy_id
                deployer._deployed_resources[deploy_id] = {
                    "deployment_name": "test-deployment",
                }

                # Mock Deployment状态
                mock_deployment = Mock()
                mock_deployment.spec.replicas = 5
                mock_deployment.status.ready_replicas = 3
                mock_deployment.status.available_replicas = 3
                mock_deployment.status.updated_replicas = 5
                deployer.apps_v1.read_namespaced_deployment.return_value = (
                    mock_deployment
                )

                replicas = deployer.get_current_replicas()

                expected = {
                    "desired": 5,
                    "ready": 3,
                    "available": 3,
                    "updated": 5,
                }
                assert replicas == expected

    @pytest.mark.asyncio
    async def test_health_check(self, k8s_config, registry_config):
        """测试健康检查"""
        with patch.multiple(
            "agentscope_runtime.engine.deployers.kubernetes_deployer",
            k8s_config=Mock(),
            client=Mock(),
        ):
            with patch("kubernetes.client.CoreV1Api"), patch(
                "kubernetes.client.AppsV1Api",
            ), patch("kubernetes.config.load_kube_config"):
                deployer = KubernetesDeployer(k8s_config, registry_config)
                deployer.v1 = Mock()
                deployer.v1.list_namespace.return_value = Mock()

                # Mock service_url
                deployer.service_url = "http://localhost:30000"

                # Mock aiohttp请求
                with patch("aiohttp.ClientSession") as mock_session:
                    mock_response = Mock()
                    mock_response.status = 200
                    mock_session.return_value.__aenter__.return_value.get.return_value.__aenter__.return_value = (
                        mock_response
                    )

                    result = await deployer.health_check()
                    assert result is True

    @pytest.mark.asyncio
    async def test_remove(self, k8s_config, registry_config):
        """测试删除部署"""
        with patch.multiple(
            "agentscope_runtime.engine.deployers.kubernetes_deployer",
            k8s_config=Mock(),
            client=Mock(),
        ):
            with patch("kubernetes.client.CoreV1Api"), patch(
                "kubernetes.client.AppsV1Api",
            ), patch("kubernetes.config.load_kube_config"):
                deployer = KubernetesDeployer(
                    k8s_config,
                    registry_config,
                    use_deployment=True,
                )
                deployer.v1 = Mock()
                deployer.apps_v1 = Mock()
                deployer.v1.list_namespace.return_value = Mock()

                # 模拟已有部署
                deploy_id = deployer.deploy_id
                deployer._deployed_resources[deploy_id] = {
                    "deployment_name": "test-deployment",
                    "service_name": "test-service",
                }
                deployer._built_images[deploy_id] = "test-image"

                # Mock删除方法
                deployer.v1.delete_namespaced_service.return_value = Mock()
                deployer.apps_v1.delete_namespaced_deployment.return_value = (
                    Mock()
                )
                deployer.image_builder.remove_image = AsyncMock()

                result = await deployer.remove(cleanup_image=True)

                # 验证结果
                assert result is True
                assert deploy_id not in deployer._deployed_resources
                assert deploy_id not in deployer._built_images

                # 验证调用
                deployer.v1.delete_namespaced_service.assert_called_once()
                deployer.apps_v1.delete_namespaced_deployment.assert_called_once()
                deployer.image_builder.remove_image.assert_called_once()


class TestIntegration:
    """集成测试"""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_full_deployment_lifecycle(
        self,
        k8s_config,
        registry_config,
        sample_user_code,
    ):
        """测试完整的部署生命周期（需要真实K8s集群）"""
        # 这个测试需要真实的K8s集群和Docker环境
        # 在CI/CD中应该跳过或使用测试集群
        pytest.skip("Requires real Kubernetes cluster")

        temp_dir, code_file, req_file = sample_user_code

        deployer = KubernetesDeployer(
            k8s_config=k8s_config,
            registry_config=registry_config,
            use_deployment=True,
        )

        try:
            # 部署
            result = await deployer.deploy(
                func=sample_agent_func,
                user_code_path=temp_dir,
                requirements_file=req_file,
                replicas=2,
            )

            assert "deploy_id" in result
            assert "url" in result

            # 检查状态
            assert deployer.is_running
            assert deployer.get_status() == "running"

            # 扩容
            scale_result = await deployer.scale(3)
            assert scale_result is True

            replicas = deployer.get_current_replicas()
            assert replicas["desired"] == 3

            # 健康检查
            health = await deployer.health_check()
            assert health is True

        finally:
            # 清理
            await deployer.remove()


if __name__ == "__main__":
    # 运行测试
    pytest.main([__file__, "-v"])
