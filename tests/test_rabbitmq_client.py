import json

from railway_autoscaler.client.rabbitmq import RabbitMQManagementClient


class FakeResponse:
    def __init__(self, payload):
        self.payload = json.dumps(payload).encode()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return self.payload


def test_queue_metrics_are_read_without_consuming_messages(monkeypatch):
    captured = {}

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["method"] = request.get_method()
        return FakeResponse({"messages_ready": 12, "messages_unacknowledged": 3})

    monkeypatch.setattr("railway_autoscaler.client.rabbitmq.urlopen", fake_urlopen)

    client = RabbitMQManagementClient("http://rabbitmq:15672", "user", "password")
    metrics = client.get_queue_metrics("celery", virtual_host="/")

    assert metrics.ready == 12
    assert metrics.unacked == 3
    assert metrics.total == 15
    assert captured["url"] == "http://rabbitmq:15672/api/queues/%2F/celery"
    assert captured["method"] == "GET"
