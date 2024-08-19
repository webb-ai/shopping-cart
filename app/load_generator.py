import argparse
import concurrent.futures
import random
import time

import requests

# Base URL of your shopping cart application
BASE_URL = "http://ac039a7b46eb943c0bc027bef517466e-414375886.us-west-2.elb.amazonaws.com/"

# List of sample item IDs (adjust as needed)
ITEM_IDS = ["item1", "item2", "item3", "item4", "item5"]


def add_to_cart():
    """Simulates adding an item to the cart"""
    item_id = random.choice(ITEM_IDS)
    quantity = random.randint(1, 5)

    payload = {
        "item_id": item_id,
        "quantity": quantity
    }

    try:
        response = requests.post(f"{BASE_URL}/cart/add", json=payload)
        if response.status_code == 200:
            print(f"Added {quantity} of {item_id} to cart")
        else:
            print(f"Failed to add item. Status code: {response.status_code}")
    except requests.RequestException as e:
        print(f"Request failed: {e}")


def checkout():
    """Simulates checking out"""
    try:
        response = requests.post(f"{BASE_URL}/cart/checkout")
        if response.status_code == 200:
            print(f"Successfully checked out")
        else:
            print(f"Failed to checkout: {response.status_code}")
    except requests.RequestException as e:
        print(f"Request failed: {e}")


def run_load_test(duration, concurrent_users, run_checkout=False):
    """Runs the load test for a specified duration with concurrent users"""
    start_time = time.time()
    with concurrent.futures.ProcessPoolExecutor(max_workers=concurrent_users) as executor:
        while time.time() - start_time < duration:
            executor.submit(checkout if run_checkout else add_to_cart)
            time.sleep(random.uniform(0.01, 0.1))  # Random delay between requests


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Load generator for shopping cart application")
    parser.add_argument("--duration", type=int, default=60, help="Duration of the load test in seconds")
    parser.add_argument("--users", type=int, default=10, help="Number of concurrent users")
    parser.add_argument("--checkout", type=bool, default=False, help="Run checkout")
    args = parser.parse_args()

    print(f"Starting load test with {args.users} concurrent users for {args.duration} seconds")
    run_load_test(args.duration, args.users, args.checkout)
    print("Load test completed")

#  poetry run python app/load_generator.py --duration 600 --users 20
#  poetry run python app/load_generator.py --duration 300 --users 1
#  poetry run python app/load_generator.py --duration 60 --users 1 --checkout True
