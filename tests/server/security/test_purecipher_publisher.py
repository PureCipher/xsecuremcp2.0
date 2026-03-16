from __future__ import annotations

import json

import pytest
from starlette.testclient import TestClient

from purecipher import PureCipherRegistry, RegistryAuthSettings
from purecipher.publisher import (
    check_project,
    load_auth_tokens,
    load_publisher_config,
    login_to_registry,
    package_project,
    publish_project,
    sync_project_artifacts,
    write_publisher_config,
)
from purecipher.publisher.cli import build_parser, init_project, main

TEST_SIGNING_SECRET = "purecipher-registry-signing-secret-for-tests"
TEST_JWT_SECRET = "purecipher-registry-jwt-secret-for-tests"


class TestPureCipherPublisherCLI:
    @staticmethod
    def _make_ready_project(project_root):
        config = load_publisher_config(project_root / "purecipher.toml")
        config.project.publisher = "acme"
        config.publisher.source_url = "https://github.com/acme/weather-lookup"
        config.publisher.homepage_url = "https://acme.dev/weather-lookup"
        config.runtime.endpoint = "https://mcp.acme.dev/weather-lookup"
        config.runtime.docker_image = "ghcr.io/acme/weather-lookup:0.1.0"
        write_publisher_config(project_root / "purecipher.toml", config)
        sync_project_artifacts(project_root, config)
        return config

    @staticmethod
    def _auth_settings() -> RegistryAuthSettings:
        return RegistryAuthSettings.from_values(
            enabled=True,
            issuer="purecipher-registry",
            jwt_secret=TEST_JWT_SECRET,
            users_json="",
        )

    def test_templates_command_lists_supported_templates(self, capsys):
        exit_code = main(["templates"])

        captured = capsys.readouterr()
        assert exit_code == 0
        assert "http: Remote HTTP" in captured.out
        assert "stdio: Local stdio" in captured.out
        assert "docker: Dockerized" in captured.out

    def test_init_project_creates_expected_files(self, tmp_path):
        project_root = tmp_path / "weather-lookup"

        created = init_project(
            project_name="weather-lookup",
            template_name="http",
            project_root=project_root,
            publisher_name="acme",
        )

        assert created == project_root.resolve()
        assert (project_root / "app.py").exists()
        assert (project_root / "pyproject.toml").exists()
        assert (project_root / "purecipher.toml").exists()
        assert (project_root / "manifest.json").exists()
        assert (project_root / "runtime.json").exists()
        assert (project_root / "tools" / "weather_lookup.py").exists()
        assert (project_root / "tests" / "test_smoke.py").exists()

        config = load_publisher_config(project_root / "purecipher.toml")
        assert config.project.name == "weather-lookup"
        assert config.project.template == "http"
        assert config.project.publisher == "acme"

    def test_init_project_rejects_existing_non_empty_directory(self, tmp_path):
        project_root = tmp_path / "publisher-project"
        project_root.mkdir()
        (project_root / "notes.txt").write_text("existing")

        with pytest.raises(ValueError, match="non-empty directory"):
            init_project(
                project_name="publisher-project",
                template_name="http",
                project_root=project_root,
            )

    def test_check_project_syncs_artifacts_and_reports_placeholders(self, tmp_path):
        project_root = tmp_path / "weather-lookup"
        init_project(
            project_name="weather-lookup",
            template_name="http",
            project_root=project_root,
        )

        result = check_project(project_root)

        assert result.ready_to_publish is False
        assert any("placeholder publisher name" in issue for issue in result.issues)
        assert (project_root / "manifest.json").exists()
        assert (project_root / "runtime.json").exists()

        manifest_payload = json.loads((project_root / "manifest.json").read_text())
        runtime_payload = json.loads((project_root / "runtime.json").read_text())
        assert manifest_payload["tool_name"] == "weather-lookup"
        assert runtime_payload["transport"] == "streamable-http"

    def test_check_command_supports_json_output(self, tmp_path, capsys):
        project_root = tmp_path / "weather-lookup"
        init_project(
            project_name="weather-lookup",
            template_name="stdio",
            project_root=project_root,
            publisher_name="acme",
        )

        exit_code = main(["check", str(project_root), "--json"])

        captured = capsys.readouterr()
        payload = json.loads(captured.out)
        assert exit_code == 0
        assert payload["template"] == "stdio"
        assert payload["transport"] == "stdio"
        assert payload["project_root"].endswith("weather-lookup")

    def test_parser_requires_subcommand(self):
        parser = build_parser()

        with pytest.raises(SystemExit):
            parser.parse_args([])

    def test_package_project_writes_publish_ready_artifacts(self, tmp_path):
        project_root = tmp_path / "weather-lookup"
        init_project(
            project_name="weather-lookup",
            template_name="http",
            project_root=project_root,
        )
        self._make_ready_project(project_root)

        result = package_project(project_root)

        assert result.check.ready_to_publish is True
        assert result.submission_payload_path.exists()
        assert result.install_recipes_path.exists()

        submission_payload = json.loads(result.submission_payload_path.read_text())
        install_payload = json.loads(result.install_recipes_path.read_text())
        assert submission_payload["display_name"] == "Weather Lookup"
        assert (
            submission_payload["metadata"]["endpoint"]
            == "https://mcp.acme.dev/weather-lookup"
        )
        assert any(
            recipe["title"] == "Connect From Another App"
            for recipe in install_payload["recipes"]
        )

    def test_package_project_writes_summary_artifacts(self, tmp_path):
        project_root = tmp_path / "weather-lookup"
        init_project(
            project_name="weather-lookup",
            template_name="http",
            project_root=project_root,
        )
        self._make_ready_project(project_root)

        result = package_project(project_root)

        assert result.summary_json_path.exists()
        assert result.summary_markdown_path.exists()

        summary_payload = json.loads(result.summary_json_path.read_text())
        assert summary_payload["tool_name"] == "weather-lookup"
        assert summary_payload["ready_to_publish"] is True
        assert "Connect From Another App" in summary_payload["install_recipe_titles"]

        summary_markdown = result.summary_markdown_path.read_text()
        assert "# Weather Lookup package summary" in summary_markdown
        assert "Install recipe titles" in summary_markdown

    def test_login_to_registry_stores_token(self, tmp_path):
        registry = PureCipherRegistry(
            signing_secret=TEST_SIGNING_SECRET,
            auth_settings=self._auth_settings(),
        )
        app = registry.http_app()
        auth_file = tmp_path / "publisher-auth.json"

        with TestClient(app) as client:
            result = login_to_registry(
                base_url="http://testserver",
                username="publisher",
                password="publisher123",
                auth_file=auth_file,
                client=client,
            )

        assert result.session["role"] == "publisher"
        saved = json.loads(auth_file.read_text())
        assert saved["registries"]["http://testserver"]["token"] == result.token

    def test_login_to_registry_recovers_from_corrupt_auth_file(self, tmp_path):
        registry = PureCipherRegistry(
            signing_secret=TEST_SIGNING_SECRET,
            auth_settings=self._auth_settings(),
        )
        app = registry.http_app()
        auth_file = tmp_path / "publisher-auth.json"
        auth_file.write_text("{broken")

        with TestClient(app) as client:
            result = login_to_registry(
                base_url="http://testserver",
                username="publisher",
                password="publisher123",
                auth_file=auth_file,
                client=client,
            )

        saved = load_auth_tokens(auth_file)
        assert saved["registries"]["http://testserver"]["token"] == result.token

    def test_check_project_preserves_manual_artifact_edits_until_refresh(
        self, tmp_path
    ):
        project_root = tmp_path / "weather-lookup"
        init_project(
            project_name="weather-lookup",
            template_name="http",
            project_root=project_root,
        )
        self._make_ready_project(project_root)

        manifest_path = project_root / "manifest.json"
        manifest_payload = json.loads(manifest_path.read_text())
        manifest_payload["description"] = "Hand-edited manifest description."
        manifest_path.write_text(json.dumps(manifest_payload, indent=2) + "\n")

        result = check_project(project_root)

        assert result.ready_to_publish is False
        assert any(
            "manifest.json no longer matches purecipher.toml" in issue
            for issue in result.issues
        )
        preserved_payload = json.loads(manifest_path.read_text())
        assert preserved_payload["description"] == "Hand-edited manifest description."

        refreshed = check_project(project_root, refresh_artifacts=True)
        refreshed_payload = json.loads(manifest_path.read_text())

        assert refreshed.manifest_updated is True
        assert refreshed.ready_to_publish is True
        assert (
            refreshed_payload["description"]
            == "Weather Lookup built with the PureCipher publisher accelerator."
        )

    def test_publish_project_submits_to_registry(self, tmp_path):
        project_root = tmp_path / "weather-lookup"
        init_project(
            project_name="weather-lookup",
            template_name="stdio",
            project_root=project_root,
        )
        self._make_ready_project(project_root)

        registry = PureCipherRegistry(
            signing_secret=TEST_SIGNING_SECRET,
            auth_settings=self._auth_settings(),
        )
        app = registry.http_app()
        auth_file = tmp_path / "publisher-auth.json"

        with TestClient(app) as client:
            login_to_registry(
                base_url="http://testserver",
                username="publisher",
                password="publisher123",
                auth_file=auth_file,
                client=client,
            )

            result = publish_project(
                project_root,
                base_url="http://testserver",
                auth_file=auth_file,
                client=client,
            )

            assert result.accepted is True
            assert result.tool_name == "weather-lookup"
            assert result.listing_url.endswith("/registry/listings/weather-lookup")

            listing = client.get("/registry/tools/weather-lookup")
            assert listing.status_code == 200
            assert listing.json()["tool_name"] == "weather-lookup"

    def test_publish_project_uses_env_token_when_auth_file_is_missing(
        self,
        tmp_path,
        monkeypatch,
    ):
        project_root = tmp_path / "weather-lookup"
        init_project(
            project_name="weather-lookup",
            template_name="stdio",
            project_root=project_root,
        )
        self._make_ready_project(project_root)

        registry = PureCipherRegistry(
            signing_secret=TEST_SIGNING_SECRET,
            auth_settings=self._auth_settings(),
        )
        app = registry.http_app()

        with TestClient(app) as client:
            login_result = login_to_registry(
                base_url="http://testserver",
                username="publisher",
                password="publisher123",
                auth_file=tmp_path / "publisher-auth.json",
                client=client,
            )
            monkeypatch.setenv("PURECIPHER_PUBLISHER_TOKEN", login_result.token)

            result = publish_project(
                project_root,
                base_url="http://testserver",
                client=client,
            )

        assert result.accepted is True
        assert result.listing_status == "published"
        assert result.review_url is None
        assert result.next_url == result.listing_url

    def test_publish_project_prefers_explicit_token_over_env_token(
        self,
        tmp_path,
        monkeypatch,
    ):
        project_root = tmp_path / "weather-lookup"
        init_project(
            project_name="weather-lookup",
            template_name="stdio",
            project_root=project_root,
        )
        self._make_ready_project(project_root)

        registry = PureCipherRegistry(
            signing_secret=TEST_SIGNING_SECRET,
            auth_settings=self._auth_settings(),
        )
        app = registry.http_app()

        with TestClient(app) as client:
            login_result = login_to_registry(
                base_url="http://testserver",
                username="publisher",
                password="publisher123",
                auth_file=tmp_path / "publisher-auth.json",
                client=client,
            )
            monkeypatch.setenv("PURECIPHER_PUBLISHER_TOKEN", "invalid-token")

            result = publish_project(
                project_root,
                base_url="http://testserver",
                token=login_result.token,
                client=client,
            )

        assert result.accepted is True
        assert result.listing_status == "published"

    def test_publish_project_returns_review_links_for_moderated_registry(
        self,
        tmp_path,
    ):
        project_root = tmp_path / "weather-lookup"
        init_project(
            project_name="weather-lookup",
            template_name="stdio",
            project_root=project_root,
        )
        self._make_ready_project(project_root)

        registry = PureCipherRegistry(
            signing_secret=TEST_SIGNING_SECRET,
            require_moderation=True,
            auth_settings=self._auth_settings(),
        )
        app = registry.http_app()
        auth_file = tmp_path / "publisher-auth.json"

        with TestClient(app) as client:
            login_to_registry(
                base_url="http://testserver",
                username="publisher",
                password="publisher123",
                auth_file=auth_file,
                client=client,
            )

            result = publish_project(
                project_root,
                base_url="http://testserver",
                auth_file=auth_file,
                client=client,
            )

            reviewer_login = login_to_registry(
                base_url="http://testserver",
                username="reviewer",
                password="reviewer123",
                client=client,
            )
            queue = client.get(
                "/registry/review/submissions",
                headers={"authorization": f"Bearer {reviewer_login.token}"},
            )

        assert result.accepted is True
        assert result.listing_status == "pending_review"
        assert result.review_url == "http://testserver/registry/review"
        assert result.next_url == result.review_url
        assert queue.status_code == 200
        assert queue.json()["counts"]["pending_review"] == 1

    def test_publish_project_requeues_existing_listing_for_moderated_registry(
        self,
        tmp_path,
    ):
        project_root = tmp_path / "weather-lookup"
        init_project(
            project_name="weather-lookup",
            template_name="stdio",
            project_root=project_root,
        )
        config = self._make_ready_project(project_root)

        registry = PureCipherRegistry(
            signing_secret=TEST_SIGNING_SECRET,
            require_moderation=True,
            auth_settings=self._auth_settings(),
        )
        app = registry.http_app()
        auth_file = tmp_path / "publisher-auth.json"

        with TestClient(app) as client:
            login_to_registry(
                base_url="http://testserver",
                username="publisher",
                password="publisher123",
                auth_file=auth_file,
                client=client,
            )

            first = publish_project(
                project_root,
                base_url="http://testserver",
                auth_file=auth_file,
                client=client,
            )
            assert first.listing_status == "pending_review"

            reviewer_login = login_to_registry(
                base_url="http://testserver",
                username="reviewer",
                password="reviewer123",
                client=client,
            )
            listing_id = first.response_payload["listing"]["listing_id"]
            approve = client.post(
                f"/registry/review/{listing_id}/approve",
                headers={"authorization": f"Bearer {reviewer_login.token}"},
                json={"moderator_id": "reviewer-1", "reason": "Approved."},
            )
            assert approve.status_code == 200

            config.project.version = "0.2.0"
            write_publisher_config(project_root / "purecipher.toml", config)

            second = publish_project(
                project_root,
                base_url="http://testserver",
                auth_file=auth_file,
                refresh_artifacts=True,
                client=client,
            )

        assert second.accepted is True
        assert second.listing_status == "pending_review"
        assert second.review_url == "http://testserver/registry/review"
