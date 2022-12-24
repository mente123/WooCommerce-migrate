from woocommerce import API
from pymongo import MongoClient
from config import WC, DB


wcapi = API(
    url=WC.STORE_URL,
    consumer_key=WC.CONSUMER_KEY,
    consumer_secret=WC.CONSUMER_SECRET,
    version="wc/v3",
    timeout=120,
)

client = MongoClient(DB.MONGO_URI)
db = client[DB.NAME]

client.server_info()  # authenticate first to check for auth errors before running the script
