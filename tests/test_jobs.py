from reprove.jobs import Job, RedisJobDispatcher


class FakeRedis:
    def __init__(self): self.items = []
    def lpush(self, name, value): self.items.insert(0, (name, value))
    def brpop(self, name, timeout=0):
        if not self.items: return None
        _, value = self.items.pop(0); return name, value


def test_redis_dispatcher_round_trips_structured_job_without_a_server():
    dispatcher = RedisJobDispatcher("redis://unused", client=FakeRedis())
    dispatcher.submit_issue("run-1", "/repo", "claim", ["tests/test.py"], ["pytest"])
    job = dispatcher.dequeue()
    assert job and job.run_id == "run-1"
    assert job.payload["tests"] == ["tests/test.py"]
