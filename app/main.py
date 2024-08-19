from fastapi import FastAPI, HTTPException
from prometheus_client import Counter, Gauge, CollectorRegistry
from pydantic import BaseModel
import redis
import stripe
import os
from datetime import datetime
import time
from functools import wraps

from prometheus_fastapi_instrumentator import Instrumentator, metrics

METRICS_ENDPOINT = "/metrics"

REDIS_FAILURES = Counter('redis_failures_total', 'Total number of Redis failures')
REDIS_LATENCY = Gauge('redis_latency_seconds', 'Redis operation latency in seconds')
STRIPE_FAILURES = Counter('stripe_failures_total', 'Total number of Stripe failures')
STRIPE_LATENCY = Gauge('stripe_latency_seconds', 'Stripe operation latency in seconds')


def redis_operation(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        try:
            result = func(*args, **kwargs)
            REDIS_LATENCY.set(time.time() - start_time)
            return result
        except redis.exceptions.RedisError:
            REDIS_FAILURES.inc()
            raise

    return wrapper


def stripe_operation(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        try:
            result = func(*args, **kwargs)
            STRIPE_LATENCY.set(time.time() - start_time)
            return result
        except stripe.error.StripeError:
            STRIPE_FAILURES.inc()
            raise

    return wrapper


def init_prometheus(app):
    instrumentator = Instrumentator(
        excluded_handlers=[METRICS_ENDPOINT],
        should_instrument_requests_inprogress=True,
        inprogress_labels=True,
    )

    instrumentator.instrument(app)

    instrumentator.add(metrics.latency(should_include_status=False)).add(
        metrics.requests()
    ).add(metrics.request_size()).add(metrics.response_size())

    instrumentator.expose(
        app=app, endpoint=METRICS_ENDPOINT, should_gzip=False, include_in_schema=False
    )


app = FastAPI()
init_prometheus(app)

# Initialize Redis client
redis_client = redis.Redis(host=os.getenv("REDIS_HOST", "localhost"), port=6379, db=0)

# Initialize Stripe
stripe.api_key = os.getenv("STRIPE_API_KEY")


class Item(BaseModel):
    id: str
    name: str
    price: float


class CartItem(BaseModel):
    item_id: str
    quantity: int


@app.get("/status")
async def get_status():
    @redis_operation
    def check_redis_connection():
        return redis_client.ping()

    try:
        # Check Redis connection
        redis_status = check_redis_connection()
    except redis.exceptions.ConnectionError:
        redis_status = False

    return {
        "status": "ok",
        "timestamp": datetime.utcnow().isoformat(),
        "redis_connected": redis_status,
        "stripe_configured": bool(stripe.api_key)
    }


@app.post("/cart/add")
async def add_to_cart(cart_item: CartItem):
    @redis_operation
    def increment_cart_item(item_id, quantity):
        cart_key = f"cart:{item_id}"
        return redis_client.hincrby(cart_key, "quantity", quantity)

    try:
        increment_cart_item(cart_item.item_id, cart_item.quantity)
        return {"message": "Item added to cart"}
    except redis.exceptions.RedisError as e:
        raise HTTPException(status_code=500, detail=f"Redis error: {str(e)}")


@app.post("/cart/checkout")
async def checkout_cart():
    @redis_operation
    def get_cart_items():
        return redis_client.keys("cart:*")

    @redis_operation
    def get_item_data(item_key):
        return redis_client.hgetall(item_key)

    @redis_operation
    def clear_cart(cart_items):
        redis_client.delete(*cart_items)

    @stripe_operation
    def create_stripe_session(total_amount):
        return stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=[{
                "price_data": {
                    "currency": "usd",
                    "unit_amount": int(total_amount * 100),
                    "product_data": {
                        "name": "Cart Checkout",
                    },
                },
                "quantity": 1,
            }],
            mode="payment",
            success_url="https://api.webb.ai/success",
            cancel_url="https://api.webb.ai/cancel",
        )

    try:
        cart_items = get_cart_items()
        total_amount = 0

        for item_key in cart_items:
            item_data = get_item_data(item_key)
            item_id = item_key.decode().split(":")[1]
            quantity = int(item_data[b"quantity"])

            # Fetch item details (assuming you have a separate item storage)
            item = Item(id=item_id, name=f"Item {item_id}", price=10.0)  # Placeholder

            total_amount += item.price * quantity

        session = create_stripe_session(total_amount)

        # Clear the cart after successful checkout
        clear_cart(cart_items)

        return {"checkout_url": session.url}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
