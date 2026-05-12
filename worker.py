import os
import redis
from rq import Worker, Queue, Connection
from app import create_app

app = create_app("production")

if __name__ == "__main__":
    redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    conn = redis.from_url(redis_url)

    with app.app_context():
        with Connection(conn):
            worker = Worker(Queue())
            worker.work()
