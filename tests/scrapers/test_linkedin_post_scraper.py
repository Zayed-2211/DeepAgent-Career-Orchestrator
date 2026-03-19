"""
Tests for LinkedInPostScraper actor input wiring.
"""

import sys
import types

# Allow importing scrapers package in environments without optional scraper deps.
if "jobspy" not in sys.modules:
    sys.modules["jobspy"] = types.SimpleNamespace(scrape_jobs=lambda **kwargs: None)
if "apify_client" not in sys.modules:
    sys.modules["apify_client"] = types.SimpleNamespace(ApifyClient=object)

from src.scrapers.linkedin_post_scraper import ACTOR_ID, LinkedInPostScraper


class _FakeActor:
    def __init__(self, client):
        self._client = client

    def call(self, run_input: dict):
        self._client.last_run_input = run_input
        return {"defaultDatasetId": "dataset-1"}


class _FakeDataset:
    def iterate_items(self):
        return iter([{"id": 1}])


class _FakeClient:
    def __init__(self):
        self.last_actor_id = None
        self.last_run_input = None

    def actor(self, actor_id: str):
        self.last_actor_id = actor_id
        return _FakeActor(self)

    def dataset(self, dataset_id: str):
        assert dataset_id == "dataset-1"
        return _FakeDataset()


def test_run_actor_uses_config_max_results(monkeypatch):
    fake_client = _FakeClient()
    monkeypatch.setattr(LinkedInPostScraper, "_init_client", lambda self: fake_client)

    scraper = LinkedInPostScraper(platform_config={"max_results": 7})
    items = scraper._run_actor(["https://www.linkedin.com/search/results/content/?q=test"])

    assert fake_client.last_run_input["maxResults"] == 7
    assert len(items) == 1


def test_run_actor_uses_config_actor_id(monkeypatch):
    fake_client = _FakeClient()
    monkeypatch.setattr(LinkedInPostScraper, "_init_client", lambda self: fake_client)

    scraper = LinkedInPostScraper(platform_config={"actor_id": "custom-actor"})
    scraper._run_actor(["https://www.linkedin.com/search/results/content/?q=test"])

    assert fake_client.last_actor_id == "custom-actor"


def test_run_actor_uses_default_actor_id_when_not_configured(monkeypatch):
    fake_client = _FakeClient()
    monkeypatch.setattr(LinkedInPostScraper, "_init_client", lambda self: fake_client)

    scraper = LinkedInPostScraper(platform_config={})
    scraper._run_actor(["https://www.linkedin.com/search/results/content/?q=test"])

    assert fake_client.last_actor_id == ACTOR_ID
