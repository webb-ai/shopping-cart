from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import redis
import stripe
import os
from datetime import datetime

from ddtrace import patch_all, tracer
from datadog import initialize, statsd

# Initialize Datadog
initialize(statsd_host=os.getenv('DOGSTATSD_HOST_IP', 'localhost'),
           statsd_port=int(os.getenv('DD_DOGSTATSD_PORT', 8125)))

tracer.configure(hostname=os.getenv('DOGSTATSD_HOST_IP', 'localhost'), port=8125)

patch_all()
app = FastAPI()


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


@app.middleware("http")
async def add_process_time_header(request, call_next):
    start_time = datetime.utcnow()
    response = await call_next(request)
    process_time = (datetime.utcnow() - start_time).total_seconds()
    statsd.histogram('test.api.request.duration.seconds', process_time, tags=[f"endpoint:{request.url.path}"])
    return response

@app.get("/status")
async def get_status():
    try:
        # Check Redis connection
        redis_status = redis_client.ping()
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
    cart_key = f"cart:{cart_item.item_id}"
    redis_client.hincrby(cart_key, "quantity", cart_item.quantity)
    return {"message": "Item added to cart"}

@app.post("/cart/checkout")
async def checkout_cart():
    cart_items = redis_client.keys("cart:*")
    total_amount = 0

    for item_key in cart_items:
        item_data = redis_client.hgetall(item_key)
        item_id = item_key.decode().split(":")[1]
        quantity = int(item_data[b"quantity"])

        # Fetch item details (assuming you have a separate item storage)
        item = Item(id=item_id, name=f"Item {item_id}", price=10.0)  # Placeholder

        total_amount += item.price * quantity

    try:
        # Create Stripe checkout session
        session = stripe.checkout.Session.create(
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
            success_url="https://example.com/success",
            cancel_url="https://example.com/cancel",
        )

        # Clear the cart after successful checkout
        redis_client.delete(*cart_items)

        return {"checkout_url": session.url}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

