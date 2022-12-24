import os
from dotenv import load_dotenv

dev_path = os.path.join(os.getcwd(), ".env.development")
prod_path = os.path.join(os.getcwd(), ".env.production")


if os.path.exists(dev_path):
    load_dotenv(dev_path)  # take environment variables from .env.development
elif os.path.exists(prod_path):
    load_dotenv(prod_path)  # take environment variables from .env.production
else:
    load_dotenv()  # take environment variables from .env


class APP:
    MAX_THREADS = int(os.getenv("MAX_THREADS", 10))


class WC:
    STORE_URL = os.getenv("SITE")
    CONSUMER_KEY = os.getenv("consumer_key")
    CONSUMER_SECRET = os.getenv("consumer_secret")


class DB:
    MONGO_URI = os.getenv("MONGO_URI")
    NAME = os.getenv("MONGO_DB")
    ORDER_COLLECTION = os.getenv("ORDER_COLLECTION", "orders")
    CUSTOMER_COLLECTION = os.getenv("CUSTOMER_COLLECTION", "vendors")
    PRODUCT_COLLECTION = os.getenv("PRODUCT_COLLECTION", "products")
